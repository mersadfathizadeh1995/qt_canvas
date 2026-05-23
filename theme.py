"""Internal theme for qt_file_canvas.

Deliberately decoupled from the embedding application's theme.  The
canvas widget inherits whatever style the host sets and only applies
its own QSS where Qt's defaults would clash (e.g. JSON tree
tightening, viewer header pill).

Consumers who want the canvas to fully match their host theme set the
QSS at the application level; this module's QSS lives at the canvas
widget scope and uses ``palette()`` introspection so colours adapt.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette


def viewer_card_qss(palette: QPalette) -> str:
    """Return a minimal QSS string scoped to the canvas widgets.

    Pulls colours from *palette* so dark themes Just Work.  Anything
    that requires a brand colour is the embedding application's job —
    the canvas stays neutral.
    """
    fg = palette.color(QPalette.WindowText).name(QColor.HexRgb)
    bg = palette.color(QPalette.Window).name(QColor.HexRgb)
    base = palette.color(QPalette.Base).name(QColor.HexRgb)
    muted = palette.color(QPalette.PlaceholderText).name(QColor.HexRgb)
    border = palette.color(QPalette.Mid).name(QColor.HexRgb)

    return f"""
QFrame#FileCanvasCard {{
    background-color: {base};
    border: 1px solid {border};
    border-radius: 6px;
}}
QLabel[role="qfc-kind-pill"] {{
    background-color: {bg};
    color: {muted};
    border: 1px solid {border};
    border-radius: 999px;
    padding: 1px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel[role="qfc-empty"] {{
    color: {muted};
    font-size: 13px;
}}
"""


__all__ = ["viewer_card_qss"]
