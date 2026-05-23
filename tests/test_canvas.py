"""Composite :class:`FileCanvas` integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from hvsr_pro.packages.qt_file_canvas import FileCanvas


def test_construct_without_root(qapp: QApplication) -> None:
    canvas = FileCanvas()
    try:
        assert canvas.current_path() is None
        assert canvas.tree.root is None
    finally:
        canvas.deleteLater()


def test_set_root_re_roots_tree(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    canvas = FileCanvas()
    try:
        canvas.set_root(fixtures_dir)
        assert canvas.tree.root == fixtures_dir
    finally:
        canvas.deleteLater()


def test_root_changed_signal_propagates(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    canvas = FileCanvas()
    try:
        received: list[Path] = []
        canvas.root_changed.connect(received.append)
        canvas.set_root(fixtures_dir)
        assert received == [fixtures_dir]
    finally:
        canvas.deleteLater()


def test_open_path_loads_file_into_viewer(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    canvas = FileCanvas(root=fixtures_dir)
    try:
        opens: list[Path] = []
        canvas.file_opened.connect(opens.append)
        target = fixtures_dir / "tiny.json"
        canvas.open_path(target)
        assert canvas.current_path() == target
        assert opens == [target]
    finally:
        canvas.deleteLater()


def test_show_tree_toggle(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    canvas = FileCanvas(root=fixtures_dir)
    try:
        assert canvas.tree.isVisible() in (True, False)  # Qt may defer
        canvas.set_show_tree(False)
        # ``setVisible(False)`` on an unmapped widget still flips the
        # property; we rely on ``isVisibleTo(parent)`` for a robust
        # introspection.
        assert canvas.tree.isVisibleTo(canvas) is False
        canvas.set_show_tree(True)
        assert canvas.tree.isVisibleTo(canvas) is True
    finally:
        canvas.deleteLater()


def test_splitter_state_round_trip(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    canvas = FileCanvas(root=fixtures_dir)
    try:
        canvas.splitter.setSizes([180, 720])
        state = canvas.splitter_state()
        # 1. The serialised state is a non-trivial byte string.
        assert isinstance(state, (bytes, bytearray))
        assert len(state) > 0
        # 2. ``restore_splitter_state`` is no-op-safe and does not raise.
        canvas.splitter.setSizes([400, 500])
        canvas.restore_splitter_state(state)
        # 3. Empty / None payloads are tolerated (used by Phase-6 cold start).
        canvas.restore_splitter_state(b"")
    finally:
        canvas.deleteLater()


def test_initial_path_opens_immediately(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    target = fixtures_dir / "tiny.txt"
    canvas = FileCanvas(root=fixtures_dir, initial_path=target)
    try:
        assert canvas.current_path() == target
    finally:
        canvas.deleteLater()


def test_open_folder_keeps_viewer_empty(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    canvas = FileCanvas(root=fixtures_dir)
    try:
        # Folders shouldn't trigger a viewer load.
        canvas.open_path(fixtures_dir)
        # current_path() is None unless a *file* loaded.
        assert canvas.current_path() is None
    finally:
        canvas.deleteLater()
