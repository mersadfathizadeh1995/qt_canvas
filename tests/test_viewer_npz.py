"""Tests for :class:`NpzViewer` and the file-tree ``reveal`` gesture."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

np = pytest.importorskip("numpy")

from qt_file_canvas import DEFAULT_REGISTRY, FileCanvas  # noqa: E402
from qt_file_canvas.viewers.npz import NpzViewer  # noqa: E402


def _write_spectrum(path: Path, *, dc: bool = False) -> None:
    F, V = 24, 40
    freqs = np.linspace(5, 62, F).astype("f4")
    vels = np.linspace(50, 2500, V).astype("f4")
    if dc:  # DC-cut schema: power (V, F) + picked_velocities (F,)
        np.savez_compressed(
            path, frequencies=freqs, velocities=vels,
            power=np.random.rand(V, F).astype("f4"),
            picked_velocities=np.linspace(300, 800, F).astype("f4"),
            method="ActiveRTBF")
    else:   # plain schema: power (F, V)
        np.savez_compressed(
            path, freqs=freqs, velocities=vels,
            power=np.random.rand(F, V).astype("f4"), mode="bartlett")


def test_npz_registered_in_default_registry() -> None:
    spec = DEFAULT_REGISTRY.lookup(Path("x.npz"))
    assert spec is not None and spec.key == "npz"


def test_npz_viewer_heatmaps_both_schemas(qapp: QApplication, tmp_path: Path) -> None:
    matplotlib = pytest.importorskip("matplotlib")  # noqa: F841
    for dc in (False, True):
        p = tmp_path / ("dc.npz" if dc else "spectrum.npz")
        _write_spectrum(p, dc=dc)
        vw = NpzViewer()
        try:
            vw.load_path(p)
            # rendered onto the matplotlib canvas (imshow + colorbar => 2 axes)
            assert vw._canvas is not None
            assert vw._stack.currentWidget() is vw._canvas
            assert len(vw._figure.axes) >= 1
        finally:
            vw.deleteLater()


def test_npz_viewer_lists_keys_when_no_2d(qapp: QApplication, tmp_path: Path) -> None:
    p = tmp_path / "vectors.npz"
    np.savez_compressed(p, a=np.arange(5), b=np.arange(3, dtype="f4"))
    vw = NpzViewer()
    try:
        vw.load_path(p)
        assert vw._stack.currentWidget() is vw._text
        txt = vw._text.toPlainText()
        assert "a:" in txt and "b:" in txt
    finally:
        vw.deleteLater()


def test_file_canvas_reveal_expands_nested_folder(qapp: QApplication, tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "runs").mkdir()
    shot = tmp_path / "outputs" / "1"
    shot.mkdir(parents=True)
    (shot / "stacked.png").write_bytes(b"x")
    canvas = FileCanvas(root=tmp_path)
    try:
        qapp.processEvents()
        canvas.reveal(shot)
        qapp.processEvents()
        model, view = canvas.tree._model, canvas.tree._view
        assert view.isExpanded(model.index(str(tmp_path / "outputs")))
        assert canvas.tree.current_path() == shot
    finally:
        canvas.deleteLater()
