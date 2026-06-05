"""Tests for :class:`CsvViewer` — works with stdlib csv OR pandas."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QTableView

from qt_file_canvas.viewers.csv_viewer import CsvViewer


def test_load_csv_populates_model(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = CsvViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.csv")
        view = viewer.findChild(QTableView)
        assert view is not None
        model = view.model()
        assert model is not None
        # Header: name, value.  Body: 3 rows.
        assert model.columnCount() == 2
        assert model.rowCount() == 3
        # First row should have the alpha label.
        idx = model.index(0, 0)
        assert "alpha" in str(model.data(idx))
    finally:
        viewer.deleteLater()


def test_load_tsv_uses_tab_delimiter(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = CsvViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.tsv")
        view = viewer.findChild(QTableView)
        assert view is not None
        model = view.model()
        assert model is not None
        assert model.columnCount() == 2
        assert model.rowCount() == 3
    finally:
        viewer.deleteLater()


def test_clear_empties_model(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    viewer = CsvViewer()
    try:
        viewer.load_path(fixtures_dir / "tiny.csv")
        viewer.clear()
        view = viewer.findChild(QTableView)
        assert view is not None
        assert view.model() is None
    finally:
        viewer.deleteLater()
