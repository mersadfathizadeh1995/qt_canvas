"""Unit tests for :class:`ViewerRegistry`."""

from __future__ import annotations

from pathlib import Path

import pytest

from qt_file_canvas.registry import (
    DEFAULT_REGISTRY,
    ViewerRegistry,
    ViewerSpec,
)
from qt_file_canvas.viewers.base import FileViewer


class _NoopViewer(FileViewer):
    """Minimal :class:`FileViewer` for registration tests."""

    def load_path(self, path: Path) -> None:
        return None


def _spec(key: str, *exts: str, priority: int = 0) -> ViewerSpec:
    return ViewerSpec(
        key=key,
        label=key.title(),
        extensions=tuple(exts),
        factory=lambda: _NoopViewer(),
        priority=priority,
    )


# ──────────────────────────────────────────────────────────────────────
class TestRegisterUnregister:
    def test_register_then_lookup_by_extension(
        self, isolated_registry: ViewerRegistry
    ) -> None:
        isolated_registry.register(_spec("foo", ".foo"))
        found = isolated_registry.lookup(Path("a.foo"))
        assert found is not None
        assert found.key == "foo"

    def test_register_collision_raises(
        self, isolated_registry: ViewerRegistry
    ) -> None:
        isolated_registry.register(_spec("dup"))
        with pytest.raises(ValueError, match="already registered"):
            isolated_registry.register(_spec("dup"))

    def test_replace_is_idempotent(
        self, isolated_registry: ViewerRegistry
    ) -> None:
        isolated_registry.register(_spec("x", ".x", priority=1))
        isolated_registry.replace(_spec("x", ".x", priority=5))
        spec = isolated_registry.lookup(Path("y.x"))
        assert spec is not None and spec.priority == 5

    def test_unregister_known_key_removes(
        self, isolated_registry: ViewerRegistry
    ) -> None:
        isolated_registry.register(_spec("z", ".z"))
        isolated_registry.unregister("z")
        assert isolated_registry.lookup(Path("a.z")) is None

    def test_unregister_unknown_key_is_noop(
        self, isolated_registry: ViewerRegistry
    ) -> None:
        isolated_registry.unregister("nonexistent")  # no raise


# ──────────────────────────────────────────────────────────────────────
class TestLookupPriority:
    def test_higher_priority_wins_on_extension_tie(
        self, isolated_registry: ViewerRegistry
    ) -> None:
        isolated_registry.register(_spec("low", ".dat", priority=1))
        isolated_registry.register(_spec("high", ".dat", priority=10))
        match = isolated_registry.lookup(Path("file.dat"))
        assert match is not None and match.key == "high"

    def test_can_view_predicate_is_consulted(
        self, isolated_registry: ViewerRegistry
    ) -> None:
        sniff_spec = ViewerSpec(
            key="sniff",
            label="Sniff",
            extensions=(),
            factory=lambda: _NoopViewer(),
            can_view=lambda p: p.name == "magic",
            priority=5,
        )
        isolated_registry.register(sniff_spec)
        # No extension match, but can_view says yes.
        m = isolated_registry.lookup(Path("magic"))
        assert m is not None and m.key == "sniff"

    def test_no_match_returns_none(
        self, isolated_registry: ViewerRegistry
    ) -> None:
        # Fresh registry: no fallback registered.
        assert isolated_registry.lookup(Path("a.unknown")) is None


# ──────────────────────────────────────────────────────────────────────
class TestDefaultRegistryShape:
    def test_default_registry_has_builtin_viewers(self) -> None:
        keys = {s.key for s in DEFAULT_REGISTRY.all()}
        # Mandatory: binary fallback always registers.
        assert "binary" in keys
        # Stdlib-only viewers must register too.
        assert "json" in keys
        assert "markdown" in keys
        assert "image" in keys
        assert "text" in keys
        # csv always tries to register (with or without pandas).
        assert "csv" in keys

    def test_default_binary_fallback_matches_anything(self) -> None:
        spec = DEFAULT_REGISTRY.lookup(Path("anything.unknown.extension"))
        assert spec is not None
        assert spec.key == "binary"

    def test_default_json_dispatch(self) -> None:
        spec = DEFAULT_REGISTRY.lookup(Path("foo.json"))
        assert spec is not None
        assert spec.key == "json"


# ──────────────────────────────────────────────────────────────────────
class TestRegistryContainerProtocol:
    def test_len_tracks_registrations(
        self, isolated_registry: ViewerRegistry
    ) -> None:
        assert len(isolated_registry) == 0
        isolated_registry.register(_spec("a"))
        isolated_registry.register(_spec("b"))
        assert len(isolated_registry) == 2

    def test_contains_known_key(
        self, isolated_registry: ViewerRegistry
    ) -> None:
        isolated_registry.register(_spec("hello"))
        assert "hello" in isolated_registry
        assert "missing" not in isolated_registry

    def test_all_is_sorted_by_priority_desc(
        self, isolated_registry: ViewerRegistry
    ) -> None:
        isolated_registry.register(_spec("a", priority=1))
        isolated_registry.register(_spec("b", priority=10))
        isolated_registry.register(_spec("c", priority=5))
        keys = [s.key for s in isolated_registry.all()]
        assert keys == ["b", "c", "a"]
