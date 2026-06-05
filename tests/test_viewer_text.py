"""Tests for :class:`TextViewer` — works with or without Pygments."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from qt_file_canvas.viewers.text import (
    MAX_TEXT_BYTES,
    TextViewer,
)


def test_load_text_renders_content(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = TextViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.txt")
        editor = viewer.findChild(QPlainTextEdit)
        assert editor is not None
        assert "Hello qfc." in editor.toPlainText()
        assert "Second line" in editor.toPlainText()
    finally:
        viewer.deleteLater()


def test_load_huge_text_truncates(
    qapp: QApplication, tmp_path: Path
) -> None:
    huge = tmp_path / "huge.txt"
    # Write a buffer just above the cap.
    huge.write_bytes(b"x" * (MAX_TEXT_BYTES + 200))
    viewer = TextViewer()
    try:
        viewer.load_path(huge)
        editor = viewer.findChild(QPlainTextEdit)
        assert editor is not None
        text = editor.toPlainText()
        assert "truncated" in text.lower()
    finally:
        viewer.deleteLater()


def test_clear_empties_editor(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = TextViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.txt")
        viewer.clear()
        editor = viewer.findChild(QPlainTextEdit)
        assert editor is not None
        assert editor.toPlainText() == ""
    finally:
        viewer.deleteLater()
