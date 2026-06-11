"""Image viewer — zoomable, pannable QGraphicsView.

Handles the formats Qt natively supports (PNG, JPEG, BMP, GIF, WEBP
on most builds, TIFF on some).  No optional dependency — :class:`QPixmap`
ships with PySide6.

Interaction
-----------
* **Mouse wheel** zooms around the cursor (Ctrl not required).
* **Left-drag** pans (open-hand cursor).
* Control bar: zoom out / zoom in / **Fit** / **100 %** and a live
  percentage readout.
* The image always loads at fit-to-view; the full-resolution pixmap is
  kept so zooming in shows native pixels.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPixmap, QTransform
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..registry import ViewerSpec, register_viewer
from .base import FileViewer

#: Kept for back-compat with earlier imports; the QGraphicsView scales
#: freely so no display-copy downscaling happens any more.
MAX_DISPLAY_WIDTH: int = 1200

#: Hard upper bound on file size to keep the load synchronous and
#: predictable.  Beyond this we hand off to the binary fallback.
MAX_IMAGE_BYTES: int = 64 * 1024 * 1024  # 64 MB

_ZOOM_MIN = 0.02
_ZOOM_MAX = 32.0
_ZOOM_STEP = 1.25


class _ZoomView(QGraphicsView):
    """Graphics view with cursor-anchored wheel zoom and drag pan."""

    zoom_changed = Signal(float)

    def __init__(self, scene: QGraphicsScene, parent: Optional[QWidget] = None) -> None:
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setFrameShape(QGraphicsView.NoFrame)

    # current uniform scale factor (m11 == m22 for uniform zoom)
    def zoom(self) -> float:
        return float(self.transform().m11())

    def set_zoom(self, factor: float) -> None:
        factor = max(_ZOOM_MIN, min(_ZOOM_MAX, float(factor)))
        self.setTransform(QTransform().scale(factor, factor))
        self.zoom_changed.emit(factor)

    def zoom_by(self, step: float) -> None:
        self.set_zoom(self.zoom() * step)

    def fit(self) -> None:
        items = self.scene().items()
        if not items:
            return
        self.fitInView(self.scene().itemsBoundingRect(), Qt.KeepAspectRatio)
        self.zoom_changed.emit(self.zoom())

    def wheelEvent(self, event) -> None:  # noqa: N802 (Qt override)
        delta = event.angleDelta().y()
        if delta == 0:
            return
        self.zoom_by(_ZOOM_STEP if delta > 0 else 1.0 / _ZOOM_STEP)
        event.accept()


class ImageViewer(FileViewer):
    """Zoomable / pannable image preview."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._original: Optional[QPixmap] = None
        self._item: Optional[QGraphicsPixmapItem] = None
        self._message = QLabel("")
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setVisible(False)

        self._scene = QGraphicsScene(self)
        self._view = _ZoomView(self._scene, self)
        self._view.zoom_changed.connect(self._on_zoom_changed)

        bar = QHBoxLayout()
        bar.setContentsMargins(6, 4, 6, 2)
        bar.setSpacing(4)

        def btn(text: str, tip: str, slot) -> QToolButton:
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setAutoRaise(True)
            b.clicked.connect(slot)
            bar.addWidget(b)
            return b

        self._zoom_out_btn = btn("−", "Zoom out (wheel down)",
                                 lambda: self._view.zoom_by(1.0 / _ZOOM_STEP))
        self._zoom_in_btn = btn("+", "Zoom in (wheel up)",
                                lambda: self._view.zoom_by(_ZOOM_STEP))
        self._fit_btn = btn("Fit", "Fit the image to the window",
                            self._view.fit)
        self._full_btn = btn("100%", "Show at native resolution",
                             lambda: self._view.set_zoom(1.0))
        self._zoom_label = QLabel("")
        self._zoom_label.setMinimumWidth(48)
        bar.addWidget(self._zoom_label)
        bar.addStretch(1)
        hint = QLabel("wheel = zoom · drag = pan")
        hint.setStyleSheet("color: gray;")
        bar.addWidget(hint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(bar)
        layout.addWidget(self._view, 1)
        layout.addWidget(self._message)

    # ------------------------------------------------------------------
    def load_path(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.clear()
            self._message.setText(f"Cannot decode image: {path.name}")
            self._message.setVisible(True)
            self.load_failed.emit(path, "QPixmap returned a null image")
            return
        self._message.setVisible(False)
        self._original = pixmap
        self._scene.clear()
        self._item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(self._item.boundingRect())
        self._view.fit()
        self.file_loaded.emit(path)

    def clear(self) -> None:
        self._scene.clear()
        self._item = None
        self._original = None
        self._message.setVisible(False)
        self._zoom_label.setText("")

    def max_preview_bytes(self) -> Optional[int]:
        return MAX_IMAGE_BYTES

    # ------------------------------------------------------------------
    def zoom(self) -> float:
        """Current zoom factor (1.0 = native pixels)."""
        return self._view.zoom()

    def _on_zoom_changed(self, factor: float) -> None:
        self._zoom_label.setText(f"{factor * 100:.0f}%")


register_viewer(ViewerSpec(
    key="image",
    label="Image",
    extensions=(".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"),
    factory=ImageViewer,
    priority=10,
    description="Zoomable, pannable image preview (wheel = zoom, drag = pan).",
))


__all__ = ["ImageViewer", "MAX_DISPLAY_WIDTH", "MAX_IMAGE_BYTES"]
