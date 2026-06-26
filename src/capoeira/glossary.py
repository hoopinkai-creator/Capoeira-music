"""Extract Brazilian-Portuguese terms from a transcript and translate them.

Strategy:
  * Detect candidate terms = known capoeira vocabulary present in the text plus
    tokens from Portuguese-tagged transcript segments.
  * Translate via the Anthropic helper when available; otherwise fall back to a
    built-in dictionary of common terms so the glossary is still useful offline.

The course layer de-dupes terms, so the same word is only ever stored once.
"""
from __future__ import annotations

import re
from typing import Any

from . import llm
from .transcribe import Transcript

# Common capoeira-music vocabulary to always look for, with offline fallbacks.
SEED_DICTIONARY: dict[str, str] = {
    "berimbau": "the single-string musical bow that leads capoeira music",
    "gunga": "the largest, lowest-pitched berimbau; keeps the base rhythm",
    "ganga": "the gunga's base-rhythm role the other berimbaus play off of",
    "medio": "the medium-pitched berimbau; plays the counter-rhythm",
    "viola": "the smallest, highest-pitched berimbau; improvises",
    "violinha": "another name for the viola (highest berimbau)",
    "toque": "literally 'touch'; a berimbau rhythm pattern",
    "salto": "'jump/leap'; the open low tone (down-triangle, 'tom')",
    "chidao": "the buzzed/scratched sound (X, 'chi')",
    "chiado": "the buzz/rattle sound of the berimbau",
    "preso": "'pressed/held'; the high tone (up-triangle, 'tim')",
    "dobrao": "the coin/stone pressed to the string to change pitch",
    "caxixi": "the woven rattle held with the playing stick",
    "angola": "a slower, lower style of capoeira and its toque",
    "angolinha": "'little Angola'; a variation toque",
    "sao bento pequeno": "'Little Saint Benedict'; a medio toque",
    "sao bento grande": "'Big Saint Benedict'; a faster toque",
    "ladainha": "the opening solo litany sung at the start of a roda",
    "chula": "the call-and-response sung after the ladainha",
    "corrido": "the call-and-response songs sung during play",
    "roda": "the circle in which capoeira is played",
    "mestre": "master; the teacher leading the group",
    "berra-boi": "a large, deep berimbau (lit. 'bull-roarer')",
}

_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ]{3,}")


def _candidate_terms(transcript: Transcript) -> list[str]:
    text = transcript.text.lower()
    found: list[str] = []

    # Multi-word seed terms first (so 'sao bento pequeno' wins over 'sao').
    for term in sorted(SEED_DICTIONARY, key=lambda t: -len(t)):
        if term in text and term not in found:
            found.append(term)

    # Tokens from Portuguese-tagged segments not already captured.
    for seg in transcript.language_spans("pt"):
        for tok in _TOKEN_RE.findall(seg.text.lower()):
            if tok not in found and tok in SEED_DICTIONARY:
                found.append(tok)
    return found


def extract_glossary(transcript: Transcript, model: str) -> list[dict[str, Any]]:
    """Return ``[{term, english, context}]`` for terms found in the transcript."""
    terms = _candidate_terms(transcript)
    if not terms:
        return []

    if llm.available():
        try:
            return _translate_with_ai(terms, transcript.text, model)
        except Exception:
            pass  # fall through to offline dictionary

    return [
        {"term": t, "english": SEED_DICTIONARY.get(t, ""), "context": "capoeira music"}
        for t in terms
    ]


def _translate_with_ai(terms: list[str], context: str, model: str) -> list[dict[str, Any]]:
    system = (
        "You are a Brazilian-Portuguese capoeira-music expert. For each term, give a concise "
        "English meaning grounded in capoeira/berimbau context. Reply ONLY with a JSON array of "
        "objects: {\"term\": str, \"english\": str, \"context\": str}."
    )
    user = (
        "Terms: " + ", ".join(terms) + "\n\n"
        "Transcript excerpt for context:\n" + context[:4000]
    )
    data = llm.ask_json(system, user, model)
    out: list[dict[str, Any]] = []
    for item in data if isinstance(data, list) else []:
        term = str(item.get("term", "")).strip()
        if term:
            out.append(
                {
                    "term": term,
                    "english": str(item.get("english", "")).strip()
                    or SEED_DICTIONARY.get(term.lower(), ""),
                    "context": str(item.get("context", "")).strip() or "capoeira music",
                }
            )
    return out or [
        {"term": t, "english": SEED_DICTIONARY.get(t, ""), "context": "capoeira music"}
        for t in terms
    ]
