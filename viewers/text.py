"""Text viewer — QPlainTextEdit with optional Pygments syntax highlighting.

Always registers — without Pygments the viewer falls back to plain
monospace text.  Highlighting is applied only for the first
:data:`HIGHLIGHT_BYTE_CAP` bytes to keep large logs responsive.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QFontDatabase,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

from ..registry import ViewerSpec, register_viewer
from .base import FileViewer

log = logging.getLogger(__name__)

#: Maximum bytes we read for the viewer.  Above this we truncate and
#: append a marker — viewer stays usable.
MAX_TEXT_BYTES: int = 16 * 1024 * 1024  # 16 MB

#: Bytes considered for Pygments highlighting.  Beyond this we drop
#: highlighting so the highlighter doesn't lock the UI thread.
HIGHLIGHT_BYTE_CAP: int = 1024 * 1024  # 1 MB

try:
    from pygments import lexers as _pyg_lexers  # type: ignore
    from pygments import token as _pyg_token    # type: ignore
    from pygments.util import ClassNotFound     # type: ignore
    _PYGMENTS_OK = True
except Exception:  # noqa: BLE001
    _PYGMENTS_OK = False


# Map a small number of Pygments token kinds to QSS-agnostic colours.
# We sample mid-grey hues so the highlight reads on both light and
# dark themes; embedding apps can override via QSyntaxHighlighter
# subclassing if they want richer colours.
_TOKEN_COLOURS = {
    "keyword": "#1f6feb",
    "string": "#0a7d3b",
    "comment": "#6b6b72",
    "number": "#a3431b",
    "operator": "#6b6b72",
    "name_function": "#6e3aae",
    "name_class": "#6e3aae",
}


class _PygmentsHighlighter(QSyntaxHighlighter):
    """Cheap Pygments-driven highlighter.

    Re-tokenises on each block; for >1 MB files we disable the
    highlighter entirely (see :meth:`TextViewer.load_path`).
    """

    def __init__(self, document: QTextDocument, lexer_name: str) -> None:
        super().__init__(document)
        self._lexer = None
        if _PYGMENTS_OK:
            try:
                self._lexer = _pyg_lexers.get_lexer_by_name(lexer_name)
            except ClassNotFound:
                self._lexer = None

        self._formats: dict[str, QTextCharFormat] = {}
        for name, color in _TOKEN_COLOURS.items():
            fmt = QTextCharFormat()
            fmt.setForeground(self._color(color))
            self._formats[name] = fmt

    @staticmethod
    def _color(value: str):
        from PySide6.QtGui import QColor
        return QColor(value)

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt API)
        if self._lexer is None:
            return
        offset = 0
        try:
            tokens = list(self._lexer.get_tokens(text))
        except Exception:  # noqa: BLE001
            return
        for token_type, value in tokens:
            length = len(value)
            kind = self._map_token(token_type)
            if kind is not None:
                fmt = self._formats.get(kind)
                if fmt is not None:
                    self.setFormat(offset, length, fmt)
            offset += length

    @staticmethod
    def _map_token(token_type) -> Optional[str]:
        if not _PYGMENTS_OK:
            return None
        t = _pyg_token
        if token_type in t.Keyword:
            return "keyword"
        if token_type in t.String:
            return "string"
        if token_type in t.Comment:
            return "comment"
        if token_type in t.Number:
            return "number"
        if token_type in t.Operator:
            return "operator"
        if token_type in t.Name.Function:
            return "name_function"
        if token_type in t.Name.Class:
            return "name_class"
        return None


class TextViewer(FileViewer):
    """Monospace text preview with optional Pygments highlighting."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._editor = QPlainTextEdit(self)
        self._editor.setReadOnly(True)
        self._editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._editor.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        layout.addWidget(self._editor)
        self._highlighter: Optional[_PygmentsHighlighter] = None

    # ------------------------------------------------------------------
    def load_path(self, path: Path) -> None:
        try:
            raw = path.read_bytes()[:MAX_TEXT_BYTES + 1]
        except OSError as exc:
            self._editor.setPlainText(f"Cannot read: {exc}")
            self.load_failed.emit(path, str(exc))
            return

        truncated = len(raw) > MAX_TEXT_BYTES
        raw = raw[:MAX_TEXT_BYTES]
        text = raw.decode("utf-8", errors="replace")
        if truncated:
            text += (
                f"\n\n... (truncated to first {MAX_TEXT_BYTES:,} bytes)"
            )
        self._editor.setPlainText(text)

        # Reset existing highlighter and conditionally attach a new one.
        if self._highlighter is not None:
            self._highlighter.setDocument(None)
            self._highlighter = None
        if len(raw) <= HIGHLIGHT_BYTE_CAP:
            lexer_name = _lexer_name_for(path)
            if lexer_name and _PYGMENTS_OK:
                self._highlighter = _PygmentsHighlighter(
                    self._editor.document(), lexer_name
                )
        self.file_loaded.emit(path)

    def clear(self) -> None:
        if self._highlighter is not None:
            self._highlighter.setDocument(None)
            self._highlighter = None
        self._editor.clear()

    def max_preview_bytes(self) -> Optional[int]:
        return MAX_TEXT_BYTES


def _lexer_name_for(path: Path) -> Optional[str]:
    """Pygments lexer name based on extension; ``None`` falls back to plain."""
    ext = path.suffix.lower()
    return {
        ".py": "python",
        ".pyi": "python",
        ".sh": "bash",
        ".bat": "batch",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "ini",
        ".log": None,
        ".txt": None,
    }.get(ext)


register_viewer(ViewerSpec(
    key="text",
    label="Text",
    extensions=(
        ".txt", ".log", ".py", ".pyi", ".yaml", ".yml",
        ".toml", ".ini", ".cfg", ".sh", ".bat",
    ),
    factory=TextViewer,
    priority=8,
    description="Monospace text with optional Pygments highlighting.",
))


__all__ = [
    "HIGHLIGHT_BYTE_CAP",
    "MAX_TEXT_BYTES",
    "TextViewer",
]
