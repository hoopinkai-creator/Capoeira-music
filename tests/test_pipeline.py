"""Tests for pipeline helpers that don't require audio (naming + dedup)."""
from capoeira.course import Course
from capoeira.pipeline import _dedupe_sequences, _name_for_sequence


def _seeded(tmp_path):
    course = Course.load(tmp_path / "course.json")
    course.add_sequence("Angola", ["X", "X", "▽", "△"], category="angola")
    return course


def test_dedupe_keeps_distinct_preserves_repeats():
    seqs = [["X", "X", "▽"], ["X", "X", "▽"], ["X", "▽", "△"]]
    out = _dedupe_sequences(seqs)
    assert out == [["X", "X", "▽"], ["X", "▽", "△"]]
    # The repeated X's inside the first sequence are untouched.
    assert out[0] == ["X", "X", "▽"]


def test_exact_match_routes_to_existing_toque(tmp_path):
    course = _seeded(tmp_path)
    name, cat = _name_for_sequence(["X", "X", "▽", "△"], "", course, "class1", 1)
    assert name == "Angola"


def test_transcript_named_toque_wins(tmp_path):
    course = _seeded(tmp_path)
    name, _ = _name_for_sequence(
        ["X", "▽"], "today we work on Angola", course, "class1", 1
    )
    assert name == "Angola"


def test_similar_sequence_becomes_variation(tmp_path):
    course = _seeded(tmp_path)
    # One extra trailing tim -> close to Angola -> attached as its variation.
    name, _ = _name_for_sequence(["X", "X", "▽", "△", "△"], "", course, "class1", 1)
    assert name == "Angola"


def test_unknown_sequence_parked_as_unclassified(tmp_path):
    course = _seeded(tmp_path)
    name, cat = _name_for_sequence(["△", "△", "△", "△", "▽ˣ"], "", course, "class1", 3)
    assert name.startswith("Unclassified")
    assert cat == "unclassified"
