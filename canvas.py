"""Composite :class:`FileCanvas` — tree + viewer stack with QSplitter.

The single public widget consumers embed.  Internally:

* Left :class:`FileTree` listens for selection / activation.
* Right :class:`ViewerStack` renders the matching viewer.
* :class:`QSplitter` lets the user resize the split; state is
  serialisable via :meth:`splitter_state` for QSettings round-trip.

Signal contract (re-emitted from the inner widgets):

* :pysig:`file_selected(Path)` — single-click in the tree.
* :pysig:`file_opened(Path)`   — double-click / Enter in the tree
                                 *or* a successful programmatic
                                 :meth:`open_path` call.
* :pysig:`viewer_failed(Path, str)` — a viewer raised; the binary
                                      fallback is showing instead.
* :pysig:`root_changed(Path)`  — :meth:`set_root` finished.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSplitter,
    QWidget,
)

from .file_tree import FileTree
from .registry import DEFAULT_REGISTRY, ViewerRegistry
from .viewer_stack import ViewerStack


class FileCanvas(QFrame):
    """File explorer + multi-format preview composite.

    Construction parameters mirror the Phase-5a public API documented
    in the plan.  Every parameter has a sensible default so the most
    common call is just ``FileCanvas(root=path)``.
    """

    file_selected = Signal(Path)
    file_opened = Signal(Path)
    viewer_failed = Signal(Path, str)
    root_changed = Signal(Path)

    def __init__(
        self,
        root: Optional[Path] = None,
        *,
        label: Optional[str] = None,
        registry: ViewerRegistry = DEFAULT_REGISTRY,
        show_tree: bool = True,
        tree_filters: Optional[Iterable[str]] = None,
        initial_path: Optional[Path] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("FileCanvasCard")
        self.setProperty("role", "card")
        # Phase-7 UX hotfix: the canvas no longer calls
        # ``self.setStyleSheet(...)``.  Qt scopes a widget's stylesheet
        # to its entire subtree, which meant the host application's QSS
        # (e.g. HV Hub's ``QTreeView``/``QPlainTextEdit`` rules) was
        # masked off and the inner widgets fell back to system theme
        # colours — black backgrounds under Windows dark mode.  The
        # canvas now relies on:
        #   * the host's ``role="card"`` QSS for the outer frame, and
        #   * the host's QPalette (set globally via ``apply_theme``)
        #     for inner widget colours.
        # The standalone demo (``examples/demo.py``) calls Qt's default
        # Fusion style and inherits the system palette, which works on
        # both light- and dark-mode machines.

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Horizontal, self)
        self._splitter.setChildrenCollapsible(False)
        layout.addWidget(self._splitter)

        self._tree = FileTree(
            root=root, label=label, name_filters=tree_filters, parent=self._splitter
        )
        self._viewer_stack = ViewerStack(registry=registry, parent=self._splitter)
        self._splitter.addWidget(self._tree)
        self._splitter.addWidget(self._viewer_stack)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 3)
        self._splitter.setSizes([200, 600])

        # Wire signals.
        self._tree.path_selected.connect(self._on_path_selected)
        self._tree.path_activated.connect(self._on_path_activated)
        self._tree.root_changed.connect(self.root_changed)
        self._viewer_stack.viewer_failed.connect(self.viewer_failed)

        if not show_tree:
            self.set_show_tree(False)

        if initial_path is not None:
            self.open_path(initial_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def tree(self) -> FileTree:
        return self._tree

    @property
    def viewer_stack(self) -> ViewerStack:
        return self._viewer_stack

    @property
    def splitter(self) -> QSplitter:
        return self._splitter

    def set_root(self, root: Path, *, label: Optional[str] = None) -> None:
        """Re-root the canvas at *root*.

        Clears the current preview and goes back to the empty
        placeholder so the user sees an unambiguous "new context" state.
        """
        self._viewer_stack.show_empty()
        self._tree.set_root(root, label=label)

    def open_path(self, path: Path) -> None:
        """Programmatically select *path* and preview it.

        Equivalent to a user double-clicking the row in the tree.
        Emits :pysig:`file_opened` on success.  If *path* is outside
        the current root, the tree won't be able to highlight it but
        the preview still loads — this matches the "deep link from
        another widget" use case.
        """
        path = Path(path)
        selected = self._tree.select_path(path)
        if path.is_file():
            self._viewer_stack.load_path(path)
            self.file_opened.emit(path)
        elif not selected:
            # Path doesn't exist or is unreachable; fall back to empty.
            self._viewer_stack.show_empty()

    def reveal(self, path: Path, *, collapse_others: bool = True) -> None:
        """Collapse the tree and expand down to *path* (a folder or file).

        The "focus this folder" gesture used by hosts that drive the tree from
        an external selector (e.g. a per-shot navigator).  Delegates to
        :meth:`FileTree.reveal`.
        """
        self._tree.reveal(Path(path), collapse_others=collapse_others)

    def refresh(self) -> None:
        """Re-read the current root from disk + reload the current file."""
        self._tree.refresh()
        cur = self._viewer_stack.current_path()
        if cur is not None and cur.is_file():
            self._viewer_stack.load_path(cur)

    def current_path(self) -> Optional[Path]:
        return self._viewer_stack.current_path()

    def set_show_tree(self, visible: bool) -> None:
        """Toggle the left tree pane.  Splitter sizes are preserved."""
        self._tree.setVisible(visible)

    # ------------------------------------------------------------------
    # QSettings round-trip helpers
    # ------------------------------------------------------------------
    def splitter_state(self) -> bytes:
        """Return the :class:`QSplitter` state for persistence."""
        return bytes(self._splitter.saveState())

    def restore_splitter_state(self, state: bytes) -> None:
        """Restore the splitter sizes from :meth:`splitter_state` output.

        Silently no-ops on a malformed payload — :class:`QSplitter`
        already returns ``False`` in that case.
        """
        if not state:
            return
        from PySide6.QtCore import QByteArray
        self._splitter.restoreState(QByteArray(state))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _on_path_selected(self, path: Path) -> None:
        # Folders fire selection events too; only preview files.
        if not path.is_file():
            return
        self._viewer_stack.load_path(path)
        self.file_selected.emit(path)

    def _on_path_activated(self, path: Path) -> None:
        if not path.is_file():
            return
        # Activation implies the user pressed Enter / double-clicked.
        # The tree already triggered a selection-change so the
        # viewer is up-to-date; we just announce the activation here.
        self.file_opened.emit(path)


__all__ = ["FileCanvas"]
