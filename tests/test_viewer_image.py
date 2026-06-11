"""Tests for :class:`ImageViewer` (zoomable QGraphicsView edition)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QGraphicsView

from qt_file_canvas.viewers.image import ImageViewer


def test_load_path_populates_scene(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = ImageViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.png")
        view = viewer.findChild(QGraphicsView)
        assert view is not None
        assert len(view.scene().items()) == 1
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


def test_clear_drops_scene(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = ImageViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.png")
        viewer.clear()
        view = viewer.findChild(QGraphicsView)
        assert view is not None
        assert len(view.scene().items()) == 0
    finally:
        viewer.deleteLater()


def test_zoom_controls(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    """100% sets scale 1.0; +/- step the factor; limits are clamped."""
    viewer = ImageViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.png")
        v = viewer._view
        v.set_zoom(1.0)
        assert viewer.zoom() == pytest.approx(1.0)
        v.zoom_by(1.25)
        assert viewer.zoom() == pytest.approx(1.25)
        v.zoom_by(1.0 / 1.25)
        assert viewer.zoom() == pytest.approx(1.0)
        v.set_zoom(1e9)        # clamped to the max
        assert viewer.zoom() <= 32.0
        v.set_zoom(0.0)        # clamped to the min
        assert viewer.zoom() >= 0.02
    finally:
        viewer.deleteLater()


def test_drag_mode_is_pan(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = ImageViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.png")
        assert viewer._view.dragMode() == QGraphicsView.ScrollHandDrag
    finally:
        viewer.deleteLater()
