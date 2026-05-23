"""Tests for :class:`PdfViewer` — skipped when QtPdf missing."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

pytest.importorskip("PySide6.QtPdf")
pytest.importorskip("PySide6.QtPdfWidgets")

from hvsr_pro.packages.qt_file_canvas.viewers.pdf import PdfViewer


def test_load_pdf_does_not_raise(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    pdf = fixtures_dir / "tiny.pdf"
    if not pdf.is_file():
        pytest.skip("tiny.pdf fixture not generated")
    viewer = PdfViewer()
    try:
        # The minimal hand-rolled PDF in the fixture may or may not
        # satisfy QPdfDocument's strict parser; either way we just
        # need the viewer not to crash.  If load fails we expect a
        # load_failed emission rather than an exception.
        failures: list[tuple[Path, str]] = []
        viewer.load_failed.connect(lambda p, r: failures.append((p, r)))
        viewer.load_path(pdf)
        # Either it loaded fine (no failures) or it failed gracefully.
        assert len(failures) in (0, 1)
    finally:
        viewer.deleteLater()


def test_clear_closes_document(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    pdf = fixtures_dir / "tiny.pdf"
    if not pdf.is_file():
        pytest.skip("tiny.pdf fixture not generated")
    viewer = PdfViewer()
    try:
        viewer.load_path(pdf)
        viewer.clear()  # must not raise
    finally:
        viewer.deleteLater()
