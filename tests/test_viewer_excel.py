"""Tests for :class:`ExcelViewer` — skipped when openpyxl missing."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QTableView

pytest.importorskip("openpyxl")

from qt_file_canvas.viewers.excel_viewer import ExcelViewer


def test_load_xlsx_populates_model(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    xlsx = fixtures_dir / "tiny.xlsx"
    if not xlsx.is_file():
        pytest.skip("tiny.xlsx fixture not generated")
    viewer = ExcelViewer()
    try:
        viewer.load_path(xlsx)
        view = viewer.findChild(QTableView)
        assert view is not None
        model = view.model()
        assert model is not None
        # Fixture has header + 2 data rows.
        assert model.columnCount() == 2
        assert model.rowCount() == 2
    finally:
        viewer.deleteLater()


def test_sheet_picker_populated(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    xlsx = fixtures_dir / "tiny.xlsx"
    if not xlsx.is_file():
        pytest.skip("tiny.xlsx fixture not generated")
    viewer = ExcelViewer()
    try:
        viewer.load_path(xlsx)
        picker = viewer.findChild(QComboBox)
        assert picker is not None
        # The single default sheet must appear.
        assert picker.count() >= 1
    finally:
        viewer.deleteLater()


def test_clear_releases_workbook(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    xlsx = fixtures_dir / "tiny.xlsx"
    if not xlsx.is_file():
        pytest.skip("tiny.xlsx fixture not generated")
    viewer = ExcelViewer()
    try:
        viewer.load_path(xlsx)
        viewer.clear()
        view = viewer.findChild(QTableView)
        assert view is not None and view.model() is None
    finally:
        viewer.deleteLater()
