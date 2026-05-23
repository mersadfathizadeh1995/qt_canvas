"""Viewer plugin registry.

A :class:`ViewerRegistry` maps file extensions (and optional
magic-byte sniffers) to :class:`ViewerSpec` records.  The package
ships a process-wide :data:`DEFAULT_REGISTRY` which the built-in
viewer modules self-register against on import; consumers that want
isolation can pass a private :class:`ViewerRegistry()` to
:class:`FileCanvas`.

Registration is intentionally idempotent through :meth:`replace` so
applications can override built-in viewers with custom ones without
worrying about import order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# ──────────────────────────────────────────────────────────────────────
# ViewerSpec
# ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ViewerSpec:
    """Plugin descriptor — one record per viewer kind.

    Attributes
    ----------
    key:
        Stable identifier, e.g. ``"image"``.  Used by
        :class:`ViewerStack` to key its cache of viewer instances.
        Two specs with the same ``key`` collide (use :meth:`replace`
        to override).
    label:
        Human-readable label shown in the kind pill / error fallback.
    extensions:
        Lowercase file extensions including the leading dot, e.g.
        ``(".png", ".jpg")``.  Empty tuple is legal if the spec
        relies on :attr:`can_view` for the match.
    factory:
        Zero-argument callable returning a fresh
        :class:`qt_file_canvas.viewers.base.FileViewer` instance.
        Called lazily by :class:`ViewerStack` the first time a file
        of this kind is opened.
    can_view:
        Optional override for extension matching.  When provided, the
        registry calls ``can_view(path)`` *in addition to* the
        extension check.  Either match accepts; both miss rejects.
        Use this for magic-byte sniffers or content-based dispatch.
    priority:
        Tie-breaker when multiple specs match.  Higher wins.  The
        binary fallback uses ``-1`` so it sorts after every other
        spec.
    description:
        Optional human-readable note.  Surfaced in error messages
        and the demo app's About screen.
    """

    key: str
    label: str
    extensions: Tuple[str, ...]
    factory: Callable[[], "FileViewer"]  # noqa: F821 — forward ref
    can_view: Optional[Callable[[Path], bool]] = None
    priority: int = 0
    description: str = ""


# ──────────────────────────────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────────────────────────────


class ViewerRegistry:
    """Indexed collection of :class:`ViewerSpec` records.

    Two indices live behind one storage:

    * ``_by_key``       — exact-key lookup for unregister / replace.
    * ``_by_extension`` — dict of ``"".lower() → List[ViewerSpec]``
                          ordered by descending priority + first-seen
                          stability.

    :meth:`lookup` walks the extensions first (fast O(1) for the
    common case), then falls back to ``can_view`` predicates ordered
    by priority.
    """

    def __init__(self) -> None:
        self._by_key: Dict[str, ViewerSpec] = {}
        self._by_extension: Dict[str, List[ViewerSpec]] = {}
        self._fallbacks: List[ViewerSpec] = []  # specs with no extensions OR can_view-only

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------
    def register(self, spec: ViewerSpec) -> None:
        """Add *spec*.  Raises :class:`ValueError` on key collision."""
        if spec.key in self._by_key:
            raise ValueError(
                f"ViewerSpec key already registered: {spec.key!r}. "
                "Use replace() to override."
            )
        self._add(spec)

    def replace(self, spec: ViewerSpec) -> None:
        """Idempotent register: unregister any existing key, then add."""
        if spec.key in self._by_key:
            self.unregister(spec.key)
        self._add(spec)

    def unregister(self, key: str) -> None:
        """Remove the spec with *key*.  Unknown keys are a no-op."""
        existing = self._by_key.pop(key, None)
        if existing is None:
            return
        for ext in existing.extensions:
            bucket = self._by_extension.get(ext.lower())
            if bucket is None:
                continue
            try:
                bucket.remove(existing)
            except ValueError:
                continue
            if not bucket:
                del self._by_extension[ext.lower()]
        if existing in self._fallbacks:
            self._fallbacks.remove(existing)

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------
    def lookup(self, path: Path) -> Optional[ViewerSpec]:
        """Return the highest-priority spec that matches *path*.

        Resolution order:

        1. extension match (``path.suffix.lower()``);
        2. ``can_view(path)`` predicate of each fallback spec, ordered
           by descending priority.

        Returns ``None`` when no spec matches; in practice the binary
        fallback's ``can_view = lambda _: True`` guarantees a match
        for any path, so callers can rely on a non-None result when
        the default registry is used.
        """
        ext = path.suffix.lower()
        candidates: List[ViewerSpec] = []
        if ext:
            candidates.extend(self._by_extension.get(ext, ()))
        # Always consider fallback specs so a can_view sniffer can
        # claim files even when the extension doesn't match.
        for spec in self._fallbacks:
            if spec.can_view is not None and spec.can_view(path):
                candidates.append(spec)
        if not candidates:
            # Final pass: any spec with can_view but no extension list
            # still gets a shot via the fallback pool.  This is the
            # binary viewer's path.
            for spec in self._fallbacks:
                if spec.can_view is None:
                    candidates.append(spec)
        if not candidates:
            return None
        # Highest priority wins; on tie, registration order is stable.
        candidates.sort(key=lambda s: s.priority, reverse=True)
        return candidates[0]

    def all(self) -> List[ViewerSpec]:
        """Return every registered spec, sorted by descending priority."""
        return sorted(self._by_key.values(), key=lambda s: s.priority, reverse=True)

    def __contains__(self, key: object) -> bool:
        return key in self._by_key

    def __len__(self) -> int:
        return len(self._by_key)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _add(self, spec: ViewerSpec) -> None:
        self._by_key[spec.key] = spec
        for ext in spec.extensions:
            self._by_extension.setdefault(ext.lower(), []).append(spec)
        # A spec joins the fallback pool when it has either a can_view
        # predicate or zero declared extensions.  This is the path the
        # binary viewer takes.
        if spec.can_view is not None or not spec.extensions:
            self._fallbacks.append(spec)


# ──────────────────────────────────────────────────────────────────────
# Default registry + convenience wrappers
# ──────────────────────────────────────────────────────────────────────


#: Process-wide default registry.  Built-in viewers register against
#: this on import.  Callers wanting isolation pass a private
#: :class:`ViewerRegistry()` to :class:`FileCanvas`.
DEFAULT_REGISTRY = ViewerRegistry()


def register_viewer(spec: ViewerSpec) -> None:
    """Convenience: ``DEFAULT_REGISTRY.register(spec)``."""
    DEFAULT_REGISTRY.register(spec)


def unregister_viewer(key: str) -> None:
    """Convenience: ``DEFAULT_REGISTRY.unregister(key)``."""
    DEFAULT_REGISTRY.unregister(key)


__all__ = [
    "DEFAULT_REGISTRY",
    "ViewerRegistry",
    "ViewerSpec",
    "register_viewer",
    "unregister_viewer",
]
