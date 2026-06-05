"""Tests for :class:`ImageViewer`."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from qt_file_canvas.viewers.image import ImageViewer


def test_load_path_sets_pixmap(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = ImageViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.png")
        label = viewer.findChild(QLabel)
        assert label is not None
        # The conftest generates a 1×1 transparent PNG; pixmap exists.
        assert label.pixmap() is not None
        assert not label.pixmap().isNull()
    finally:
        viewer.deleteLater()


def test_load_unreadable_path_emits_failure(
    qapp: QApplication, tmp_path: Path
) -> None:
    viewer = ImageViewer()
    try:
        failures: list[tuple[Path, str]] = []
        viewer.load_failed.connect(lambda p, r: failures.append((p, r)))
        bogus = tmp_path / "ghost.png"
        bogus.write_bytes(b"not actually a png")
        viewer.load_path(bogus)
        # QPixmap returns a null pixmap → viewer emits load_failed.
        assert len(failures) == 1
        assert failures[0][0] == bogus
    finally:
        viewer.deleteLater()


def test_clear_drops_pixmap(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = ImageViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.png")
        viewer.clear()
        label = viewer.findChild(QLabel)
        assert label is not None
        assert label.pixmap().isNull()
    finally:
        viewer.deleteLater()
