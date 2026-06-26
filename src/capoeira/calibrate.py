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
from .features import FEATURE_NAMES, extract, feature_vector
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


def cluster_strikes(
    cfg: Config, rec, k: int = 3, listen_seconds: float = 0.6, per_cluster: int = 7
) -> list[dict[str, Any]]:
    """Cluster a class's strikes by sound and export one audio montage per cluster.

    Returns a list of cluster summaries. Lets the user label just ``k`` sounds
    (chi/tom/tim/...) instead of hundreds of individual strikes. Assignments are
    saved to ``data/calibration/clusters/<class>.json`` for :func:`train_from_cluster_labels`.
    """
    import json as _json

    import librosa
    import numpy as np
    import soundfile as sf
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    from .onset import detect_strikes

    sr = int(cfg.audio["sample_rate"])
    feats: list[dict[str, float]] = []
    listen: list[Any] = []
    meta: list[dict[str, Any]] = []
    for memo in rec.memos:
        wav = to_wav(memo.path, sr, out_dir=cfg.calibration_dir / "_wav")
        y, _ = librosa.load(str(wav), sr=sr, mono=True)
        for s in detect_strikes(wav, cfg.audio):
            feats.append(extract(s.samples, s.sr))
            start = int(s.time * sr)
            listen.append(y[start : start + int(listen_seconds * sr)])
            meta.append({"memo": memo.hash, "time": round(float(s.time), 3)})

    if not feats:
        return []

    X = np.array([feature_vector(f) for f in feats])
    Xs = StandardScaler().fit_transform(X)
    k = min(k, len(X))
    km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(Xs)

    out_dir = cfg.calibration_dir / "clusters"
    out_dir.mkdir(parents=True, exist_ok=True)
    assignments = {
        "class": rec.class_id,
        "k": k,
        "strikes": [
            {**meta[i], "cluster": int(km.labels_[i]), "features": feats[i]}
            for i in range(len(meta))
        ],
    }
    (out_dir / f"{rec.class_id}.json").write_text(_json.dumps(assignments))

    summaries: list[dict[str, Any]] = []
    gap = np.zeros(int(0.15 * sr))
    for c in range(k):
        idx = np.where(km.labels_ == c)[0]
        center = km.cluster_centers_[c]
        order = idx[np.argsort(np.linalg.norm(Xs[idx] - center, axis=1))][:per_cluster]
        montage = (
            np.concatenate([np.concatenate([listen[j], gap]) for j in order])
            if len(order)
            else np.zeros(sr)
        )
        wav_path = out_dir / f"{rec.class_id}_cluster{c}.wav"
        sf.write(str(wav_path), montage.astype("float32"), sr)
        sub = X[idx]
        summaries.append({
            "cluster": c,
            "size": int(len(idx)),
            "wav": str(wav_path),
            "zcr": round(float(sub[:, FEATURE_NAMES.index("zcr")].mean()), 3),
            "centroid": round(float(sub[:, FEATURE_NAMES.index("centroid")].mean()), 0),
        })
    return summaries


def train_from_cluster_labels(cfg: Config, class_id: str, labels: dict[int, str]) -> dict[str, Any]:
    """Propagate cluster labels (e.g. {0:'chi',1:'tom',2:'tim'}) to all strikes and train."""
    import json as _json

    from .classify import MLClassifier

    path = cfg.calibration_dir / "clusters" / f"{class_id}.json"
    if not path.exists():
        return {"trained": False, "reason": f"no cluster assignments for {class_id}"}
    data = _json.loads(path.read_text())

    label_map = {"accent": "tim"}
    vectors, ys = [], []
    for st in data["strikes"]:
        lab = labels.get(st["cluster"]) or labels.get(str(st["cluster"]))
        if not lab or lab == "skip":
            continue
        vectors.append(feature_vector(st["features"]))
        ys.append(label_map.get(lab, lab))
    if len(set(ys)) < 2:
        return {"trained": False, "reason": "need at least 2 distinct labels"}

    model = MLClassifier.train(vectors, ys)
    model.save(cfg.model_path)
    counts: dict[str, int] = {}
    for y in ys:
        counts[y] = counts.get(y, 0) + 1
    return {"trained": True, "n": len(ys), "by_label": counts, "model": str(cfg.model_path)}


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
