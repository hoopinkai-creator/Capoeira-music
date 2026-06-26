"""Tests for recording discovery (one folder per class, multiple memos allowed)."""
from capoeira.ingest import discover_classes, parse_date


def _touch(path, content=b"audio"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_parse_date_from_name():
    assert parse_date("2026-06-26-angola-intro") == "2026-06-26"
    assert parse_date("20260703_lesson") == "2026-07-03"


def test_one_folder_per_class_with_multiple_memos(tmp_path):
    rec = tmp_path / "recordings"
    _touch(rec / "2026-06-26-angola" / "memo-1.m4a", b"a")
    _touch(rec / "2026-06-26-angola" / "memo-2.m4a", b"bb")  # different content -> different hash
    _touch(rec / "2026-07-03-sao-bento" / "lesson.m4a", b"ccc")

    classes = discover_classes(rec)
    by_id = {c.class_id: c for c in classes}

    assert "2026-06-26-angola" in by_id
    assert len(by_id["2026-06-26-angola"].memos) == 2  # both memos grouped into one class
    assert by_id["2026-06-26-angola"].date == "2026-06-26"
    assert by_id["2026-06-26-angola"].title == "Angola"
    assert len(by_id["2026-07-03-sao-bento"].memos) == 1


def test_loose_file_becomes_its_own_class(tmp_path):
    rec = tmp_path / "recordings"
    _touch(rec / "quick-note.m4a", b"x")
    classes = discover_classes(rec)
    assert any(c.class_id == "quick-note" and len(c.memos) == 1 for c in classes)


def test_memos_have_distinct_hashes(tmp_path):
    rec = tmp_path / "recordings"
    _touch(rec / "c" / "a.m4a", b"one")
    _touch(rec / "c" / "b.m4a", b"two")
    (cls,) = [c for c in discover_classes(rec) if c.class_id == "c"]
    hashes = {m.hash for m in cls.memos}
    assert len(hashes) == 2


def test_ignores_non_audio_files(tmp_path):
    rec = tmp_path / "recordings"
    _touch(rec / "c" / "a.m4a", b"one")
    _touch(rec / "c" / "notes.txt", b"hello")
    (cls,) = [c for c in discover_classes(rec) if c.class_id == "c"]
    assert len(cls.memos) == 1
