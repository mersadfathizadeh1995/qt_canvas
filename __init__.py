"""qt_file_canvas — embeddable Qt file tree + multi-format viewer canvas.

Independent, reusable Qt component.  Talks ``pathlib.Path`` only —
zero knowledge of any host application's domain.  The single
:class:`FileCanvas` widget composes a :class:`FileTree` and a
:class:`ViewerStack` driven by a plugin :class:`ViewerRegistry`.

Quick start::

    from pathlib import Path
    from qt_file_canvas import FileCanvas

    canvas = FileCanvas(root=Path("D:/Projects/MySite"))
    canvas.show()

The package self-registers eight built-in viewers (image, json, csv,
excel, text, markdown, pdf, binary fallback) on import.  Adding a new
kind from any consumer is two lines — see :func:`register_viewer`.

Extraction recipe — see ``README.md`` for the full ``git subtree split``
workflow.  After extraction the import path stays
``from qt_file_canvas import FileCanvas`` because the distribution
name (``qt-file-canvas``) maps cleanly to the import name.
"""

from __future__ import annotations

# Public surface — keep these in one block; the order doesn't matter to
# Python but it makes the package's API obvious at a glance.
from .canvas import FileCanvas
from .file_tree import FileTree
from .registry import (
    DEFAULT_REGISTRY,
    ViewerRegistry,
    ViewerSpec,
    register_viewer,
    unregister_viewer,
)
from .viewer_stack import ViewerStack
from .viewers.base import FileViewer

# Import the viewer modules so they self-register against the default
# registry.  Each module is import-safe even when its heavy
# dependency (pandas, openpyxl, PyMuPDF / QtPdf, Pygments) is missing:
# the module loads, logs at DEBUG, and simply skips its
# ``register_viewer`` call.  Files of that kind fall through to the
# :class:`BinaryViewer` fallback (priority -1).
from . import viewers as _viewers  # noqa: F401  (side-effect: registration)

__all__ = [
    "DEFAULT_REGISTRY",
    "FileCanvas",
    "FileTree",
    "FileViewer",
    "ViewerRegistry",
    "ViewerSpec",
    "ViewerStack",
    "register_viewer",
    "unregister_viewer",
]

__version__ = "0.1.0"
