"""Calibration: label real strikes and train the classifier.

Audio-only classification needs grounding on the user's own instrument and mic.
The workflow:

  1. ``extract`` — detect strikes in a recording, save a short WAV clip for each,
     and append a row (with an empty label) to ``data/calibration/labels.jsonl``.
  2. ``label``  — interactively assign chi/tom/tim/accent to each pending clip
     (listen to the saved clip path, then type the label).
  3. ``train``  — train a RandomForest on every labeled row and save it to
     ``data/models/strike_clf.pkl``. The pipeline then uses it automatically.

Accuracy improves as more classes are labeled; typically 1–2 classes is enough
to become reliable.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Config
from .deps import require
from .features import extract, feature_vector
from .ingest import ClassRecording, discover_classes, to_wav
from .onset import detect_strikes

VALID_LABELS = {"chi", "tom", "tim", "accent", "skip"}
_LABELS_FILE = "labels.jsonl"


def _store_path(cfg: Config) -> Path:
    return cfg.calibration_dir / _LABELS_FILE


def load_store(cfg: Config) -> list[dict[str, Any]]:
    path = _store_path(cfg)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _append_rows(cfg: Config, rows: list[dict[str, Any]]) -> None:
    path = _store_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _rewrite_store(cfg: Config, rows: list[dict[str, Any]]) -> None:
    path = _store_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")


def extract_class(cfg: Config, target: ClassRecording) -> int:
    """Detect strikes across a class's memos, save clips, append pending rows."""
    soundfile = require("soundfile")
    n_added = 0
    existing = {r["clip"] for r in load_store(cfg)}
    rows: list[dict[str, Any]] = []
    for memo in target.memos:
        wav = to_wav(memo.path, int(cfg.audio["sample_rate"]), out_dir=cfg.calibration_dir / "_wav")
        strikes = detect_strikes(wav, cfg.audio)
        for idx, strike in enumerate(strikes):
            clip = cfg.calibration_dir / f"{memo.hash}_{idx:03d}.wav"
            rel = str(clip.relative_to(cfg.root))
            if rel in existing:
                continue
            soundfile.write(str(clip), strike.samples, strike.sr)
            rows.append(
                {
                    "clip": rel,
                    "class": target.class_id,
                    "time": round(strike.time, 3),
                    "features": extract(strike.samples, strike.sr),
                    "label": "",
                }
            )
            n_added += 1
    _append_rows(cfg, rows)
    return n_added


def pending(cfg: Config) -> list[dict[str, Any]]:
    return [r for r in load_store(cfg) if not r.get("label")]


def label_interactive(cfg: Config, prompt=input) -> int:
    """Prompt for each unlabeled clip. Returns the number labeled this session."""
    rows = load_store(cfg)
    labeled = 0
    for row in rows:
        if row.get("label"):
            continue
        print(f"\nClip: {row['clip']}  (class={row.get('class')}, t={row.get('time')}s)")
        ans = prompt("  label [chi/tom/tim/accent/skip]: ").strip().lower()
        while ans not in VALID_LABELS:
            ans = prompt("  please enter one of chi/tom/tim/accent/skip: ").strip().lower()
        if ans == "skip":
            continue
        row["label"] = ans
        labeled += 1
    _rewrite_store(cfg, rows)
    return labeled


def train(cfg: Config) -> dict[str, Any]:
    """Train and persist the classifier from all labeled rows."""
    from .classify import MLClassifier

    rows = [r for r in load_store(cfg) if r.get("label") and r["label"] != "skip"]
    if len(rows) < 6:
        return {"trained": False, "reason": f"need >=6 labeled strikes, have {len(rows)}"}

    # 'accent' is a loudness attribute, not a base class; treat as tim for the
    # base classifier (the accent pass in classify.py re-applies emphasis).
    label_map = {"accent": "tim"}
    vectors = [feature_vector(r["features"]) for r in rows]
    labels = [label_map.get(r["label"], r["label"]) for r in rows]

    model = MLClassifier.train(vectors, labels)
    model.save(cfg.model_path)
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return {"trained": True, "n": len(rows), "by_label": counts, "model": str(cfg.model_path)}
