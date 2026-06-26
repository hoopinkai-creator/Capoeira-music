"""Tests for the Canva payload builder (typed-text notation form included)."""
from capoeira.canva_sync import build_payload
from capoeira.config import Config
from capoeira.course import Course


def _cfg(tmp_path):
    """Config with output/notation redirected to tmp so tests don't pollute the repo."""
    cfg = Config.load()
    cfg.raw["paths"]["output"] = str(tmp_path / "output")
    cfg.raw["paths"]["notation"] = str(tmp_path / "output" / "notation")
    return cfg


def _course(tmp_path):
    course = Course.load(tmp_path / "course.json")
    course.add_sequence("Angola", ["X", "X", "▽", "△"], category="angola", first_seen="2026-06-26")
    course.add_glossary_term("gunga", "lowest berimbau", first_seen="2026-06-26")
    course.add_instruction("Start with the gunga.", "2026-06-26")
    course.add_culture("Angola is the older style.", "2026-06-26")
    return course


def test_payload_has_all_sections(tmp_path):
    cfg = _cfg(tmp_path)
    payload = build_payload(cfg, _course(tmp_path))
    types = [s["type"] for s in payload["sections"]]
    for expected in ["title", "notation_key", "toques", "glossary", "instructions", "culture", "classes"]:
        assert expected in types


def test_variation_includes_typed_text_form(tmp_path):
    cfg = _cfg(tmp_path)
    payload = build_payload(cfg, _course(tmp_path))
    toques = next(s for s in payload["sections"] if s["type"] == "toques")["pages"]
    var = toques[0]["variations"][0]
    # Ready-to-type vector text (symbols) + aligned syllable line.
    assert var["notation_text"] == "X  X  ▽  △"
    assert var["notation_lines"][0] == "X X ▽ △"
    assert var["notation_lines"][1] == "chi chi tom tim"


def test_payload_carries_existing_design_id(tmp_path):
    cfg = _cfg(tmp_path)
    course = _course(tmp_path)
    course.set_canva_design("DESIGN123", "2026-06-26")
    payload = build_payload(cfg, course)
    assert payload["existing_design_id"] == "DESIGN123"
