"""PDF viewer — QPdfView + QPdfDocument.

Skips registration when :mod:`PySide6.QtPdf` is missing (some
minimal Linux Qt builds); files of that type then fall through to
the binary viewer.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..registry import ViewerSpec, register_viewer
from .base import FileViewer

log = logging.getLogger(__name__)

#: Hard cap; above this :class:`ViewerStack` short-circuits to the
#: binary viewer.  Big technical reports fit comfortably.
MAX_PDF_BYTES: int = 200 * 1024 * 1024  # 200 MB

try:
    from PySide6.QtPdf import QPdfDocument  # type: ignore
    from PySide6.QtPdfWidgets import QPdfView  # type: ignore
    _QTPDF_OK = True
except Exception:  # noqa: BLE001
    _QTPDF_OK = False


class PdfViewer(FileViewer):
    """Rendered PDF preview backed by :class:`QPdfView`.

    Multi-page scroll mode by default; users can zoom with the mouse
    wheel via Qt's built-in handler.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._doc = QPdfDocument(self)
        self._view = QPdfView(self)
        self._view.setDocument(self._doc)
        self._view.setPageMode(QPdfView.PageMode.MultiPage)
        layout.addWidget(self._view)

    # ------------------------------------------------------------------
    def load_path(self, path: Path) -> None:
        # ``QPdfDocument.load`` accepts a file path and returns Status.
        status = self._doc.load(str(path))
        # PySide6 6.4+ returns a QPdfDocument.Status enum; treat
        # anything other than ``Ready`` as a fail and fall back.
        ok = (status == QPdfDocument.Status.Ready) if hasattr(
            QPdfDocument, "Status"
        ) else True
        if not ok:
            self.load_failed.emit(path, "QPdfDocument failed to load")
            return
        self.file_loaded.emit(path)

    def clear(self) -> None:
        try:
            self._doc.close()
        except Exception:  # noqa: BLE001
            pass

    def max_preview_bytes(self) -> Optional[int]:
        return MAX_PDF_BYTES


if _QTPDF_OK:
    register_viewer(ViewerSpec(
        key="pdf",
        label="PDF",
        extensions=(".pdf",),
        factory=PdfViewer,
        priority=10,
        description="Multi-page PDF rendered with QPdfView.",
    ))
else:
    log.debug("PySide6.QtPdf missing — pdf viewer not registered (falls back to binary)")


__all__ = ["MAX_PDF_BYTES", "PdfViewer"]
