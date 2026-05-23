"""Markdown viewer — QTextBrowser.setMarkdown (stdlib Qt).

No optional dependency.  Tables, code blocks, and headings render
out of the box on Qt ≥ 5.14; older Qt falls back to plain text.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from ..registry import ViewerSpec, register_viewer
from .base import FileViewer

#: Cap so a 50 MB README doesn't lock the renderer.  Beyond this the
#: viewer reads the first N bytes and appends a truncation note.
MAX_MARKDOWN_BYTES: int = 4 * 1024 * 1024  # 4 MB


class MarkdownViewer(FileViewer):
    """Rendered markdown preview backed by :class:`QTextBrowser`."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._browser = QTextBrowser(self)
        self._browser.setOpenExternalLinks(True)
        layout.addWidget(self._browser)

    # ------------------------------------------------------------------
    def load_path(self, path: Path) -> None:
        try:
            raw = path.read_bytes()[: MAX_MARKDOWN_BYTES + 1]
        except OSError as exc:
            self._browser.setPlainText(f"Cannot read: {exc}")
            self.load_failed.emit(path, str(exc))
            return
        truncated = len(raw) > MAX_MARKDOWN_BYTES
        text = raw[:MAX_MARKDOWN_BYTES].decode("utf-8", errors="replace")
        if truncated:
            text += f"\n\n*…truncated to first {MAX_MARKDOWN_BYTES:,} bytes…*"
        # Set the source so relative image links resolve correctly.
        self._browser.setSearchPaths([str(path.parent)])
        self._browser.setMarkdown(text)
        self.file_loaded.emit(path)

    def clear(self) -> None:
        self._browser.clear()

    def max_preview_bytes(self) -> Optional[int]:
        return MAX_MARKDOWN_BYTES


register_viewer(ViewerSpec(
    key="markdown",
    label="Markdown",
    extensions=(".md", ".markdown"),
    factory=MarkdownViewer,
    priority=10,
    description="Rendered markdown using QTextBrowser.setMarkdown().",
))


__all__ = ["MarkdownViewer", "MAX_MARKDOWN_BYTES"]
