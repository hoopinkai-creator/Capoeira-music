"""End-to-end processing of a class recording into the living course.

For each unprocessed memo in a class folder:
  * AUDIO track  -> detect strikes, split into phrases, classify into symbol
    sequences (requires the [audio] extra + ffmpeg).
  * SPEECH track -> transcribe, extract glossary terms + instructions/culture
    (requires the [speech]/[ai] extras; degrades to offline fallbacks).

Sequences are de-duplicated at the whole-sequence level and attached to a toque
(named from the transcript when possible, else matched to the closest known
toque, else parked in an 'Unclassified' bucket for the user to name). Notation
images are rendered for every new/updated variation.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .classify import StrikeClassifier
from .config import Config
from .course import Course
from .deps import have, have_ffmpeg
from .ingest import ClassRecording
from .notation import syllables_for


@dataclass
class ClassResult:
    class_id: str
    date: str
    sequences_added: int = 0
    sequences_duplicate: int = 0
    glossary_added: int = 0
    instructions_added: int = 0
    culture_added: int = 0
    memos_processed: int = 0
    warnings: list[str] = field(default_factory=list)
    classifier_mode: str = ""


def _slug(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "_" for c in text]
    return "".join(keep).strip("_").replace("__", "_") or "toque"


def _best_toque_match(sequence: list[str], course: Course) -> tuple[str | None, float]:
    """Closest existing toque by sequence similarity (name, ratio)."""
    best_name, best_ratio = None, 0.0
    for toque in course.toques():
        for var in toque.variations:
            ratio = difflib.SequenceMatcher(a=var.sequence, b=sequence).ratio()
            if ratio > best_ratio:
                best_name, best_ratio = toque.name, ratio
    return best_name, best_ratio


def _name_for_sequence(
    sequence: list[str], transcript_text: str, course: Course, class_id: str, idx: int
) -> tuple[str, str]:
    """Decide which toque a sequence belongs to. Returns (name, category)."""
    text = transcript_text.lower()

    # 1) Exact match against a stored variation -> that toque (a repeat/variation).
    for toque in course.toques():
        if toque.has_sequence(sequence):
            return toque.name, toque.category

    # 2) A known toque named in the transcript.
    named = [t for t in course.toques() if t.name.lower() in text]
    if len(named) == 1:
        return named[0].name, named[0].category

    # 3) Closest known toque if clearly similar -> a new variation of it.
    match_name, ratio = _best_toque_match(sequence, course)
    if match_name and ratio >= 0.6:
        cat = next((t.category for t in course.toques() if t.name == match_name), "")
        return match_name, cat

    # 4) Unclassified bucket for the user to name later.
    return f"Unclassified {class_id} #{idx}", "unclassified"


def _dedupe_sequences(sequences: list[list[str]]) -> list[list[str]]:
    """Collapse identical full sequences (intra-sequence repeats are preserved)."""
    seen: list[list[str]] = []
    for seq in sequences:
        if seq and seq not in seen:
            seen.append(seq)
    return seen


def _audio_sequences(cfg: Config, memo_wavs: list[Path], result: ClassResult) -> list[list[str]]:
    """Run the audio track over a class's memos -> list of symbol sequences."""
    from .onset import detect_strikes, group_phrases

    classifier = StrikeClassifier(cfg.classifier, cfg.model_path)
    result.classifier_mode = classifier.mode
    sequences: list[list[str]] = []
    for wav in memo_wavs:
        strikes = detect_strikes(wav, cfg.audio)
        for phrase in group_phrases(strikes, float(cfg.audio["phrase_gap_seconds"])):
            symbols = classifier.classify_strikes(phrase)
            if symbols:
                sequences.append(symbols)
    return _dedupe_sequences(sequences)


def _speech(cfg: Config, memo_wavs: list[Path]):
    """Run the speech track -> a combined Transcript (or None if unavailable)."""
    if not have("faster_whisper"):
        return None
    from .transcribe import Transcript, transcribe

    segments = []
    for wav in memo_wavs:
        segments.extend(transcribe(wav, cfg.speech).segments)
    return Transcript(segments=segments)


def process_class(cfg: Config, course: Course, rec: ClassRecording) -> ClassResult:
    """Process one class end-to-end, mutating ``course`` in memory."""
    from .ingest import to_wav
    from .render import render_sequence

    result = ClassResult(class_id=rec.class_id, date=rec.date)

    new_memos = [m for m in rec.memos if not course.is_processed(m.hash)]
    if not new_memos:
        result.warnings.append("all memos already processed")
        return result

    # Decode memos to WAV (audio + speech both consume these).
    memo_wavs: list[Path] = []
    if have_ffmpeg():
        for memo in new_memos:
            memo_wavs.append(to_wav(memo.path, int(cfg.audio["sample_rate"])))
    else:
        result.warnings.append("ffmpeg not found: skipping audio/speech tracks")

    # --- AUDIO track ----------------------------------------------------
    sequences: list[list[str]] = []
    if memo_wavs and have("librosa"):
        sequences = _audio_sequences(cfg, memo_wavs, result)
    elif memo_wavs:
        result.warnings.append("librosa not installed: skipping rhythm detection")

    # --- SPEECH track ---------------------------------------------------
    transcript = _speech(cfg, memo_wavs) if memo_wavs else None
    transcript_text = transcript.text if transcript else ""

    # --- attach sequences to toques + render ----------------------------
    for idx, seq in enumerate(sequences, start=1):
        name, category = _name_for_sequence(seq, transcript_text, course, rec.class_id, idx)
        res = course.add_sequence(
            name, seq, category=category, first_seen=rec.date, source=rec.class_id
        )
        if res.status == res.DUPLICATE:
            result.sequences_duplicate += 1
            continue
        result.sequences_added += 1
        png = cfg.notation_dir / f"{_slug(name)}_{_slug('_'.join(seq))}.png"
        svg = png.with_suffix(".svg")
        render_sequence(
            seq, svg, title=name, syllables=syllables_for(seq),
            out_png=png if have("cairosvg") else None,
        )
        course.set_variation_png(name, seq, str(png.relative_to(cfg.root)))

    # --- glossary + notes -----------------------------------------------
    if transcript is not None and transcript_text:
        from .glossary import extract_glossary
        from .notes import extract_notes

        for entry in extract_glossary(transcript, cfg.ai["model"]):
            if course.add_glossary_term(
                entry["term"], entry["english"], context=entry.get("context", ""),
                first_seen=rec.date,
            ):
                result.glossary_added += 1

        notes = extract_notes(transcript, cfg.ai["model"])
        for text in notes["instructions"]:
            if course.add_instruction(text, rec.date):
                result.instructions_added += 1
        for text in notes["culture"]:
            if course.add_culture(text, rec.date):
                result.culture_added += 1
        course.add_class(rec.date, rec.class_id, notes.get("summary", ""))
    else:
        course.add_class(rec.date, rec.class_id, "")

    # --- mark processed -------------------------------------------------
    for memo in new_memos:
        course.mark_processed(memo.hash, memo.path.name, rec.date)
    result.memos_processed = len(new_memos)
    return result
