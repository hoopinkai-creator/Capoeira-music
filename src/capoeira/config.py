"""Configuration loading and path resolution.

Loads ``config.yaml`` from the project root and exposes resolved absolute paths.
Falls back to sane defaults if a key is missing so the core never crashes on a
partial config.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - yaml is a core dependency
    yaml = None


def project_root() -> Path:
    """Project root = two levels up from this file (src/capoeira/config.py)."""
    return Path(__file__).resolve().parents[2]


_DEFAULTS: dict[str, Any] = {
    "paths": {
        "recordings": "recordings",
        "course_json": "data/course.json",
        "calibration": "data/calibration",
        "model": "data/models/strike_clf.pkl",
        "output": "output",
        "notation": "output/notation",
    },
    "audio": {
        "sample_rate": 16000,
        "onset": {"delta": 0.06, "wait": 2, "pre_max": 3, "post_max": 3},
        "phrase_gap_seconds": 1.2,
        "strike_window_seconds": 0.25,
    },
    "classifier": {
        "heuristic": {
            "buzz_zcr_threshold": 0.18,
            "pitch_split_hz": 320.0,
            "accent_rms_percentile": 85,
        }
    },
    "speech": {"whisper_model": "small", "languages": ["pt", "en"]},
    "ai": {"model": "claude-opus-4-8"},
    "canva": {"design_id": None},
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


@dataclass
class Config:
    root: Path
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: str | os.PathLike | None = None) -> "Config":
        root = project_root()
        path = Path(config_path) if config_path else root / "config.yaml"
        data: dict[str, Any] = {}
        if path.exists() and yaml is not None:
            data = yaml.safe_load(path.read_text()) or {}
        merged = _deep_merge(_DEFAULTS, data)
        return cls(root=root, raw=merged)

    # --- path helpers -----------------------------------------------------
    def path(self, key: str) -> Path:
        rel = self.raw["paths"][key]
        p = Path(rel)
        return p if p.is_absolute() else self.root / p

    @property
    def recordings_dir(self) -> Path:
        return self.path("recordings")

    @property
    def course_json(self) -> Path:
        return self.path("course_json")

    @property
    def calibration_dir(self) -> Path:
        return self.path("calibration")

    @property
    def model_path(self) -> Path:
        return self.path("model")

    @property
    def output_dir(self) -> Path:
        return self.path("output")

    @property
    def notation_dir(self) -> Path:
        return self.path("notation")

    # --- section helpers --------------------------------------------------
    @property
    def audio(self) -> dict[str, Any]:
        return self.raw["audio"]

    @property
    def classifier(self) -> dict[str, Any]:
        return self.raw["classifier"]

    @property
    def speech(self) -> dict[str, Any]:
        return self.raw["speech"]

    @property
    def ai(self) -> dict[str, Any]:
        return self.raw["ai"]
