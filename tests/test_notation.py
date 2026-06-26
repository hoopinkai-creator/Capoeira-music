"""Tests for the notation dedup / variation logic.

The crucial behaviour: dedup happens at the WHOLE-SEQUENCE level, and repeated
strikes WITHIN a sequence are always preserved.
"""
from capoeira import notation
from capoeira.notation import Toque, add_sequence, syllables_for, diff_sequences


def test_intra_sequence_repeats_preserved():
    toques: list[Toque] = []
    add_sequence(toques, "Angola", ["X", "X", "▽", "△"])
    # Both X's must survive — no collapsing of repeats inside a sequence.
    assert toques[0].variations[0].sequence == ["X", "X", "▽", "△"]


def test_exact_repeat_is_deduplicated():
    toques: list[Toque] = []
    add_sequence(toques, "Angola", ["X", "X", "▽", "△"])
    result = add_sequence(toques, "Angola", ["X", "X", "▽", "△"])
    assert result.status == result.DUPLICATE
    assert len(toques[0].variations) == 1  # not added twice


def test_different_sequence_added_as_variation():
    toques: list[Toque] = []
    add_sequence(toques, "Angola", ["X", "X", "▽", "△"])
    result = add_sequence(toques, "Angola", ["X", "X", "▽", "△", "△"])
    assert result.status == result.ADDED
    assert len(toques[0].variations) == 2
    assert "added" in result.detail  # diff describes the trailing tim


def test_new_toque_created():
    toques: list[Toque] = []
    result = add_sequence(toques, "Sao Bento Pequeno", ["X", "X", "▽", "▲"], category="medio")
    assert result.status == result.ADDED
    assert toques[0].name == "Sao Bento Pequeno"
    assert toques[0].category == "medio"


def test_toque_name_match_is_case_insensitive():
    toques: list[Toque] = []
    add_sequence(toques, "Angola", ["X", "▽"])
    add_sequence(toques, "angola", ["X", "▽"])
    assert len(toques) == 1  # same toque, not a new one


def test_syllables_rendering():
    assert syllables_for(["X", "X", "▽", "△"]) == "chi chi tom tim"


def test_invalid_symbol_rejected():
    toques: list[Toque] = []
    try:
        add_sequence(toques, "Bad", ["X", "Z"])
    except ValueError as exc:
        assert "Z" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for invalid symbol")


def test_diff_describes_insertion():
    detail = diff_sequences(["X", "X", "▽", "△"], ["X", "X", "▽", "△", "△"])
    assert "added" in detail


def test_syllable_to_symbol_map():
    assert notation.SYLLABLE_TO_SYMBOL["chi"] == "X"
    assert notation.SYLLABLE_TO_SYMBOL["tom"] == "▽"
    assert notation.SYLLABLE_TO_SYMBOL["tim"] == "△"
