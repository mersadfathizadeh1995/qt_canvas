"""Built-in file viewers.

Importing this package triggers self-registration of each viewer
module against :data:`qt_file_canvas.registry.DEFAULT_REGISTRY`.

Each viewer module is **import-safe** even when its optional
dependency is missing — it loads, logs at DEBUG, and silently skips
its ``register_viewer`` call.  Files of that kind then fall through
to :class:`qt_file_canvas.viewers.binary.BinaryViewer` (priority -1).
"""

from __future__ import annotations

# Order is deliberate: load the universal binary fallback first so
# every other registration error still leaves a working viewer in
# the registry.
from . import binary as _binary           # noqa: F401
from . import image as _image             # noqa: F401
from . import json_viewer as _json_v      # noqa: F401
from . import csv_viewer as _csv_v        # noqa: F401
from . import excel_viewer as _excel_v    # noqa: F401
from . import text as _text_v             # noqa: F401
from . import markdown_viewer as _md_v    # noqa: F401
from . import pdf as _pdf_v               # noqa: F401

__all__: list[str] = []
