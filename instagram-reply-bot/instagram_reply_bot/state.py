"""Persist which comment ids we've already replied to, so re-runs are safe."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def load_replied(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return set()
    return set(data.get("replied", []))


def save_replied(path: Path, replied: Iterable[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"replied": sorted(set(replied))}, indent=2))
    return path
