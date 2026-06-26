"""Berimbau notation model + sequence de-duplication / variation detection.

Symbol vocabulary (from the user's handwritten key):

    X   chidao   "chi"   buzz / scratch
    ▽   salto    "tom"   open low tone
    △   preso    "tim"   pressed high tone
    ▽ˣ  hammeron          accented strike
    ▲   salto(strong)     emphasized open tone

Core rule (explicit user constraint):
  * A *sequence* is the full ordered list of strikes for one toque, EXACTLY as
    played. Repeated strikes WITHIN a sequence are always preserved
    (e.g. ``X X ▽ △`` keeps both X's). We never collapse intra-sequence repeats.
  * De-duplication happens only at the WHOLE-SEQUENCE level: if the same full
    sequence is played again (in the same class or across classes), it is
    recorded once. A meaningfully different sequence is stored as a new
    *variation* of the toque, flagged with a short diff.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Iterable

# Canonical symbols and their metadata.
SYMBOLS: dict[str, dict[str, str | None]] = {
    "X": {"name": "chidao", "syllable": "chi", "sound": "buzz / scratch"},
    "▽": {"name": "salto", "syllable": "tom", "sound": "open low tone"},
    "△": {"name": "preso", "syllable": "tim", "sound": "pressed high tone"},
    "▽ˣ": {"name": "hammeron", "syllable": "tom", "sound": "accented strike"},
    "▲": {"name": "preso (strong)", "syllable": "tim", "sound": "emphasized pressed high tone"},
}

# Map a recognised spoken syllable back to its symbol (for speech cross-checks).
SYLLABLE_TO_SYMBOL: dict[str, str] = {
    "chi": "X",
    "tom": "▽",
    "tim": "△",
}

VALID_SYMBOLS = set(SYMBOLS)


def is_valid_sequence(sequence: Iterable[str]) -> bool:
    return all(s in VALID_SYMBOLS for s in sequence)


def syllables_for(sequence: Iterable[str]) -> str:
    """Render a sequence as its spoken syllables, e.g. ['X','▽'] -> 'chi tom'."""
    out = []
    for s in sequence:
        syl = SYMBOLS.get(s, {}).get("syllable")
        out.append(syl if syl else s)
    return " ".join(out)


@dataclass
class Variation:
    """A single distinct way a toque was played."""

    sequence: list[str]
    syllables: str = ""
    notation_png: str | None = None
    first_seen: str = ""
    source: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.syllables:
            self.syllables = syllables_for(self.sequence)

    @classmethod
    def from_dict(cls, d: dict) -> "Variation":
        return cls(
            sequence=list(d.get("sequence", [])),
            syllables=d.get("syllables", ""),
            notation_png=d.get("notation_png"),
            first_seen=d.get("first_seen", ""),
            source=d.get("source", ""),
            notes=d.get("notes", ""),
        )

    def to_dict(self) -> dict:
        return {
            "sequence": list(self.sequence),
            "syllables": self.syllables,
            "notation_png": self.notation_png,
            "first_seen": self.first_seen,
            "source": self.source,
            "notes": self.notes,
        }


def sequences_equal(a: Iterable[str], b: Iterable[str]) -> bool:
    """Exact full-sequence equality. Repeats are significant; order matters."""
    return list(a) == list(b)


def diff_sequences(existing: list[str], new: list[str]) -> str:
    """Human-readable diff describing how ``new`` differs from ``existing``.

    Used to annotate a newly added variation so the course doc explains what
    changed (e.g. 'added a trailing tim (△)').
    """
    sm = difflib.SequenceMatcher(a=existing, b=new)
    parts: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        old = " ".join(existing[i1:i2]) or "∅"
        cur = " ".join(new[j1:j2]) or "∅"
        if tag == "replace":
            parts.append(f"changed '{old}' -> '{cur}'")
        elif tag == "delete":
            parts.append(f"removed '{old}'")
        elif tag == "insert":
            parts.append(f"added '{cur}'")
    if not parts:
        return "identical"
    return "; ".join(parts)


@dataclass
class Toque:
    """A named rhythm with one or more distinct variations."""

    name: str
    category: str = ""
    variations: list[Variation] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Toque":
        return cls(
            name=d.get("name", ""),
            category=d.get("category", ""),
            variations=[Variation.from_dict(v) for v in d.get("variations", [])],
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "variations": [v.to_dict() for v in self.variations],
        }

    def has_sequence(self, sequence: Iterable[str]) -> bool:
        seq = list(sequence)
        return any(sequences_equal(v.sequence, seq) for v in self.variations)

    def closest_variation(self, sequence: list[str]) -> Variation | None:
        """The most similar stored variation (for diff annotation)."""
        best: tuple[float, Variation | None] = (-1.0, None)
        for v in self.variations:
            ratio = difflib.SequenceMatcher(a=v.sequence, b=sequence).ratio()
            if ratio > best[0]:
                best = (ratio, v)
        return best[1]


class VariationResult:
    """Outcome of trying to add a sequence to a toque."""

    ADDED = "added"          # brand-new toque or new variation stored
    DUPLICATE = "duplicate"  # exact sequence already present; ignored

    def __init__(self, status: str, toque: str, variation: Variation | None, detail: str = ""):
        self.status = status
        self.toque = toque
        self.variation = variation
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<VariationResult {self.status} {self.toque!r} {self.detail!r}>"


def add_sequence(
    toques: list[Toque],
    name: str,
    sequence: list[str],
    *,
    category: str = "",
    first_seen: str = "",
    source: str = "",
    notes: str = "",
) -> VariationResult:
    """Add a played sequence to the toque list, applying sequence-level dedup.

    Returns a :class:`VariationResult` describing what happened. The ``toques``
    list is mutated in place.
    """
    if not is_valid_sequence(sequence):
        bad = [s for s in sequence if s not in VALID_SYMBOLS]
        raise ValueError(f"invalid notation symbols: {bad}")

    toque = next((t for t in toques if t.name.lower() == name.lower()), None)

    if toque is None:
        variation = Variation(
            sequence=list(sequence), first_seen=first_seen, source=source, notes=notes
        )
        toques.append(Toque(name=name, category=category, variations=[variation]))
        return VariationResult(VariationResult.ADDED, name, variation, "new toque")

    # Whole-sequence dedup: identical sequence already present -> ignore.
    if toque.has_sequence(sequence):
        return VariationResult(VariationResult.DUPLICATE, name, None, "exact repeat")

    closest = toque.closest_variation(list(sequence))
    detail = diff_sequences(closest.sequence, list(sequence)) if closest else "new variation"
    variation = Variation(
        sequence=list(sequence),
        first_seen=first_seen,
        source=source,
        notes=(notes + (f" (variation: {detail})" if notes else f"variation: {detail}")).strip(),
    )
    toque.variations.append(variation)
    return VariationResult(VariationResult.ADDED, name, variation, detail)
