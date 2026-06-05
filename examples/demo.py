"""Standalone demo: ``python -m qt_file_canvas.examples.demo <folder>``.

Opens a 1100x700 window with a :class:`FileCanvas` rooted at the
folder argument (defaults to the current working directory).  The
window title shows the resolved root and the active viewer label
updates as you click around.

Demo intent: prove that the package works without any of HV Pro's
infrastructure (no HubState, no Project, no QSettings).  This is also
what users get if they ``pip install qt-file-canvas`` after the
repo extraction (see ``../README.md``).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Sequence

from .. import FileCanvas


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )
    for noisy in ("matplotlib", "PIL", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="qt_file_canvas.examples.demo",
        description="Open a FileCanvas window rooted at the given folder.",
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=str(Path.cwd()),
        help="Folder to browse (defaults to CWD).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    _configure_logging()
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    root = Path(args.folder).resolve()

    os.environ.setdefault("QT_API", "pyside6")
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("qt_file_canvas demo")
    app.setStyle("Fusion")

    window = QMainWindow()
    window.setWindowTitle(f"qt_file_canvas — {root}")
    window.resize(1100, 700)

    canvas = FileCanvas(root=root)
    canvas.viewer_failed.connect(
        lambda path, reason: logging.getLogger("demo").warning(
            "Viewer failed for %s: %s", path, reason
        )
    )
    canvas.file_opened.connect(
        lambda path: logging.getLogger("demo").info("Opened: %s", path)
    )

    window.setCentralWidget(canvas)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
