"""Load / merge / save the living course knowledge base (``data/course.json``).

The course JSON is the single source of truth. It is version-controlled so each
processed class shows up as a clean git diff. All merge operations are
idempotent: processing the same recording twice must not create duplicates.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .notation import Toque, VariationResult, add_sequence


def _norm(text: str) -> str:
    """Loose normalisation for dedup of glossary terms / note text."""
    return " ".join(text.lower().split())


@dataclass
class Course:
    path: Path
    data: dict[str, Any] = field(default_factory=dict)

    # --- persistence ------------------------------------------------------
    @classmethod
    def load(cls, path: str | Path) -> "Course":
        path = Path(path)
        if path.exists():
            data = json.loads(path.read_text())
        else:
            data = _empty_course()
        data.setdefault("processed_files", [])
        data.setdefault("toques", [])
        data.setdefault("glossary", [])
        data.setdefault("instructions", [])
        data.setdefault("culture", [])
        data.setdefault("classes", [])
        data.setdefault("canva", {"design_id": None, "last_synced": None})
        return cls(path=path, data=data)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n")

    # --- toques -----------------------------------------------------------
    def toques(self) -> list[Toque]:
        return [Toque.from_dict(t) for t in self.data["toques"]]

    def _write_toques(self, toques: list[Toque]) -> None:
        self.data["toques"] = [t.to_dict() for t in toques]

    def add_sequence(
        self,
        name: str,
        sequence: list[str],
        *,
        category: str = "",
        first_seen: str = "",
        source: str = "",
        notes: str = "",
    ) -> VariationResult:
        """Add a played sequence, applying sequence-level dedup, and persist in memory."""
        toques = self.toques()
        result = add_sequence(
            toques,
            name,
            sequence,
            category=category,
            first_seen=first_seen,
            source=source,
            notes=notes,
        )
        self._write_toques(toques)
        return result

    # --- idempotency ------------------------------------------------------
    def is_processed(self, file_hash: str) -> bool:
        return any(p.get("hash") == file_hash for p in self.data["processed_files"])

    def mark_processed(self, file_hash: str, name: str, class_date: str) -> None:
        if self.is_processed(file_hash):
            return
        self.data["processed_files"].append(
            {"hash": file_hash, "name": name, "class_date": class_date}
        )

    # --- glossary ---------------------------------------------------------
    def add_glossary_term(
        self, term: str, english: str, *, context: str = "", first_seen: str = ""
    ) -> bool:
        """Add a Portuguese term once. Returns True if newly added."""
        key = _norm(term)
        for entry in self.data["glossary"]:
            if _norm(entry.get("term", "")) == key:
                return False
        self.data["glossary"].append(
            {"term": term, "english": english, "context": context, "first_seen": first_seen}
        )
        return True

    # --- instructions / culture ------------------------------------------
    def _add_note(self, bucket: str, text: str, class_date: str) -> bool:
        key = _norm(text)
        for entry in self.data[bucket]:
            if _norm(entry.get("text", "")) == key:
                return False
        self.data[bucket].append({"text": text, "class_date": class_date})
        return True

    def add_instruction(self, text: str, class_date: str) -> bool:
        return self._add_note("instructions", text, class_date)

    def add_culture(self, text: str, class_date: str) -> bool:
        return self._add_note("culture", text, class_date)

    # --- classes ----------------------------------------------------------
    def add_class(self, date: str, file: str, summary: str = "") -> None:
        self.data["classes"].append({"date": date, "file": file, "summary": summary})

    # --- canva ------------------------------------------------------------
    def set_canva_design(self, design_id: str, last_synced: str) -> None:
        self.data["canva"] = {"design_id": design_id, "last_synced": last_synced}

    @property
    def canva_design_id(self) -> str | None:
        return self.data.get("canva", {}).get("design_id")


def _empty_course() -> dict[str, Any]:
    return {
        "version": 1,
        "title": "Capoeira Music — Living Course",
        "notation_key": {},
        "processed_files": [],
        "toques": [],
        "glossary": [],
        "instructions": [],
        "culture": [],
        "classes": [],
        "canva": {"design_id": None, "last_synced": None},
    }
