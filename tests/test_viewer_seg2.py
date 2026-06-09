"""Tests for the SEG-2 gather viewer + its magic-byte dispatch."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from qt_file_canvas import DEFAULT_REGISTRY
from qt_file_canvas.viewers.seg2 import is_seg2

obspy = pytest.importorskip("obspy")


def test_is_seg2_magic_bytes(tmp_path: Path) -> None:
    good = tmp_path / "rec.dat"
    good.write_bytes(b"\x55\x3a\x01\x00rest")          # SEG-2 descriptor block id
    other = tmp_path / "rec2.dat"
    other.write_bytes(b"\x3a\x55\x00\x00rest")          # byte-swapped form
    junk = tmp_path / "junk.dat"
    junk.write_bytes(b"not a seg2 file" * 4)
    assert is_seg2(good) and is_seg2(other)
    assert not is_seg2(junk)
    assert not is_seg2(tmp_path / "missing.dat")


def test_seg2_registered_and_claims_dat_by_magic(tmp_path: Path) -> None:
    # a .dat that *is* SEG-2 -> the seg2 viewer; a .dat that isn't -> binary
    seg2 = tmp_path / "rec.dat"
    seg2.write_bytes(b"\x55\x3a" + b"\x00" * 64)
    junk = tmp_path / "junk.dat"
    junk.write_bytes(b"hello world" * 8)
    assert DEFAULT_REGISTRY.lookup(seg2).key == "seg2"
    assert DEFAULT_REGISTRY.lookup(junk).key == "binary"
    # the unambiguous extensions resolve by extension too
    assert DEFAULT_REGISTRY.lookup(Path("x.seg2")).key == "seg2"


def test_seg2_viewer_bad_file_emits_failure(qapp: QApplication, tmp_path: Path) -> None:
    from qt_file_canvas.viewers.seg2 import Seg2Viewer
    vw = Seg2Viewer()
    try:
        seen: list = []
        vw.load_failed.connect(lambda p, r: seen.append((p, r)))
        bogus = tmp_path / "bad.seg2"
        bogus.write_bytes(b"\x55\x3a" + b"\x00" * 8)   # magic ok, body invalid
        vw.load_path(bogus)
        assert seen                                     # obspy raised -> failure surfaced
    finally:
        vw.deleteLater()
