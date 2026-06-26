"""Tests for the course knowledge-base merge logic (idempotency + dedup)."""
from capoeira.course import Course


def make_course(tmp_path):
    return Course.load(tmp_path / "course.json")


def test_glossary_added_once(tmp_path):
    course = make_course(tmp_path)
    assert course.add_glossary_term("ganga", "base rhythm", first_seen="2026-06-26") is True
    # Same term (different casing/spacing) is not added again.
    assert course.add_glossary_term("Ganga", "something else") is False
    assert len(course.data["glossary"]) == 1


def test_instructions_deduped(tmp_path):
    course = make_course(tmp_path)
    assert course.add_instruction("Cue the berimbau to your voice", "2026-06-26") is True
    assert course.add_instruction("cue the berimbau to your voice", "2026-07-01") is False
    assert len(course.data["instructions"]) == 1


def test_processed_file_idempotent(tmp_path):
    course = make_course(tmp_path)
    course.mark_processed("abc123", "class1.m4a", "2026-06-26")
    course.mark_processed("abc123", "class1.m4a", "2026-06-26")
    assert len(course.data["processed_files"]) == 1
    assert course.is_processed("abc123")


def test_add_sequence_persists_and_dedups(tmp_path):
    course = make_course(tmp_path)
    course.add_sequence("Angola", ["X", "X", "▽", "△"], category="angola")
    r = course.add_sequence("Angola", ["X", "X", "▽", "△"])
    assert r.status == r.DUPLICATE
    assert len(course.data["toques"]) == 1
    assert len(course.data["toques"][0]["variations"]) == 1


def test_save_and_reload_roundtrip(tmp_path):
    course = make_course(tmp_path)
    course.add_sequence("Angola", ["X", "X", "▽", "△"], category="angola")
    course.add_glossary_term("viola", "highest berimbau")
    course.save()

    reloaded = Course.load(tmp_path / "course.json")
    assert len(reloaded.data["toques"]) == 1
    assert reloaded.data["toques"][0]["variations"][0]["sequence"] == ["X", "X", "▽", "△"]
    assert len(reloaded.data["glossary"]) == 1


def test_seed_course_loads(tmp_path):
    # The shipped seed file should load and expose its toques.
    from capoeira.config import Config

    cfg = Config.load()
    if cfg.course_json.exists():
        course = Course.load(cfg.course_json)
        names = [t["name"] for t in course.data["toques"]]
        assert "Angola" in names
