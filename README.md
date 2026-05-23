# qt_file_canvas

Embeddable Qt file tree + multi-format viewer canvas with a plugin
registry. Built on PySide6.  Optional heavy dependencies
(`pandas`, `openpyxl`, `Pygments`) are loaded lazily; a missing dep
degrades that one file kind to the binary fallback — the rest of the
canvas keeps working.

Currently lives in-tree under `hvsr_pro/packages/qt_file_canvas/` as
a sibling of `hv_hub`.  Designed for `git subtree split` extraction
to its own repo (`qt-file-canvas` on PyPI) once it stabilises.

## Quick start

```python
from pathlib import Path
from qt_file_canvas import FileCanvas

canvas = FileCanvas(
    root=Path("D:/Projects/MySite"),
    label="MySite/",
    show_tree=True,
)
canvas.file_opened.connect(lambda p: print(f"opened {p}"))
canvas.show()
```

## Built-in viewers

| Key | Extensions | Dep | Notes |
|---|---|---|---|
| `image` | `.png .jpg .jpeg .gif .bmp .webp .tif .tiff` | stdlib Qt | Scrollable; downscaled if wider than 1200 px |
| `json` | `.json` | stdlib | Recursive `QTreeWidget`; pretty-print fallback at 5 MB |
| `csv` | `.csv .tsv` | `pandas` (optional) | 5 000-row cap with pandas; 1 000-row cap on stdlib fallback |
| `excel` | `.xlsx .xlsm` | `openpyxl` | Read-only; sheet picker; 5 000-row × 200-col cap |
| `text` | `.txt .log .py .yaml .toml .ini .sh .bat` | stdlib + optional `Pygments` | Highlighting up to 1 MB; plain monospace beyond |
| `markdown` | `.md .markdown` | stdlib Qt (≥ 5.14) | `QTextBrowser.setMarkdown` |
| `pdf` | `.pdf` | `PySide6.QtPdf` (optional) | Multi-page scroll; falls back to binary if QtPdf missing |
| `binary` | `*` | stdlib | Universal fallback: hex dump of first 4 KB |

Files of any extension fall through to the binary viewer when no
spec matches.  Files larger than a viewer's `max_preview_bytes()`
cap also fall through automatically.

## Adding a new viewer

Two lines from any consumer:

```python
from qt_file_canvas import register_viewer, ViewerSpec, FileViewer

class DxfViewer(FileViewer):
    def load_path(self, path):
        ...

register_viewer(ViewerSpec(
    key="dxf",
    label="DXF",
    extensions=(".dxf",),
    factory=DxfViewer,
))
```

For an isolated registry (e.g. different consumer, different file
kinds), pass a private `ViewerRegistry()` to `FileCanvas`:

```python
from qt_file_canvas import FileCanvas, ViewerRegistry

private_registry = ViewerRegistry()
private_registry.register(ViewerSpec(...))
canvas = FileCanvas(root=path, registry=private_registry)
```

## API surface

```python
from qt_file_canvas import (
    FileCanvas,
    FileTree,
    ViewerStack,
    FileViewer,
    ViewerSpec,
    ViewerRegistry,
    DEFAULT_REGISTRY,
    register_viewer,
    unregister_viewer,
)
```

### `FileCanvas`

```python
canvas = FileCanvas(
    root=Path("D:/Projects/Pro3"),
    label="Pro3/",                        # defaults to root.name + "/"
    registry=DEFAULT_REGISTRY,
    show_tree=True,
    tree_filters=("*.json", "*.png"),     # name filter; None → no filter
    initial_path=None,
    parent=None,
)

# Imperative API
canvas.set_root(path, label=None)         # tears down + rebuilds the tree
canvas.open_path(path)                    # selects + previews; emits file_opened
canvas.refresh()                          # re-read disk; preserves selection
canvas.current_path()                     # -> Path | None
canvas.set_show_tree(visible)
canvas.splitter_state()                   # -> bytes; for QSettings round-trip
canvas.restore_splitter_state(state)

# Signals
canvas.file_selected   # Signal(Path)         single click in tree
canvas.file_opened     # Signal(Path)         double click / Enter
canvas.viewer_failed   # Signal(Path, str)    viewer raised; payload = error message
canvas.root_changed    # Signal(Path)
```

### `ViewerSpec`

```python
@dataclass(frozen=True)
class ViewerSpec:
    key: str
    label: str
    extensions: tuple[str, ...]
    factory: Callable[[], FileViewer]
    can_view: Callable[[Path], bool] | None = None
    priority: int = 0
    description: str = ""
```

### `ViewerRegistry`

```python
class ViewerRegistry:
    def register(self, spec): ...     # raises on key collision
    def replace(self, spec): ...      # idempotent override
    def unregister(self, key): ...
    def lookup(self, path): ...       # -> ViewerSpec | None
    def all(self): ...                # -> list[ViewerSpec] (priority-desc)
```

## Run the demo

```bash
python -m hvsr_pro.packages.qt_file_canvas.examples.demo D:/Some/Folder
```

Opens a 1100x700 window with the canvas rooted at the given folder.
Logs viewer failures and successful opens to stdout.

## Repo extraction

When the package is ready to leave the monorepo:

```bash
git subtree split --prefix=hvsr_pro/packages/qt_file_canvas -b qt-file-canvas-split
git push <new-remote> qt-file-canvas-split:main
```

After extraction, the only change in consumers is `requirements.txt`
(`qt-file-canvas>=0.1`).  The `from qt_file_canvas import FileCanvas`
line stays unchanged because the PyPI distribution name
(`qt-file-canvas`) maps cleanly to the import name (`qt_file_canvas`).
The `pyproject.toml` template lives next to this README and is ready
to use after the split — just bump the version and add the project
URL.

## Tests

```bash
QT_QPA_PLATFORM=offscreen pytest hvsr_pro/packages/qt_file_canvas/tests -q
```

Tests skip viewer modules whose optional dependency is missing
(`csv` without pandas, `excel` without openpyxl, `pdf` without QtPdf,
`text` highlighting without Pygments) — the binary fallback test
always runs.

## Independence guarantee

The package imports nothing from the rest of HV Pro:

```bash
grep -R "hv_hub\|gui_v2\|project_manager\|hv_studio" \
     hvsr_pro/packages/qt_file_canvas
# (empty)
```

This is enforced by the Phase 5a CI grep gate.
