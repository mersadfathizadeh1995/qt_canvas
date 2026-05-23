"""Tests for :class:`JsonViewer`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QPlainTextEdit,
    QStackedWidget,
    QTreeWidget,
)

from hvsr_pro.packages.qt_file_canvas.viewers.json_viewer import (
    PRETTY_PRINT_BYTES,
    JsonViewer,
)


def test_small_file_renders_as_tree(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = JsonViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.json")
        stack = viewer.findChild(QStackedWidget)
        assert stack is not None
        tree = viewer.findChild(QTreeWidget)
        assert tree is not None
        # Tree page is page 0 — the small-file rendering path.
        assert stack.currentIndex() == 0
        assert tree.topLevelItemCount() == 1
        root = tree.topLevelItem(0)
        assert root is not None
        # Top-level keys from the fixture: name, items, nested.
        labels = [root.child(i).text(0) for i in range(root.childCount())]
        assert "name" in labels
        assert "items" in labels
        assert "nested" in labels
    finally:
        viewer.deleteLater()


def test_invalid_json_falls_back_to_error_message(
    qapp: QApplication, tmp_path: Path
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json}", encoding="utf-8")
    viewer = JsonViewer()
    try:
        failures: list[tuple[Path, str]] = []
        viewer.load_failed.connect(lambda p, r: failures.append((p, r)))
        viewer.load_path(bad)
        assert len(failures) == 1
        # Stack flips to the text page with the error message.
        stack = viewer.findChild(QStackedWidget)
        assert stack is not None and stack.currentIndex() == 1
        editor = viewer.findChild(QPlainTextEdit)
        assert editor is not None
        assert "Invalid JSON" in editor.toPlainText()
    finally:
        viewer.deleteLater()


def test_large_file_uses_pretty_print_path(
    qapp: QApplication, tmp_path: Path
) -> None:
    # Build a JSON document larger than the tree-builder cap.
    big = tmp_path / "big.json"
    big.write_text(
        json.dumps([{"i": i} for i in range(1, 200_000)]),
        encoding="utf-8",
    )
    if big.stat().st_size <= PRETTY_PRINT_BYTES:
        pytest.skip("fixture below pretty-print threshold")
    viewer = JsonViewer()
    try:
        viewer.load_path(big)
        stack = viewer.findChild(QStackedWidget)
        assert stack is not None
        assert stack.currentIndex() == 1  # pretty-text page
        editor = viewer.findChild(QPlainTextEdit)
        assert editor is not None
        # Pretty-printed JSON starts with "[" and contains the indent.
        text = editor.toPlainText()
        assert text.lstrip().startswith("[")
        assert "  " in text  # indented
    finally:
        viewer.deleteLater()


def test_clear_empties_widgets(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = JsonViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.json")
        viewer.clear()
        tree = viewer.findChild(QTreeWidget)
        assert tree is not None and tree.topLevelItemCount() == 0
        editor = viewer.findChild(QPlainTextEdit)
        assert editor is not None and editor.toPlainText() == ""
    finally:
        viewer.deleteLater()
