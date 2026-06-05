"""Shared pytest fixtures for qt_file_canvas tests.

* :func:`qapp` — module-scoped headless :class:`QApplication`.
* :func:`fixtures_dir` — session-scoped directory pre-populated with
  one tiny file per built-in viewer kind.  Generated programmatically
  so the repo doesn't carry binary fixtures.
"""

from __future__ import annotations

import json as _json
import logging
import os
from pathlib import Path
from typing import Optional

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """A single headless :class:`QApplication` shared by every test."""
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="session")
def fixtures_dir(tmp_path_factory: pytest.TempPathFactory, qapp: QApplication) -> Path:
    """Materialise tiny test files for every viewer kind.

    Files actually created:

    * ``tiny.png``        — 1×1 transparent PNG via :class:`QImage`.
    * ``tiny.json``       — one nested dict.
    * ``tiny.csv``        — 3 rows × 2 cols.
    * ``tiny.tsv``        — 3 rows × 2 cols.
    * ``tiny.txt``        — 2 lines.
    * ``tiny.md``         — heading + paragraph.
    * ``tiny.bin``        — 64 random bytes (binary fallback test).
    * ``tiny.xlsx``       — only if ``openpyxl`` is importable.
    * ``tiny.pdf``        — only if a minimal PDF byte template is valid.

    The last two are tolerant: missing fixtures cause their tests to
    skip via :class:`pytest.skip` rather than fail.
    """
    out = tmp_path_factory.mktemp("qfc_fixtures")

    # --- PNG (1x1 transparent) ---------------------------------------
    img = QImage(1, 1, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    img.save(str(out / "tiny.png"), "PNG")

    # --- JSON --------------------------------------------------------
    (out / "tiny.json").write_text(
        _json.dumps(
            {"name": "qfc-test", "items": [1, 2, 3], "nested": {"a": True, "b": None}},
            indent=2,
        ),
        encoding="utf-8",
    )

    # --- CSV / TSV ---------------------------------------------------
    csv_text = "name,value\nalpha,1\nbravo,2\ncharlie,3\n"
    (out / "tiny.csv").write_text(csv_text, encoding="utf-8")
    (out / "tiny.tsv").write_text(csv_text.replace(",", "\t"), encoding="utf-8")

    # --- Text + markdown ---------------------------------------------
    (out / "tiny.txt").write_text(
        "Hello qfc.\nSecond line — used for the text viewer test.\n",
        encoding="utf-8",
    )
    (out / "tiny.md").write_text(
        "# Tiny\n\nA tiny markdown file with **bold** and `code` inline.\n",
        encoding="utf-8",
    )

    # --- Generic binary ----------------------------------------------
    (out / "tiny.bin").write_bytes(
        bytes(range(64))  # deterministic; tests assert hex offsets
    )

    # --- XLSX (openpyxl) ---------------------------------------------
    try:
        import openpyxl  # type: ignore
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["name", "value"])
        ws.append(["alpha", 1])
        ws.append(["bravo", 2])
        wb.save(str(out / "tiny.xlsx"))
    except Exception as exc:  # noqa: BLE001
        log.debug("Skipping tiny.xlsx fixture: %s", exc)

    # --- PDF (minimal valid bytes) -----------------------------------
    # Hard-coded minimal "Hello PDF" — small enough to embed and valid
    # enough for QPdfDocument to parse.  If the byte template ever
    # breaks (PySide6 update), test_viewer_pdf.py skips gracefully.
    minimal_pdf = (
        b"%PDF-1.1\n"
        b"%\xe2\xe3\xcf\xd3\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 144 144]"
        b"/Contents 4 0 R/Resources<<>>>>endobj\n"
        b"4 0 obj<</Length 44>>stream\n"
        b"BT /F1 12 Tf 36 72 Td (Hello qfc PDF) Tj ET\n"
        b"endstream endobj\n"
        b"xref\n0 5\n"
        b"0000000000 65535 f \n"
        b"0000000018 00000 n \n"
        b"0000000063 00000 n \n"
        b"0000000110 00000 n \n"
        b"0000000196 00000 n \n"
        b"trailer<</Size 5/Root 1 0 R>>\n"
        b"startxref\n284\n%%EOF\n"
    )
    (out / "tiny.pdf").write_bytes(minimal_pdf)

    return out


@pytest.fixture
def isolated_registry() -> "ViewerRegistry":  # noqa: F821
    """Fresh :class:`ViewerRegistry` for tests that mutate registration.

    Independent of :data:`DEFAULT_REGISTRY` so concurrent tests don't
    fight over keys.  The fixture re-imports the public symbols so
    consumers don't need to know the private path.
    """
    from qt_file_canvas.registry import ViewerRegistry
    return ViewerRegistry()
