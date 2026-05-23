"""CSV / TSV viewer — pandas if available, stdlib csv fallback otherwise.

The viewer always registers — even without pandas it shows a usable
preview using the stdlib :mod:`csv` module with a tight row cap.
"""

from __future__ import annotations

import csv as _csv
import logging
from pathlib import Path
from typing import Any, List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import QTableView, QVBoxLayout, QWidget

from ..registry import ViewerSpec, register_viewer
from .base import FileViewer

log = logging.getLogger(__name__)

#: Soft row cap when pandas is available — beyond this we slice.
PANDAS_ROW_CAP: int = 5000

#: Hard row cap when only the stdlib csv module is available.
STDLIB_ROW_CAP: int = 1000

#: Hard file-size cap; above this :class:`ViewerStack` falls back to
#: the binary viewer.
MAX_CSV_BYTES: int = 200 * 1024 * 1024  # 200 MB

try:
    import pandas as _pd  # type: ignore
    _PANDAS_OK = True
except Exception:  # noqa: BLE001
    _PANDAS_OK = False


class _CsvTableModel(QAbstractTableModel):
    """Plain QAbstractTableModel over a list-of-lists with header.

    Used by both the pandas and stdlib paths so the table view is
    identical regardless of how the data was parsed.
    """

    def __init__(
        self,
        headers: List[str],
        rows: List[List[Any]],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._headers = list(headers)
        self._rows = list(rows)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        row = self._rows[index.row()]
        col = index.column()
        if col >= len(row):
            return ""
        value = row[col]
        if value is None:
            return ""
        return str(value)

    def headerData(  # noqa: N802 (Qt API)
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ) -> Any:
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if 0 <= section < len(self._headers):
                return self._headers[section]
            return ""
        return section + 1


class CsvViewer(FileViewer):
    """CSV / TSV preview backed by ``pandas`` or stdlib ``csv``."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._view = QTableView(self)
        self._view.setAlternatingRowColors(True)
        self._view.horizontalHeader().setStretchLastSection(False)
        layout.addWidget(self._view)
        self._model: Optional[_CsvTableModel] = None

    # ------------------------------------------------------------------
    def load_path(self, path: Path) -> None:
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
        if _PANDAS_OK:
            headers, rows = self._load_with_pandas(path, delimiter)
        else:
            headers, rows = self._load_with_stdlib(path, delimiter)
        self._model = _CsvTableModel(headers, rows, self)
        self._view.setModel(self._model)
        for col in range(self._model.columnCount()):
            self._view.resizeColumnToContents(col)
        self.file_loaded.emit(path)

    def clear(self) -> None:
        self._view.setModel(None)
        self._model = None

    def max_preview_bytes(self) -> Optional[int]:
        return MAX_CSV_BYTES

    # ------------------------------------------------------------------
    @staticmethod
    def _load_with_pandas(path: Path, delimiter: str):
        try:
            df = _pd.read_csv(
                path,
                sep=delimiter,
                nrows=PANDAS_ROW_CAP,
                dtype=str,
                keep_default_na=False,
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("pandas.read_csv failed on %s: %s", path, exc)
            return CsvViewer._load_with_stdlib(path, delimiter)
        headers = [str(c) for c in df.columns]
        rows = df.values.tolist()
        return headers, rows

    @staticmethod
    def _load_with_stdlib(path: Path, delimiter: str):
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fp:
                reader = _csv.reader(fp, delimiter=delimiter)
                rows = list(reader)
        except OSError as exc:
            return [], [[f"Cannot read: {exc}"]]
        if not rows:
            return [], []
        headers = rows[0]
        body = rows[1: STDLIB_ROW_CAP + 1]
        return headers, body


register_viewer(ViewerSpec(
    key="csv",
    label="CSV",
    extensions=(".csv", ".tsv"),
    factory=CsvViewer,
    priority=10,
    description="Tabular CSV / TSV preview (pandas-backed when available).",
))


__all__ = [
    "CsvViewer",
    "MAX_CSV_BYTES",
    "PANDAS_ROW_CAP",
    "STDLIB_ROW_CAP",
]
