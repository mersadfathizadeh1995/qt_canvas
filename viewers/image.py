"""Image viewer — QPixmap in a scrollable QLabel.

Handles the formats Qt natively supports (PNG, JPEG, BMP, GIF, WEBP
on most builds, TIFF on some).  No optional dependency — :class:`QPixmap`
ships with PySide6.

Files are scaled down to ``MAX_DISPLAY_WIDTH`` if wider so a 30-megapixel
photo doesn't paint a 5000-px-wide widget; the underlying pixmap is
kept full-resolution so the user can scroll-zoom in a future iteration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from ..registry import ViewerSpec, register_viewer
from .base import FileViewer

#: Largest width we render at once.  Above this we scale down for the
#: display copy but keep the original around so a future zoom action
#: can blow it back up.
MAX_DISPLAY_WIDTH: int = 1200

#: Hard upper bound on file size to keep the load synchronous and
#: predictable.  Beyond this we hand off to the binary fallback.
MAX_IMAGE_BYTES: int = 64 * 1024 * 1024  # 64 MB


class ImageViewer(FileViewer):
    """Scrollable image preview."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._original: Optional[QPixmap] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setBackgroundRole(self.backgroundRole())

        self._label = QLabel(self._scroll)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setScaledContents(False)
        self._scroll.setWidget(self._label)

        layout.addWidget(self._scroll)

    # ------------------------------------------------------------------
    def load_path(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._label.setText(f"Cannot decode image: {path.name}")
            self._original = None
            self.load_failed.emit(path, "QPixmap returned a null image")
            return
        self._original = pixmap
        display = pixmap
        if pixmap.width() > MAX_DISPLAY_WIDTH:
            display = pixmap.scaledToWidth(
                MAX_DISPLAY_WIDTH, Qt.SmoothTransformation
            )
        self._label.setPixmap(display)
        self._label.setText("")
        self.file_loaded.emit(path)

    def clear(self) -> None:
        self._label.clear()
        self._original = None

    def max_preview_bytes(self) -> Optional[int]:
        return MAX_IMAGE_BYTES


register_viewer(ViewerSpec(
    key="image",
    label="Image",
    extensions=(".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"),
    factory=ImageViewer,
    priority=10,
    description="Scrollable image preview using QPixmap.",
))


__all__ = ["ImageViewer", "MAX_DISPLAY_WIDTH", "MAX_IMAGE_BYTES"]
