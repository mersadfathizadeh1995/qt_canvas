"""JSON viewer — recursive QTreeWidget with depth-1 default expansion.

Pretty-printed text fallback for files above :data:`PRETTY_PRINT_BYTES`
keeps the tree builder responsive on huge logs / dumps.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Union

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QPlainTextEdit,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..registry import ViewerSpec, register_viewer
from .base import FileViewer

#: Above this size we render the file as pretty-printed text rather
#: than a recursive tree.  Trees of >100k nodes lock up Qt on Windows.
PRETTY_PRINT_BYTES: int = 5 * 1024 * 1024  # 5 MB

#: Hard cap — anything larger falls back to the binary viewer via the
#: ``max_preview_bytes`` short-circuit in :class:`ViewerStack`.
MAX_JSON_BYTES: int = 50 * 1024 * 1024  # 50 MB

#: Default expansion depth for the tree view.  0 = roots only.
DEFAULT_EXPAND_DEPTH: int = 1


class JsonViewer(FileViewer):
    """Tree-view (small files) + pretty-text fallback (large files)."""

    _PAGE_TREE = 0
    _PAGE_TEXT = 1

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget(self)

        self._tree = QTreeWidget(self._stack)
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Key", "Value"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._stack.addWidget(self._tree)

        self._text = QPlainTextEdit(self._stack)
        self._text.setReadOnly(True)
        self._text.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._text.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self._stack.addWidget(self._text)

        layout.addWidget(self._stack)

    # ------------------------------------------------------------------
    def load_path(self, path: Path) -> None:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            self._show_error(f"Cannot read file: {exc}")
            self.load_failed.emit(path, str(exc))
            return

        size = len(raw)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._show_error(f"Invalid JSON: {exc}")
            self.load_failed.emit(path, str(exc))
            return

        if size > PRETTY_PRINT_BYTES:
            # Tree builder would lock up on huge documents.
            self._text.setPlainText(json.dumps(data, indent=2, ensure_ascii=False))
            self._stack.setCurrentIndex(self._PAGE_TEXT)
        else:
            self._build_tree(data)
            self._stack.setCurrentIndex(self._PAGE_TREE)
        self.file_loaded.emit(path)

    def clear(self) -> None:
        self._tree.clear()
        self._text.clear()

    def max_preview_bytes(self) -> Optional[int]:
        return MAX_JSON_BYTES

    # ------------------------------------------------------------------
    def _build_tree(self, data: Any) -> None:
        self._tree.clear()
        root = self._make_item("root", data)
        self._tree.addTopLevelItem(root)
        self._expand_to_depth(root, DEFAULT_EXPAND_DEPTH)
        self._tree.resizeColumnToContents(0)

    def _make_item(
        self,
        key: Union[str, int],
        value: Any,
    ) -> QTreeWidgetItem:
        if isinstance(value, dict):
            item = QTreeWidgetItem([str(key), f"{{{len(value)}}}"])
            for k, v in value.items():
                item.addChild(self._make_item(str(k), v))
        elif isinstance(value, list):
            item = QTreeWidgetItem([str(key), f"[{len(value)}]"])
            for i, v in enumerate(value):
                item.addChild(self._make_item(i, v))
        else:
            item = QTreeWidgetItem([str(key), self._format_scalar(value)])
        return item

    @staticmethod
    def _format_scalar(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _expand_to_depth(self, item: QTreeWidgetItem, depth: int) -> None:
        if depth < 0:
            return
        item.setExpanded(True)
        for i in range(item.childCount()):
            self._expand_to_depth(item.child(i), depth - 1)

    def _show_error(self, message: str) -> None:
        self._text.setPlainText(message)
        self._stack.setCurrentIndex(self._PAGE_TEXT)


register_viewer(ViewerSpec(
    key="json",
    label="JSON",
    extensions=(".json",),
    factory=JsonViewer,
    priority=10,
    description="Recursive JSON tree with pretty-print fallback for large files.",
))


__all__ = [
    "DEFAULT_EXPAND_DEPTH",
    "JsonViewer",
    "MAX_JSON_BYTES",
    "PRETTY_PRINT_BYTES",
]
