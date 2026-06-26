"""Tests for the dependency-free SVG renderer (PNG rasterisation is optional)."""
from capoeira.render import build_svg, render_sequence


def test_svg_contains_symbols_and_labels():
    svg = build_svg(["X", "X", "▽", "△"], title="Angola")
    assert svg.startswith("<svg")
    assert "Angola" in svg
    assert "<polygon" in svg   # the triangles
    assert "<line" in svg      # the X strokes
    # Canonical per-symbol labels are present.
    assert ">chi<" in svg and ">tom<" in svg and ">tim<" in svg


def test_filled_triangle_for_strong_salto():
    svg = build_svg(["▲"])
    # Strong salto is a filled polygon (fill = ink colour, not 'none').
    assert 'fill="#1a2b6b"' in svg


def test_accent_superscript_rendered():
    svg = build_svg(["▽ˣ"])
    assert "#b5341d" in svg  # accent colour used for the superscript x


def test_spoken_subtitle_shown():
    svg = build_svg(["X", "▽"], syllables="chi tom tom")
    assert "chi tom tom" in svg


def test_render_writes_svg(tmp_path):
    out = render_sequence(["X", "▽", "△"], tmp_path / "t.svg", title="Test")
    assert out["svg"].endswith("t.svg")
    assert (tmp_path / "t.svg").exists()
