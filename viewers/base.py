"""Abstract base for file viewers.

Every viewer plugin is a :class:`QWidget` subclass that knows how to
render *one* kind of file (image, csv, json, ...).  The lifetime
contract is:

* :class:`ViewerStack` instantiates **one** viewer per
  :attr:`ViewerSpec.key` and caches it.
* :meth:`load_path` is called every time the user selects a file of
  this kind.  Subclasses must reset any previous state and render the
  new file synchronously.
* :meth:`clear` is invoked before :meth:`load_path` (and on a
  no-selection event) so the viewer can release large buffers.
* Exceptions from :meth:`load_path` are caught by the stack, which
  emits :pysig:`viewer_failed` on the parent :class:`FileCanvas` and
  falls back to the binary viewer.  Subclasses should let unexpected
  errors propagate; do not swallow them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget


class FileViewer(QWidget):
    """Abstract base class for viewer plugins.

    Subclasses **must** override :meth:`load_path`.  Everything else
    has a sensible default.

    Signals
    -------
    file_loaded:
        Emitted with the :class:`Path` argument from :meth:`load_path`
        once the viewer has rendered the file successfully.  Optional
        for subclasses; :class:`ViewerStack` does not require it.
    load_failed:
        Emitted with ``(path, error_message)`` when the viewer caught
        a recoverable error.  Subclasses that catch exceptions
        themselves (e.g. text viewer falling back to bytes) emit this
        instead of raising.
    """

    file_loaded = Signal(Path)
    load_failed = Signal(Path, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

    # ------------------------------------------------------------------
    # Required override
    # ------------------------------------------------------------------
    def load_path(self, path: Path) -> None:
        """Render *path*.  Subclasses **must** override.

        Implementations should:

        1. Reset previous state (call :meth:`clear` if convenient).
        2. Read the file and populate the viewer's widgets.
        3. Emit :pysig:`file_loaded` on success (optional).
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must override load_path()"
        )

    # ------------------------------------------------------------------
    # Optional overrides
    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Reset viewer state.  Default is no-op.

        Override when the viewer holds large buffers (e.g. an open
        PDF document, a pandas DataFrame, a QPixmap).  :class:`ViewerStack`
        does *not* call this automatically; the embedding canvas does
        on root change and on viewer-failure fallback.
        """
        return None

    def max_preview_bytes(self) -> Optional[int]:
        """Return a per-viewer size cap, in bytes; ``None`` means no cap.

        :class:`ViewerStack` reads this **before** calling
        :meth:`load_path` and short-circuits to the binary viewer
        when the file exceeds the cap.  Use this to keep heavy
        viewers (pdf, excel) from melting the UI on accidentally
        huge files.
        """
        return None


__all__ = ["FileViewer"]
