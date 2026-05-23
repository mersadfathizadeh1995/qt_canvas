"""Tests for :class:`ViewerStack` — dispatch, caching, fallback."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from hvsr_pro.packages.qt_file_canvas.registry import (
    DEFAULT_REGISTRY,
    ViewerRegistry,
    ViewerSpec,
)
from hvsr_pro.packages.qt_file_canvas.viewer_stack import ViewerStack
from hvsr_pro.packages.qt_file_canvas.viewers.base import FileViewer


class _StubViewer(FileViewer):
    """Records what was loaded so tests can assert behaviour."""

    def __init__(self, *, fail: bool = False, cap: int | None = None) -> None:
        super().__init__()
        self.loaded: list[Path] = []
        self.cleared = 0
        self._fail = fail
        self._cap = cap

    def load_path(self, path: Path) -> None:
        if self._fail:
            raise RuntimeError("intentional viewer failure")
        self.loaded.append(path)
        self.file_loaded.emit(path)

    def clear(self) -> None:
        self.cleared += 1

    def max_preview_bytes(self):
        return self._cap


def _make_registry_with_stub(
    *, fail: bool = False, cap: int | None = None
) -> tuple[ViewerRegistry, _StubViewer]:
    """Build a registry where the stub viewer claims everything."""
    registry = ViewerRegistry()
    stub = _StubViewer(fail=fail, cap=cap)
    registry.register(ViewerSpec(
        key="stub",
        label="Stub",
        extensions=(),
        factory=lambda: stub,
        can_view=lambda _path: True,
        priority=10,
    ))
    # Provide a binary fallback so the stack can recover from failures.
    binary = _StubViewer()
    registry.register(ViewerSpec(
        key="binary",
        label="Binary",
        extensions=(),
        factory=lambda: binary,
        can_view=lambda _path: True,
        priority=-1,
    ))
    return registry, stub


# ──────────────────────────────────────────────────────────────────────
class TestViewerStack:
    def test_shows_empty_on_construction(self, qapp: QApplication) -> None:
        stack = ViewerStack()
        try:
            assert stack.current_path() is None
        finally:
            stack.deleteLater()

    def test_load_path_dispatches_to_matching_viewer(
        self, qapp: QApplication, fixtures_dir: Path
    ) -> None:
        registry, stub = _make_registry_with_stub()
        stack = ViewerStack(registry=registry)
        try:
            target = fixtures_dir / "tiny.json"
            stack.load_path(target)
            assert stub.loaded == [target]
            assert stack.current_path() == target
        finally:
            stack.deleteLater()

    def test_viewer_cache_reuses_instance(
        self, qapp: QApplication, fixtures_dir: Path
    ) -> None:
        # Counter-based factory: a fresh ViewerStack should only call
        # it once even when load_path runs twice.
        calls: list[int] = []
        stub = _StubViewer()

        def factory() -> FileViewer:
            calls.append(1)
            return stub

        registry = ViewerRegistry()
        registry.register(ViewerSpec(
            key="stub", label="Stub", extensions=(), factory=factory,
            can_view=lambda _p: True, priority=10,
        ))
        registry.register(ViewerSpec(
            key="binary", label="Binary", extensions=(),
            factory=lambda: _StubViewer(),
            can_view=lambda _p: True, priority=-1,
        ))
        stack = ViewerStack(registry=registry)
        try:
            stack.load_path(fixtures_dir / "tiny.json")
            stack.load_path(fixtures_dir / "tiny.txt")
            assert sum(calls) == 1, "factory should be called only once"
        finally:
            stack.deleteLater()

    def test_failure_falls_back_to_binary(
        self, qapp: QApplication, fixtures_dir: Path
    ) -> None:
        registry, stub = _make_registry_with_stub(fail=True)
        stack = ViewerStack(registry=registry)
        try:
            failures: list[tuple[Path, str]] = []
            stack.viewer_failed.connect(
                lambda p, reason: failures.append((p, reason))
            )
            target = fixtures_dir / "tiny.txt"
            stack.load_path(target)
            assert len(failures) == 1
            assert failures[0][0] == target
        finally:
            stack.deleteLater()

    def test_size_cap_short_circuits_to_binary(
        self, qapp: QApplication, fixtures_dir: Path
    ) -> None:
        # Stub claims a 1-byte cap → any real file is "too big" and the
        # stack should hand off to the binary fallback instead of
        # calling load_path on the stub.
        registry, stub = _make_registry_with_stub(cap=1)
        stack = ViewerStack(registry=registry)
        try:
            target = fixtures_dir / "tiny.txt"
            stack.load_path(target)
            assert stub.loaded == [], "Stub should NOT have received the load"
        finally:
            stack.deleteLater()

    def test_show_empty_clears_current_path(
        self, qapp: QApplication, fixtures_dir: Path
    ) -> None:
        registry, _stub = _make_registry_with_stub()
        stack = ViewerStack(registry=registry)
        try:
            stack.load_path(fixtures_dir / "tiny.txt")
            stack.show_empty()
            assert stack.current_path() is None
        finally:
            stack.deleteLater()
