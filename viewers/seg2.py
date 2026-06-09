"""SEG-2 shot-gather viewer — wiggle / image plot of the traces.

Reads a SEG-2 record (the seismic ``.dat`` / ``.seg2`` format) with **ObsPy**
(optional) and plots the gather: every trace drawn vertically (time increasing
downward), trace number on the x-axis — the standard shot-gather view.  A
**Wiggle / Image** toggle, an optional variable-area **Fill**, and a **first-K
traces** cap round it out.

Optional deps: **obspy** (reads the file — registration is skipped without it, so
SEG-2 files fall through to the binary hex viewer) and **matplotlib** (the plot —
degrades to a header/stats text summary when absent).

The viewer claims a file by a magic-byte sniff of the SEG-2 file-descriptor block
ID (``0x3a55`` / ``0x553a``), so it handles ``.dat`` records regardless of the
extension while never stealing a non-SEG-2 ``.dat``.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..registry import ViewerSpec, register_viewer
from .base import FileViewer

log = logging.getLogger(__name__)

MAX_SEG2_BYTES: int = 256 * 1024 * 1024  # 256 MB
_MAX_WIGGLES_DEFAULT = 48
#: SEG-2 file-descriptor block IDs, either byte order (the file-type marker).
_SEG2_MAGIC = (b"\x55\x3a", b"\x3a\x55")
_WIGGLE_COLOR = "#2E86C1"


def is_seg2(path: Path) -> bool:
    """True when *path* starts with a SEG-2 file-descriptor block ID."""
    try:
        with open(path, "rb") as fh:
            return fh.read(2) in _SEG2_MAGIC
    except OSError:
        return False


def _read_seg2(path: Path):
    """``(data (n_traces, n_samples), dt, receiver_xs, source_x)`` via ObsPy."""
    import numpy as np
    import obspy

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # ObsPy's custom-header advisory is noisy
        st = obspy.read(str(path), format="SEG2")
    data = np.array([tr.data for tr in st], dtype=float)
    dt = float(st[0].stats.delta) if len(st) else 0.0

    def _hdr(tr, key):
        seg2 = tr.stats.get("seg2", {}) or {}
        raw = seg2.get(key)
        try:
            return float(raw) if raw not in (None, "") else None
        except (TypeError, ValueError):
            return None

    rx = [_hdr(tr, "RECEIVER_LOCATION") for tr in st]
    sx = _hdr(st[0], "SOURCE_LOCATION") if len(st) else None
    return data, dt, rx, sx


class Seg2Viewer(FileViewer):
    """Wiggle / image plot of a SEG-2 shot gather."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._data = None
        self._dt = 0.0
        self._rx = []
        self._sx = None
        self._path: Optional[Path] = None
        self._canvas = None
        self._figure = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 0)
        bar.addWidget(QLabel("Style:"))
        self._style = QComboBox()
        self._style.addItems(["Wiggle", "Image"])
        self._style.currentIndexChanged.connect(self._render)
        bar.addWidget(self._style)
        self._fill = QCheckBox("Fill")
        self._fill.toggled.connect(self._render)
        bar.addWidget(self._fill)
        bar.addSpacing(10)
        bar.addWidget(QLabel("First N:"))
        self._k = QSpinBox()
        self._k.setRange(1, 100000)
        self._k.setValue(_MAX_WIGGLES_DEFAULT)
        self._k.valueChanged.connect(self._render)
        bar.addWidget(self._k)
        bar.addStretch(1)
        outer.addLayout(bar)

        self._stack = QStackedWidget()
        outer.addWidget(self._stack, 1)
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._stack.addWidget(self._text)

    # ------------------------------------------------------------------
    def load_path(self, path: Path) -> None:
        self._path = Path(path)
        try:
            self._data, self._dt, self._rx, self._sx = _read_seg2(self._path)
        except Exception as exc:  # noqa: BLE001
            self._data = None
            self._text.setPlainText(f"Could not read SEG-2 gather:\n{exc}")
            self._stack.setCurrentWidget(self._text)
            self.load_failed.emit(path, str(exc))
            return
        self._render()
        self.file_loaded.emit(path)

    def clear(self) -> None:
        self._data = None
        self._path = None
        self._text.clear()

    def max_preview_bytes(self) -> Optional[int]:
        return MAX_SEG2_BYTES

    # ------------------------------------------------------------------
    def _ensure_canvas(self) -> bool:
        if self._canvas is not None:
            return True
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
        except Exception:  # noqa: BLE001 -- matplotlib optional
            return False
        self._figure = Figure(figsize=(5, 4))
        self._figure.subplots_adjust(left=0.1, right=0.98, top=0.92, bottom=0.12)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._stack.addWidget(self._canvas)
        return True

    def _render(self, *_a) -> None:
        if self._data is None:
            return
        if not self._ensure_canvas():
            self._show_summary(prefix="(install matplotlib to plot the gather)\n\n")
            return
        import numpy as np

        data = self._data
        n = min(int(self._k.value()), data.shape[0])
        block = data[:n]
        t = np.arange(block.shape[1]) * (self._dt or 1.0)

        self._figure.clear()
        ax = self._figure.add_subplot(111)
        if self._style.currentText() == "Image":
            peak = float(np.max(np.abs(block))) or 1.0
            ax.imshow(block.T, aspect="auto", cmap="seismic", vmin=-peak, vmax=peak,
                      extent=[0.5, n + 0.5, t[-1], 0.0])
        else:
            self._wiggle(ax, block, t, self._fill.isChecked())
        ax.set_xlabel("trace")
        ax.set_ylabel("time (s)")
        title = self._path.name if self._path else "SEG-2"
        extra = f" · {data.shape[0]} traces"
        if self._sx is not None:
            extra += f" · source x {self._sx:g} m"
        ax.set_title(title + extra, fontsize=10)
        try:
            self._canvas.draw()
        except Exception:  # noqa: BLE001
            pass
        self._stack.setCurrentWidget(self._canvas)

    @staticmethod
    def _wiggle(ax, block, t, fill: bool) -> None:
        import numpy as np
        from matplotlib.collections import LineCollection

        n = block.shape[0]
        peak = np.max(np.abs(block), axis=1)
        peak[peak == 0.0] = 1.0
        xs = np.arange(n)[:, None] + 0.45 * block / peak[:, None]
        segs = [np.column_stack([xs[i], t]) for i in range(n)]
        ax.add_collection(LineCollection(segs, colors=_WIGGLE_COLOR, linewidths=0.6))
        if fill:
            for i in range(n):
                ax.fill_betweenx(t, i, xs[i], where=(xs[i] >= i),
                                 color=_WIGGLE_COLOR, alpha=0.4)
        ax.set_ylim(t[-1], t[0])         # time increases downward
        ax.set_xlim(-0.7, n - 0.3)
        step = max(1, n // 8)
        ax.set_xticks(range(0, n, step))
        ax.set_xticklabels([str(i + 1) for i in range(0, n, step)])

    def _show_summary(self, prefix: str = "") -> None:
        import numpy as np
        d = self._data
        n_tr, n_s = (d.shape if d is not None and d.ndim == 2 else (0, 0))
        peak = float(np.max(np.abs(d))) if d is not None and d.size else 0.0
        lines = [prefix + f"SEG-2 gather : {self._path.name if self._path else ''}",
                 f"traces       : {n_tr}",
                 f"samples      : {n_s}",
                 f"dt           : {self._dt * 1000:.4f} ms"
                 + (f"  ({1.0 / self._dt:.1f} Hz)" if self._dt else ""),
                 f"length       : {n_s * self._dt:.4f} s",
                 f"source x     : {self._sx if self._sx is not None else 'n/a'}",
                 f"peak |amp|   : {peak:.4g}"]
        self._text.setPlainText("\n".join(lines))
        self._stack.setCurrentWidget(self._text)


# obspy is required to read the gather; skip registration without it so SEG-2
# files fall through to the binary hex viewer (the package contract).
try:  # noqa: SIM105
    import obspy as _obspy  # noqa: F401
    _HAS_OBSPY = True
except Exception:  # noqa: BLE001
    _HAS_OBSPY = False
    log.debug("seg2 viewer: obspy unavailable; SEG-2 falls back to the binary viewer")

if _HAS_OBSPY:
    register_viewer(ViewerSpec(
        key="seg2",
        label="SEG-2 gather",
        extensions=(".seg2", ".sg2"),
        factory=Seg2Viewer,
        can_view=is_seg2,                 # claim .dat (and any) SEG-2 by magic bytes
        priority=10,
        description="Wiggle / image plot of a SEG-2 shot gather (via obspy).",
    ))


__all__ = ["Seg2Viewer", "is_seg2", "MAX_SEG2_BYTES"]
