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

import logging
from pathlib import Path
from typing import Iterable, Optional

from PySide6.QtCore import QDir, QItemSelectionModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QFileSystemModel,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)


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
        self._reveal_target: Optional[Path] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header row: folder label (stretches) + small refresh button.
        # The refresh affordance was added by the 2026-05-23 file-list
        # diagnostic pass — without it, users on filesystems where Qt's
        # native watcher is silent (OneDrive, network mounts) had no
        # way to re-pull after dropping files into the folder.
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(4)

        self._label = QLabel("", self)
        self._label.setProperty("role", "muted")
        self._label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        header_row.addWidget(self._label, 1)

        self._refresh_btn = QToolButton(self)
        self._refresh_btn.setObjectName("FileTreeRefresh")
        self._refresh_btn.setText("\u21bb")  # ↻ U+21BB CLOCKWISE OPEN CIRCLE ARROW
        self._refresh_btn.setToolTip("Reload this folder from disk")
        self._refresh_btn.setAutoRaise(True)
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(self._refresh_btn, 0)
        layout.addLayout(header_row)

        # Tree-or-placeholder stack: the tree shows when files exist;
        # the placeholder explains why the tree is empty (folder is
        # missing, or is empty).  This is the user-visible diagnostic
        # the deferred 2026-05-23 task tracked — previously the user
        # got a blank pane with no hint about which folder was being
        # watched or whether their dropped files were even in the
        # right place.
        self._stack = QStackedWidget(self)
        layout.addWidget(self._stack, 1)

        self._view = QTreeView(self._stack)
        self._view.setHeaderHidden(True)
        self._view.setAlternatingRowColors(True)
        self._view.setRootIsDecorated(True)
        self._view.setExpandsOnDoubleClick(False)  # we re-route to activate
        self._view.setUniformRowHeights(True)
        self._stack.addWidget(self._view)

        self._placeholder = QLabel("", self._stack)
        self._placeholder.setObjectName("FileTreePlaceholder")
        self._placeholder.setProperty("role", "muted")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._placeholder.setMargin(16)
        self._placeholder.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        self._stack.addWidget(self._placeholder)

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

        # ``directoryLoaded`` fires once QFileSystemModel finishes the
        # async populate for a directory — that's when we know whether
        # the folder has any rows and can pick the tree vs placeholder.
        self._model.directoryLoaded.connect(self._on_directory_loaded)

        if root is not None:
            self.set_root(root, label=label)
        else:
            self._update_placeholder()

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
        for.  The full absolute path is logged at INFO and exposed as
        the label's tooltip so the user can confirm at a glance which
        folder the canvas is actually watching.
        """
        root = Path(root)
        self._root = root
        try:
            absolute = root.resolve(strict=False)
        except (OSError, RuntimeError):
            absolute = root.absolute()
        exists = root.exists()
        log.info(
            "FileTree: set_root(%s) [exists=%s, absolute=%s]",
            root,
            exists,
            absolute,
        )
        # Update the underlying model root so QFileSystemModel scans
        # only this subtree.  ``setRootPath`` returns the index of the
        # new root, which we forward to the view.
        index = self._model.setRootPath(str(root))
        self._view.setRootIndex(index)
        # Header label: use *label* if provided, else "<root.name>/".
        if label is None:
            label = f"{root.name or root.anchor or str(root)}/"
        self._label.setText(label)
        self._label.setToolTip(str(absolute))
        self._update_placeholder()
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
        (e.g. CIFS / SMB / OneDrive) or after a programmatic refresh
        button.  Wired to the ↻ button next to the folder label.
        """
        if self._root is None:
            return
        log.info("FileTree: manual refresh of %s", self._root)
        # ``QFileSystemModel.refresh`` exists only via the protected
        # ``_q_directoryChanged`` slot; the public way is to swap
        # ``setRootPath`` back to itself, which re-queries.
        index = self._model.setRootPath(str(self._root))
        self._view.setRootIndex(index)
        self._update_placeholder()

    def current_path(self) -> Optional[Path]:
        index = self._view.currentIndex()
        return self._index_to_path(index)

    def reveal(self, path: Path, *, collapse_others: bool = True) -> None:
        """Collapse the tree and expand the ancestor chain down to *path*.

        The "show me just this folder" gesture: collapse everything (so the
        rest of the project folds away), expand from the root down to *path*,
        then select + scroll to it.  QFileSystemModel populates each directory
        asynchronously, so when an ancestor index is not indexed yet the rest is
        retried from :meth:`_on_directory_loaded` once that directory loads.
        """
        self._reveal_target = Path(path)
        if collapse_others:
            self._view.collapseAll()
        self._apply_reveal()

    def _apply_reveal(self) -> None:
        target = getattr(self, "_reveal_target", None)
        if target is None or self._root is None:
            return
        try:
            rel = target.resolve(strict=False).relative_to(
                Path(self._root).resolve(strict=False))
        except (ValueError, OSError):
            self._reveal_target = None
            return
        cur = Path(self._root)
        for part in rel.parts:
            cur = cur / part
            idx = self._model.index(str(cur))
            if not idx.isValid():
                return                       # not indexed yet -> wait for load
            self._view.expand(idx)
        if self.select_path(target):
            self._reveal_target = None       # fully revealed

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

    # ------------------------------------------------------------------
    # Empty-state placeholder (2026-05-23 file-list diagnostic)
    # ------------------------------------------------------------------
    def _on_directory_loaded(self, path: str) -> None:
        """QFileSystemModel finished populating *path* — refresh state.

        The model loads each directory asynchronously; this slot is
        the only reliable hook for "I now know how many rows live
        under this folder".  We re-evaluate the placeholder whenever
        the loaded path matches our current root.
        """
        if self._root is None:
            return
        try:
            same = Path(path) == self._root or Path(path) == self._root.absolute()
        except (OSError, ValueError):
            same = False
        if same:
            self._update_placeholder()
        # a directory finished loading -> continue any pending reveal that was
        # waiting on this (or a deeper) directory to be indexed.
        if getattr(self, "_reveal_target", None) is not None:
            self._apply_reveal()

    def _update_placeholder(self) -> None:
        """Show the tree or the empty/missing placeholder as appropriate.

        Three states:

        * **No root set** — show the tree (default empty model).
        * **Root does not exist** — show ``Folder doesn't exist yet``
          placeholder with the absolute path so the user can create
          it or correct the path mismatch.
        * **Root exists but has zero indexed rows** — show ``Folder
          is empty`` placeholder with a hint to drop files and click
          ↻.  This is the common diagnostic case.
        * **Root exists and has rows** — show the tree.
        """
        root = self._root
        if root is None:
            self._stack.setCurrentWidget(self._view)
            return

        try:
            absolute = root.resolve(strict=False)
        except (OSError, RuntimeError):
            absolute = root.absolute()

        if not root.exists():
            self._placeholder.setText(
                "Folder does not exist yet:\n"
                f"{absolute}\n\n"
                "Create the folder on disk, then click \u21bb to reload."
            )
            self._stack.setCurrentWidget(self._placeholder)
            return

        # Folder exists; check how many rows the model has indexed
        # under it.  ``QFileSystemModel`` populates asynchronously,
        # so during the very first paint the count may be 0 even
        # when files exist on disk — we get a second chance via
        # ``_on_directory_loaded`` once the populate completes.
        root_idx = self._model.index(str(root))
        if root_idx.isValid() and self._model.rowCount(root_idx) > 0:
            self._stack.setCurrentWidget(self._view)
            return

        self._placeholder.setText(
            "No files in this folder yet:\n"
            f"{absolute}\n\n"
            "Drop files into this folder, then click \u21bb to reload."
        )
        self._stack.setCurrentWidget(self._placeholder)


__all__ = ["FileTree"]
