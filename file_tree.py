"""File-tree widget rooted at a configurable :class:`Path`.

Wraps :class:`QFileSystemModel` + :class:`QTreeView` with the
ergonomics :class:`FileCanvas` needs:

* exposes ``path_selected(Path)`` for the single-click preview flow
  and ``path_activated(Path)`` for the open / double-click flow;
* lets callers swap roots without rebuilding the widget (the model
  is rooted in place);
* hides the secondary columns (Size, Type, Date) by default — those
  belong in the file preview's header, not the tree.

The widget is intentionally narrow.  It does not know about viewers
or the registry; :class:`FileCanvas` is the integrator.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from PySide6.QtCore import QDir, QItemSelectionModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QFileSystemModel,
    QFrame,
    QLabel,
    QSizePolicy,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


class FileTree(QFrame):
    """Rooted file tree.

    Signals
    -------
    path_selected:
        Fires with the :class:`Path` of the currently-selected node.
        Single-click; emitted on selection change.  Folders are
        elided — the canvas only previews regular files.
    path_activated:
        Fires on double-click / Enter.  Same path as
        :pysig:`path_selected` for files; for folders the canvas
        ignores this.
    root_changed:
        Fires after :meth:`set_root` finishes wiring the model.
    """

    path_selected = Signal(Path)
    path_activated = Signal(Path)
    root_changed = Signal(Path)

    def __init__(
        self,
        root: Optional[Path] = None,
        label: Optional[str] = None,
        name_filters: Optional[Iterable[str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("FileTree")
        self._root: Optional[Path] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._label = QLabel("", self)
        self._label.setProperty("role", "muted")
        self._label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(self._label)

        self._view = QTreeView(self)
        self._view.setHeaderHidden(True)
        self._view.setAlternatingRowColors(True)
        self._view.setRootIsDecorated(True)
        self._view.setExpandsOnDoubleClick(False)  # we re-route to activate
        self._view.setUniformRowHeights(True)
        layout.addWidget(self._view, 1)

        self._model = QFileSystemModel(self)
        self._model.setReadOnly(True)
        # Display every entry by default; callers can restrict via
        # ``name_filters`` / :meth:`set_name_filters`.
        self._model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)
        if name_filters:
            self._model.setNameFilters(list(name_filters))
            self._model.setNameFilterDisables(False)
        self._view.setModel(self._model)

        # Hide the auxiliary columns (Size, Type, Date) so the tree
        # reads as a clean folder list.
        for col in range(1, self._model.columnCount()):
            self._view.setColumnHidden(col, True)

        sel_model = self._view.selectionModel()
        # On startup ``setModel`` returns a brand-new selection model;
        # connect right after to avoid the first stray emit.
        sel_model.currentChanged.connect(self._on_current_changed)
        self._view.doubleClicked.connect(self._on_double_clicked)
        self._view.activated.connect(self._on_double_clicked)

        if root is not None:
            self.set_root(root, label=label)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def root(self) -> Optional[Path]:
        return self._root

    def set_root(self, root: Path, *, label: Optional[str] = None) -> None:
        """Re-root the tree at *root*.

        The model index update keeps the widget alive; only the
        :meth:`QTreeView.setRootIndex` view of the model changes.
        Missing folders are tolerated — the tree will show empty and
        the header label still updates so the user sees what was asked
        for.
        """
        root = Path(root)
        self._root = root
        # Update the underlying model root so QFileSystemModel scans
        # only this subtree.  ``setRootPath`` returns the index of the
        # new root, which we forward to the view.
        index = self._model.setRootPath(str(root))
        self._view.setRootIndex(index)
        # Header label: use *label* if provided, else "<root.name>/".
        if label is None:
            label = f"{root.name or root.anchor or str(root)}/"
        self._label.setText(label)
        self.root_changed.emit(root)

    def set_name_filters(self, filters: Optional[Iterable[str]]) -> None:
        """Update the QFileSystemModel name filters.

        ``None`` clears the filter (show everything).
        """
        if filters is None:
            self._model.setNameFilters([])
        else:
            self._model.setNameFilters(list(filters))
            self._model.setNameFilterDisables(False)

    def refresh(self) -> None:
        """Re-read the current root from disk.

        QFileSystemModel watches the filesystem with native events
        already; this is for cases where a writer doesn't fire one
        (e.g. CIFS / SMB) or after a programmatic refresh button.
        """
        if self._root is None:
            return
        # ``QFileSystemModel.refresh`` exists only via the protected
        # ``_q_directoryChanged`` slot; the public way is to swap
        # ``setRootPath`` back to itself, which re-queries.
        index = self._model.setRootPath(str(self._root))
        self._view.setRootIndex(index)

    def current_path(self) -> Optional[Path]:
        index = self._view.currentIndex()
        return self._index_to_path(index)

    def select_path(self, path: Path) -> bool:
        """Programmatically select *path* in the tree.

        Returns ``True`` on success, ``False`` if the path is not
        under the current root or QFileSystemModel hasn't indexed it
        yet (deeply nested first-time access).
        """
        index = self._model.index(str(path))
        if not index.isValid():
            return False
        sel = self._view.selectionModel()
        if sel is None:
            return False
        # PySide6 6.x exposes selection flags under the nested
        # ``SelectionFlag`` enum; the older flat-attribute form does not
        # exist on the instance.  Build the OR-ed flag explicitly.
        sel.setCurrentIndex(
            index,
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        self._view.scrollTo(index, QTreeView.ScrollHint.PositionAtCenter)
        return True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        path = self._index_to_path(current)
        if path is None:
            return
        self.path_selected.emit(path)

    def _on_double_clicked(self, index: QModelIndex) -> None:
        path = self._index_to_path(index)
        if path is None:
            return
        # Forward folder activation to the view's built-in
        # expand/collapse; the canvas ignores directory activations.
        if self._model.isDir(index):
            self._view.setExpanded(index, not self._view.isExpanded(index))
            return
        self.path_activated.emit(path)

    def _index_to_path(self, index: QModelIndex) -> Optional[Path]:
        if not index.isValid():
            return None
        return Path(self._model.filePath(index))


__all__ = ["FileTree"]
