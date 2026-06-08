"""NumPy ``.npz`` viewer — heatmap a 2-D array, list the rest.

Renders a NumPy archive: the 2-D array(s) as a heatmap (matplotlib, optional),
using 1-D arrays named like axes (``freqs`` / ``frequencies`` x ``velocities``)
for the extent when present, and overlaying a per-column 1-D array (e.g.
``picked_velocities``) as a curve.  When matplotlib is missing or there's no 2-D
array, it falls back to a compact key / shape / dtype listing.

Generic — it works for any spectrum-like archive; it does the right thing for the
two FK_Pro schemas (``spectrum.npz`` = power(F,V)+freqs+velocities; the DC-cut npz
= power(V,F)+frequencies+velocities+picked_velocities).

Optional deps: **numpy** (needed to read the file — registration is skipped when
absent, so ``.npz`` falls through to the binary hex viewer) and **matplotlib**
(the heatmap — degrades to the text listing when absent).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..registry import ViewerSpec, register_viewer
from .base import FileViewer

log = logging.getLogger(__name__)

MAX_NPZ_BYTES: int = 256 * 1024 * 1024  # 256 MB

# axis-name heuristics (lower-cased exact matches)
_X_NAMES = ("freqs", "frequencies", "freq", "frequency", "x")
_Y_NAMES = ("velocities", "velocity", "vel", "slowness", "y")
_PICK_NAMES = ("picked_velocities", "picked", "pick", "ridge")


class NpzViewer(FileViewer):
    """Heatmap the 2-D array(s) in a ``.npz``; list the rest."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._path: Optional[Path] = None
        self._data: dict = {}
        self._canvas = None
        self._figure = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 0)
        bar.addWidget(QLabel("Array:"))
        self._combo = QComboBox()
        self._combo.currentIndexChanged.connect(self._render_current)
        bar.addWidget(self._combo)
        bar.addStretch(1)
        outer.addLayout(bar)

        self._stack = QStackedWidget()
        outer.addWidget(self._stack, 1)
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._stack.addWidget(self._text)

    # ------------------------------------------------------------------
    def load_path(self, path: Path) -> None:
        import numpy as np

        self._path = Path(path)
        try:
            with np.load(path, allow_pickle=False) as npz:
                self._data = {k: npz[k] for k in npz.files}
        except Exception as exc:  # noqa: BLE001
            self._data = {}
            self._text.setPlainText(f"Cannot read .npz: {exc}")
            self._stack.setCurrentWidget(self._text)
            self.load_failed.emit(path, str(exc))
            return

        twod = [k for k, v in self._data.items() if getattr(v, "ndim", 0) == 2]
        self._combo.blockSignals(True)
        self._combo.clear()
        for k in twod:
            self._combo.addItem(f"{k}  {tuple(self._data[k].shape)}", k)
        self._combo.blockSignals(False)
        self._combo.setVisible(len(twod) > 1)

        if twod:
            self._render_current()
        else:
            self._show_listing()
        self.file_loaded.emit(path)

    def clear(self) -> None:
        self._data = {}
        self._path = None
        self._text.clear()

    def max_preview_bytes(self) -> Optional[int]:
        return MAX_NPZ_BYTES

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
        self._figure.subplots_adjust(left=0.12, right=0.99, top=0.92, bottom=0.12)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._stack.addWidget(self._canvas)
        return True

    def _render_current(self, *_a) -> None:
        if not self._data:
            return
        key = self._combo.currentData()
        if key is None:
            self._show_listing()
            return
        if not self._ensure_canvas():
            self._show_listing(prefix="(install matplotlib to plot arrays)\n\n")
            return
        import numpy as np

        arr = np.asarray(self._data[key], dtype=float)
        x = self._axis(_X_NAMES)
        y = self._axis(_Y_NAMES)
        power = arr
        extent = None
        if x is not None and y is not None:
            # orient to (rows=y, cols=x) for imshow(origin="lower")
            if arr.shape == (len(x), len(y)):
                power = arr.T
            extent = [float(x[0]), float(x[-1]), float(y[0]), float(y[-1])]

        self._figure.clear()
        ax = self._figure.add_subplot(111)
        im = ax.imshow(power, aspect="auto", origin="lower", cmap="turbo", extent=extent)
        self._figure.colorbar(im, ax=ax, shrink=0.85)
        pick = self._pick()
        if pick is not None and x is not None and len(pick) == len(x):
            ax.plot(x, pick, color="#FFFFFF", lw=1.0, alpha=0.9, label="picked")
            ax.legend(loc="upper right", fontsize=8)
        ax.set_xlabel(self._axis_name(_X_NAMES) or "column")
        ax.set_ylabel(self._axis_name(_Y_NAMES) or "row")
        ax.set_title(f"{self._path.name if self._path else ''} · {key}")
        try:
            self._canvas.draw()
        except Exception:  # noqa: BLE001
            pass
        self._stack.setCurrentWidget(self._canvas)

    # -- array helpers -----------------------------------------------------
    def _named(self, names):
        for n in names:
            for k, v in self._data.items():
                if k.lower() == n and getattr(v, "ndim", 0) == 1:
                    return k, v
        return None, None

    def _axis(self, names):
        import numpy as np
        _, v = self._named(names)
        return None if v is None else np.asarray(v, dtype=float)

    def _axis_name(self, names):
        k, _ = self._named(names)
        return k

    def _pick(self):
        return self._axis(_PICK_NAMES)

    def _show_listing(self, prefix: str = "") -> None:
        lines = [prefix + (self._path.name if self._path else ".npz")]
        for k, v in self._data.items():
            shape = getattr(v, "shape", ())
            dtype = getattr(v, "dtype", "?")
            if getattr(v, "ndim", 1) == 0:
                lines.append(f"  {k}: {v}  ({dtype})")
            else:
                lines.append(f"  {k}: shape {tuple(shape)}  {dtype}")
        self._text.setPlainText("\n".join(lines))
        self._stack.setCurrentWidget(self._text)


# numpy is required to read the archive at all; skip registration without it so
# ``.npz`` cleanly falls through to the binary hex viewer (the package contract).
try:  # noqa: SIM105
    import numpy as _np  # noqa: F401
    _HAS_NUMPY = True
except Exception:  # noqa: BLE001
    _HAS_NUMPY = False
    log.debug("npz viewer: numpy unavailable; .npz falls back to the binary viewer")

if _HAS_NUMPY:
    register_viewer(ViewerSpec(
        key="npz",
        label="NumPy archive",
        extensions=(".npz",),
        factory=NpzViewer,
        priority=10,
        description="Heatmap the 2-D array(s) in a .npz; list the rest.",
    ))


__all__ = ["NpzViewer", "MAX_NPZ_BYTES"]
