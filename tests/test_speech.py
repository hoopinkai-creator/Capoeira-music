"""Tests for glossary + notes extraction offline fallbacks (no AI, no audio)."""
from capoeira.glossary import extract_glossary
from capoeira.notes import extract_notes
from capoeira.transcribe import Segment, Transcript


def _transcript():
    return Transcript(segments=[
        Segment(0.0, 4.0, "Start with the gunga and play the toque for Angola.", "en"),
        Segment(4.0, 8.0, "Pull the string with your finger to change the tone.", "en"),
        Segment(8.0, 12.0, "Capoeira Angola comes from the history and tradition of Bahia.", "en"),
        Segment(12.0, 14.0, "o berimbau e o caxixi", "pt"),
    ])


def test_glossary_finds_seed_terms_offline():
    g = extract_glossary(_transcript(), model="x")
    terms = {e["term"] for e in g}
    assert "gunga" in terms
    assert "berimbau" in terms
    assert "caxixi" in terms
    # Offline fallback supplies an English meaning from the seed dictionary.
    gunga = next(e for e in g if e["term"] == "gunga")
    assert "berimbau" in gunga["english"].lower()


def test_multiword_term_detected():
    t = Transcript(segments=[Segment(0, 3, "today we learn sao bento pequeno", "en")])
    terms = {e["term"] for e in extract_glossary(t, model="x")}
    assert "sao bento pequeno" in terms


def test_notes_heuristic_splits_instructions_and_culture():
    notes = extract_notes(_transcript(), model="x")
    instr = " ".join(notes["instructions"]).lower()
    culture = " ".join(notes["culture"]).lower()
    assert "pull the string" in instr
    assert "tradition" in culture or "history" in culture
    assert notes["summary"]


def test_empty_transcript_safe():
    notes = extract_notes(Transcript(segments=[]), model="x")
    assert notes == {"instructions": [], "culture": [], "summary": ""}
    assert extract_glossary(Transcript(segments=[]), model="x") == []
