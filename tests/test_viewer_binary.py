"""Tests for :class:`BinaryViewer` — the universal fallback."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from qt_file_canvas.viewers.binary import (
    HEX_DUMP_BYTES,
    BinaryViewer,
)


def test_load_path_renders_hex_dump(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = BinaryViewer()
    try:
        target = fixtures_dir / "tiny.bin"
        viewer.load_path(target)
        editor = viewer.findChild(QPlainTextEdit)
        assert editor is not None
        text = editor.toPlainText()
        # Header line carries filename and size.
        assert "tiny.bin" in text
        # Hex dump rows render bytes 0x00..0x3f from the deterministic fixture.
        assert "00000000" in text
        assert "00 01 02 03" in text
    finally:
        viewer.deleteLater()


def test_load_path_truncates_above_cap(
    qapp: QApplication, tmp_path: Path
) -> None:
    big = tmp_path / "big.bin"
    big.write_bytes(b"\x00" * (HEX_DUMP_BYTES + 200))
    viewer = BinaryViewer()
    try:
        viewer.load_path(big)
        editor = viewer.findChild(QPlainTextEdit)
        assert editor is not None
        text = editor.toPlainText()
        assert "truncated" in text.lower()
    finally:
        viewer.deleteLater()


def test_missing_file_does_not_raise(
    qapp: QApplication, tmp_path: Path
) -> None:
    viewer = BinaryViewer()
    try:
        # Should not raise — the viewer renders an explanatory message.
        viewer.load_path(tmp_path / "does-not-exist.bin")
        editor = viewer.findChild(QPlainTextEdit)
        assert editor is not None
        assert "(file not found)" in editor.toPlainText()
    finally:
        viewer.deleteLater()


def test_clear_empties_editor(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = BinaryViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.bin")
        viewer.clear()
        editor = viewer.findChild(QPlainTextEdit)
        assert editor is not None
        assert editor.toPlainText() == ""
    finally:
        viewer.deleteLater()
