"""Tiny icon helper.

The canvas leans on :class:`QStyle.StandardPixmap` for everything it
needs (folder / file / refresh).  This module exposes one helper that
hands out the cached :class:`QIcon` from the application style — keeps
the canvas dependency-free.

If a future need for custom SVG icons emerges, drop ``.svg`` files
into ``qt_file_canvas/_assets/`` and extend :func:`icon` to fall back
to :class:`QIcon` from a resource path.  No code change in the
canvas itself.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyle

# Map of canvas-internal names → QStyle.StandardPixmap.  Kept narrow
# so style changes don't ripple through the codebase.
_STANDARD_ICONS = {
    "folder": QStyle.StandardPixmap.SP_DirIcon,
    "folder_open": QStyle.StandardPixmap.SP_DirOpenIcon,
    "file": QStyle.StandardPixmap.SP_FileIcon,
    "refresh": QStyle.StandardPixmap.SP_BrowserReload,
    "back": QStyle.StandardPixmap.SP_ArrowBack,
    "warning": QStyle.StandardPixmap.SP_MessageBoxWarning,
}


def icon(name: str) -> QIcon:
    """Return the :class:`QIcon` for *name*.

    Unknown names return an empty :class:`QIcon` (Qt handles this
    gracefully — no painted icon, no exception).
    """
    style = _style()
    if style is None:
        return QIcon()
    pixmap = _STANDARD_ICONS.get(name)
    if pixmap is None:
        return QIcon()
    return style.standardIcon(pixmap)


def _style() -> Optional[QStyle]:
    app = QApplication.instance()
    if app is None:
        return None
    return app.style()


__all__ = ["icon"]
