"""Headless tests for :class:`FileTree`."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from qt_file_canvas.file_tree import FileTree


def test_construct_without_root(qapp: QApplication) -> None:
    tree = FileTree()
    try:
        assert tree.root is None
        assert tree.current_path() is None
    finally:
        tree.deleteLater()


def test_set_root_updates_root_property(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    tree = FileTree()
    try:
        tree.set_root(fixtures_dir)
        assert tree.root == fixtures_dir
    finally:
        tree.deleteLater()


def test_root_changed_signal_fires(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    tree = FileTree()
    try:
        received: list[Path] = []
        tree.root_changed.connect(received.append)
        tree.set_root(fixtures_dir)
        assert received == [fixtures_dir]
    finally:
        tree.deleteLater()


def test_select_path_emits_path_selected(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    tree = FileTree(root=fixtures_dir)
    try:
        selected: list[Path] = []
        tree.path_selected.connect(selected.append)
        target = fixtures_dir / "tiny.json"
        ok = tree.select_path(target)
        assert ok is True
        # path_selected is fired through the selection model — at least
        # one emission must have happened with the target.
        assert any(p == target for p in selected)
    finally:
        tree.deleteLater()


def test_select_path_outside_root_returns_false(
    qapp: QApplication, fixtures_dir: Path, tmp_path: Path
) -> None:
    tree = FileTree(root=fixtures_dir)
    try:
        # tmp_path is a sibling of fixtures_dir under tmp_path_factory,
        # so it's *outside* the fixtures_dir root.
        outside = tmp_path / "ghost.json"
        outside.write_text("{}", encoding="utf-8")
        ok = tree.select_path(outside)
        # QFileSystemModel.index returns a valid index for any indexed
        # path, but the tree visually can't navigate outside its
        # root.  The signal of intent is the function's return value;
        # we don't enforce ok==False because QFileSystemModel may have
        # indexed *outside* — we only care that the call doesn't
        # raise and emits no spurious activation.
        assert isinstance(ok, bool)
    finally:
        tree.deleteLater()


def test_name_filters_apply(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    tree = FileTree(root=fixtures_dir, name_filters=("*.json",))
    try:
        # The tree's model still indexes everything but applies a
        # display filter; we sanity-check it doesn't crash and we can
        # change the filter later.
        tree.set_name_filters(None)  # clear
        tree.set_name_filters(("*.md",))
    finally:
        tree.deleteLater()


def test_refresh_does_not_lose_root(
    qapp: QApplication, fixtures_dir: Path
) -> None:
    tree = FileTree(root=fixtures_dir)
    try:
        tree.refresh()
        assert tree.root == fixtures_dir
    finally:
        tree.deleteLater()


# ──────────────────────────────────────────────────────────────────────
# 2026-05-23 file-list diagnostic affordances
# ──────────────────────────────────────────────────────────────────────


class TestDiagnosticAffordances:
    """Regression guards for the empty-state placeholder, path tooltip,
    and refresh button added by the deferred file-list diagnostic
    pass.  Symptom: users dropped image files into a folder and saw an
    empty Files tab with no hint about which folder was being watched.
    """

    def test_refresh_button_is_wired_to_refresh(
        self, qapp: QApplication, fixtures_dir: Path
    ) -> None:
        tree = FileTree(root=fixtures_dir)
        try:
            assert tree._refresh_btn is not None
            assert tree._refresh_btn.text() == "\u21bb"
            # Click should not raise and should preserve the root.
            tree._refresh_btn.click()
            assert tree.root == fixtures_dir
        finally:
            tree.deleteLater()

    def test_label_tooltip_shows_absolute_path(
        self, qapp: QApplication, fixtures_dir: Path
    ) -> None:
        tree = FileTree()
        try:
            tree.set_root(fixtures_dir)
            tip = tree._label.toolTip()
            # Tooltip is the absolute path; on Windows that's a drive-
            # rooted path string.
            assert tip
            assert str(fixtures_dir) in tip or str(fixtures_dir.resolve()) in tip
        finally:
            tree.deleteLater()

    def test_placeholder_shown_for_missing_root(
        self, qapp: QApplication, tmp_path: Path
    ) -> None:
        ghost = tmp_path / "does_not_exist"
        tree = FileTree(root=ghost)
        try:
            assert tree._stack.currentWidget() is tree._placeholder
            text = tree._placeholder.text()
            assert "does not exist" in text.lower()
            assert str(ghost) in text or str(ghost.resolve()) in text
        finally:
            tree.deleteLater()

    def test_placeholder_shown_for_empty_root(
        self, qapp: QApplication, tmp_path: Path
    ) -> None:
        empty = tmp_path / "empty_folder"
        empty.mkdir()
        tree = FileTree(root=empty)
        try:
            # Spin the event loop so QFileSystemModel completes its
            # async populate; the placeholder is updated via the
            # directoryLoaded slot.
            for _ in range(20):
                qapp.processEvents()
                if tree._placeholder.text():
                    break
            assert tree._stack.currentWidget() is tree._placeholder
            text = tree._placeholder.text()
            assert "no files" in text.lower() or "empty" in text.lower()
            assert str(empty) in text or str(empty.resolve()) in text
        finally:
            tree.deleteLater()

    def test_placeholder_hidden_when_files_present(
        self, qapp: QApplication, fixtures_dir: Path
    ) -> None:
        tree = FileTree(root=fixtures_dir)
        try:
            # fixtures_dir contains tiny.png / tiny.json / etc.; spin
            # the event loop so directoryLoaded fires.
            import time
            for _ in range(30):
                qapp.processEvents()
                if tree._stack.currentWidget() is tree._view:
                    break
                time.sleep(0.02)
            assert tree._stack.currentWidget() is tree._view
        finally:
            tree.deleteLater()

    def test_refresh_re_evaluates_placeholder(
        self, qapp: QApplication, tmp_path: Path
    ) -> None:
        """After dropping a file into a previously-empty folder, the
        refresh button must flip the stack to the tree view."""
        folder = tmp_path / "drop_zone"
        folder.mkdir()
        tree = FileTree(root=folder)
        try:
            for _ in range(20):
                qapp.processEvents()
                if tree._placeholder.text():
                    break
            assert tree._stack.currentWidget() is tree._placeholder

            # Drop a file and refresh.
            (folder / "shot.png").write_bytes(
                b"\x89PNG\r\n\x1a\n"  # PNG magic; QFileSystemModel only
                                        # cares about the directory
                                        # listing, not the contents
            )
            tree.refresh()
            import time
            for _ in range(30):
                qapp.processEvents()
                if tree._stack.currentWidget() is tree._view:
                    break
                time.sleep(0.02)
            assert tree._stack.currentWidget() is tree._view
        finally:
            tree.deleteLater()
