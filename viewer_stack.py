"""Viewer stack — caches one viewer per :class:`ViewerSpec.key`.

Resolves a path through :class:`ViewerRegistry`, instantiates the
matching :class:`FileViewer` on first use, and routes
:meth:`FileViewer.load_path` exceptions to a fallback so the canvas
never goes blank.

The fallback is the spec with key ``"binary"`` from the registry
(the universal viewer that always claims any path).  If the registry
has no ``"binary"`` spec, the stack shows a plain "Cannot preview"
message label instead — extra defensive but cheap.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QStackedWidget,
    QWidget,
)

from .registry import DEFAULT_REGISTRY, ViewerRegistry, ViewerSpec
from .viewers.base import FileViewer

log = logging.getLogger(__name__)

#: Placeholder key for the "no file selected" page.  Lives in the
#: stack at index 0 so it's the default visible page on construction.
_EMPTY_KEY = "__qfc_empty__"

#: Placeholder key for the "cannot preview" fallback label, used only
#: when the registry has no binary viewer (unusual: only happens if a
#: consumer aggressively unregisters defaults).
_NO_FALLBACK_KEY = "__qfc_no_fallback__"


class ViewerStack(QStackedWidget):
    """Cache of viewer instances driven by the registry.

    Signals
    -------
    viewer_failed:
        Emitted with ``(path, error_message)`` whenever a viewer's
        :meth:`load_path` raised.  The stack then falls back to the
        binary viewer for the same file.
    file_loaded:
        Emitted with the :class:`Path` after a successful load.
    """

    viewer_failed = Signal(Path, str)
    file_loaded = Signal(Path)

    def __init__(
        self,
        registry: ViewerRegistry = DEFAULT_REGISTRY,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._registry = registry
        self._viewers: Dict[str, FileViewer] = {}
        self._current_path: Optional[Path] = None

        # Pre-create the placeholder "no file selected" page.
        from PySide6.QtCore import Qt  # localised — keeps top-level imports tidy
        self._empty_page = QLabel(
            "Select a file from the tree to preview it.", self
        )
        self._empty_page.setProperty("role", "qfc-empty")
        self._empty_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_index_by_key: Dict[str, int] = {}
        self._page_index_by_key[_EMPTY_KEY] = self.addWidget(self._empty_page)
        self.setCurrentIndex(self._page_index_by_key[_EMPTY_KEY])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def registry(self) -> ViewerRegistry:
        return self._registry

    def current_path(self) -> Optional[Path]:
        """Return the path most recently passed to :meth:`load_path`."""
        return self._current_path

    def show_empty(self) -> None:
        """Show the placeholder page (no file selected)."""
        self._current_path = None
        self.setCurrentIndex(self._page_index_by_key[_EMPTY_KEY])

    def load_path(self, path: Path) -> None:
        """Render *path* in the matching viewer.

        Resolution:

        1. Look up the matching :class:`ViewerSpec` via the registry.
        2. If the viewer declares :meth:`FileViewer.max_preview_bytes`
           and the file exceeds it, short-circuit to the binary
           viewer.
        3. Reuse cached :class:`FileViewer` instance for the spec's
           key, or instantiate via :attr:`ViewerSpec.factory`.
        4. Call :meth:`FileViewer.load_path`; on exception emit
           :pysig:`viewer_failed` and fall back to binary.
        """
        path = Path(path)
        self._current_path = path
        spec = self._registry.lookup(path)
        if spec is None:
            self._show_no_fallback_message(path, "No viewer matches this file.")
            return

        # Honour per-viewer size caps.  Instantiating to ask for the
        # cap is slightly wasteful — but viewer ctors are deliberately
        # cheap, and we'd cache the instance anyway.
        viewer = self._get_or_create_viewer(spec)
        cap = viewer.max_preview_bytes()
        if cap is not None and self._file_size(path) > cap and spec.key != "binary":
            log.debug(
                "File %s (%d bytes) exceeds %s cap %d — using binary fallback",
                path, self._file_size(path), spec.key, cap,
            )
            self._render_with_fallback(path, "size cap exceeded")
            return

        try:
            viewer.clear()
            viewer.load_path(path)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "Viewer %s failed on %s: %s", spec.key, path, exc, exc_info=True
            )
            self.viewer_failed.emit(path, str(exc))
            self._render_with_fallback(path, f"{spec.key} viewer failed: {exc}")
            return

        self.setCurrentIndex(self._page_index_by_key[spec.key])
        self.file_loaded.emit(path)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _get_or_create_viewer(self, spec: ViewerSpec) -> FileViewer:
        viewer = self._viewers.get(spec.key)
        if viewer is not None:
            return viewer
        try:
            viewer = spec.factory()
        except Exception as exc:  # noqa: BLE001
            log.warning("Viewer factory for %s raised: %s", spec.key, exc)
            # Surface as a viewer_failed and surface the no-fallback
            # placeholder; we don't try a binary fallback here because
            # we'd recurse indefinitely if the binary spec is the one
            # that failed.
            self._show_no_fallback_message(
                self._current_path or Path("."),
                f"Could not instantiate {spec.key} viewer: {exc}",
            )
            raise
        # Parent the new viewer to the stack so Qt manages its
        # lifetime; ``addWidget`` returns the stack index.
        index = self.addWidget(viewer)
        self._page_index_by_key[spec.key] = index
        self._viewers[spec.key] = viewer
        return viewer

    def _render_with_fallback(self, path: Path, reason: str) -> None:
        # Look up the binary spec specifically by key.  This is the
        # registered universal fallback (priority=-1, can_view=True).
        fallback_spec: Optional[ViewerSpec] = None
        for spec in self._registry.all():
            if spec.key == "binary":
                fallback_spec = spec
                break
        if fallback_spec is None:
            self._show_no_fallback_message(path, reason)
            return
        try:
            viewer = self._get_or_create_viewer(fallback_spec)
            viewer.clear()
            viewer.load_path(path)
            self.setCurrentIndex(self._page_index_by_key[fallback_spec.key])
        except Exception as exc:  # noqa: BLE001
            log.error("Binary fallback failed for %s: %s", path, exc, exc_info=True)
            self._show_no_fallback_message(path, str(exc))

    def _show_no_fallback_message(self, path: Path, reason: str) -> None:
        # Lazily build the no-fallback page; uncommon path so we don't
        # need it eagerly.
        key = _NO_FALLBACK_KEY
        if key not in self._page_index_by_key:
            label = QLabel(self)
            label.setProperty("role", "qfc-empty")
            from PySide6.QtCore import Qt
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._page_index_by_key[key] = self.addWidget(label)
        page = self.widget(self._page_index_by_key[key])
        if isinstance(page, QLabel):
            page.setText(f"Cannot preview {path.name}\n\n{reason}")
        self.setCurrentIndex(self._page_index_by_key[key])

    @staticmethod
    def _file_size(path: Path) -> int:
        try:
            return path.stat().st_size if path.is_file() else 0
        except OSError:
            return 0


__all__ = ["ViewerStack"]
