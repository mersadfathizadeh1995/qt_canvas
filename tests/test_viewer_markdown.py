"""Tests for :class:`MarkdownViewer`."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QTextBrowser

from hvsr_pro.packages.qt_file_canvas.viewers.markdown_viewer import (
    MarkdownViewer,
)


def test_load_markdown_renders(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = MarkdownViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.md")
        browser = viewer.findChild(QTextBrowser)
        assert browser is not None
        # toPlainText() strips markup but keeps the rendered text;
        # "Tiny" (the H1) must be present.
        plain = browser.toPlainText()
        assert "Tiny" in plain
        assert "bold" in plain
    finally:
        viewer.deleteLater()


def test_clear_empties_browser(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = MarkdownViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.md")
        viewer.clear()
        browser = viewer.findChild(QTextBrowser)
        assert browser is not None
        assert browser.toPlainText() == ""
    finally:
        viewer.deleteLater()


def test_missing_file_emits_failure(
    qapp: QApplication, tmp_path: Path
) -> None:
    viewer = MarkdownViewer()
    try:
        failures: list[tuple[Path, str]] = []
        viewer.load_failed.connect(lambda p, r: failures.append((p, r)))
        viewer.load_path(tmp_path / "ghost.md")
        assert len(failures) == 1
    finally:
        viewer.deleteLater()
