"""Extract playing instructions, history/cultural context, and a class summary.

Uses the Anthropic helper to segment the transcript into:
  * **instructions** — actionable playing guidance (technique, register, order).
  * **culture** — history, lineage, meaning, and cultural context.
  * **summary** — a short paragraph describing the class.

Falls back to a lightweight keyword heuristic when AI is unavailable, so the
course still records *something* per class.
"""
from __future__ import annotations

from typing import Any

from . import llm
from .transcribe import Transcript

_INSTRUCTION_CUES = (
    "pull", "press", "string", "finger", "cue", "start with", "begin with",
    "register", "tempo", "faster", "slower", "hold", "strike", "hit", "play",
    "practice", "repeat", "count", "sing", "voice",
)
_CULTURE_CUES = (
    "history", "tradition", "angola", "regional", "slave", "brazil", "bahia",
    "mestre", "lineage", "ancestor", "ritual", "roda", "origin", "culture",
    "meaning", "spirit",
)


def extract_notes(transcript: Transcript, model: str) -> dict[str, Any]:
    """Return ``{instructions: [...], culture: [...], summary: str}``."""
    if not transcript.text:
        return {"instructions": [], "culture": [], "summary": ""}

    if llm.available():
        try:
            return _extract_with_ai(transcript.text, model)
        except Exception:
            pass

    return _extract_heuristic(transcript)


def _extract_with_ai(text: str, model: str) -> dict[str, Any]:
    system = (
        "You analyse a transcript of a capoeira-music (berimbau) lesson. Extract: "
        "(1) concrete playing INSTRUCTIONS the student should follow, "
        "(2) any HISTORY or CULTURAL context mentioned, and "
        "(3) a 1-2 sentence SUMMARY of the class. "
        "Each instruction/culture item must be a short standalone sentence. "
        "Reply ONLY as JSON: {\"instructions\": [str], \"culture\": [str], \"summary\": str}."
    )
    data = llm.ask_json(system, text[:12000], model)
    if not isinstance(data, dict):
        return {"instructions": [], "culture": [], "summary": ""}
    return {
        "instructions": [str(x).strip() for x in data.get("instructions", []) if str(x).strip()],
        "culture": [str(x).strip() for x in data.get("culture", []) if str(x).strip()],
        "summary": str(data.get("summary", "")).strip(),
    }


def _split_sentences(text: str) -> list[str]:
    out: list[str] = []
    for chunk in text.replace("?", ".").replace("!", ".").split("."):
        s = chunk.strip()
        if len(s.split()) >= 4:
            out.append(s)
    return out


def _extract_heuristic(transcript: Transcript) -> dict[str, Any]:
    instructions: list[str] = []
    culture: list[str] = []
    for sent in _split_sentences(transcript.text):
        low = sent.lower()
        if any(cue in low for cue in _CULTURE_CUES):
            culture.append(sent)
        elif any(cue in low for cue in _INSTRUCTION_CUES):
            instructions.append(sent)
    summary = transcript.text[:240].strip()
    return {"instructions": instructions, "culture": culture, "summary": summary}
