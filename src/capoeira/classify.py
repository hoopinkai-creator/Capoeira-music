"""Classify each strike into a notation symbol.

Two modes, chosen automatically:

  * **Heuristic (bootstrap):** rule-of-thumb thresholds on the features so the
    system produces output before any labeled data exists. Tunable in
    ``config.yaml`` under ``classifier.heuristic``.
  * **Trained:** a scikit-learn model saved at ``data/models/strike_clf.pkl``,
    produced by the ``calibrate`` workflow. Used automatically when present and
    is far more accurate on the user's own instrument/mic.

After base labels (chi/tom/tim) are assigned, an accent pass marks the loudest
strikes as *strong*: a strong tim -> ▲, a strong tom -> ▽ˣ (hammeron).
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from .deps import require
from .features import FEATURE_NAMES, extract, feature_vector

# Base labels and their plain (un-accented) symbols.
LABELS = ["chi", "tom", "tim"]
LABEL_TO_SYMBOL = {"chi": "X", "tom": "▽", "tim": "△"}
# Strong (accented) upgrades.
STRONG_SYMBOL = {"tim": "▲", "tom": "▽ˣ", "chi": "X"}


class HeuristicClassifier:
    """Threshold-based bootstrap classifier (no training required)."""

    def __init__(self, heuristic_cfg: dict[str, Any]):
        self.buzz_zcr = float(heuristic_cfg.get("buzz_zcr_threshold", 0.18))
        self.pitch_split = float(heuristic_cfg.get("pitch_split_hz", 320.0))

    def predict_label(self, feat: dict[str, float]) -> str:
        # Buzz (chi): noisy / high zero-crossing rate and weak pitch.
        if feat.get("zcr", 0.0) >= self.buzz_zcr and feat.get("pitch_conf", 0.0) < 0.25:
            return "chi"
        # Pitched: low fundamental -> tom (open), high -> tim (pressed).
        pitch = feat.get("pitch_hz", 0.0)
        if pitch <= 0.0:
            # No reliable pitch but not clearly buzz: fall back on brightness.
            return "tim" if feat.get("centroid", 0.0) > 2000 else "tom"
        return "tom" if pitch < self.pitch_split else "tim"


class MLClassifier:
    """scikit-learn wrapper persisted to disk."""

    def __init__(self, model: Any):
        self.model = model

    @classmethod
    def load(cls, path: Path) -> "MLClassifier | None":
        path = Path(path)
        if not path.exists():
            return None
        with open(path, "rb") as f:
            return cls(pickle.load(f))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self.model, f)

    @classmethod
    def train(cls, vectors: list[list[float]], labels: list[str]) -> "MLClassifier":
        require("numpy")
        ensemble = require("sklearn.ensemble")
        clf = ensemble.RandomForestClassifier(n_estimators=200, random_state=0)
        clf.fit(vectors, labels)
        return cls(clf)

    def predict_label(self, feat: dict[str, float]) -> str:
        return str(self.model.predict([feature_vector(feat)])[0])


def _accent_threshold(feats: list[dict[str, float]], percentile: float):
    np = require("numpy")
    rms = [f.get("rms", 0.0) for f in feats]
    if not rms:
        return float("inf")
    return float(np.percentile(rms, percentile))


class StrikeClassifier:
    """High-level classifier: picks trained model if available, else heuristic."""

    def __init__(self, classifier_cfg: dict[str, Any], model_path: Path):
        self.cfg = classifier_cfg
        self.accent_percentile = float(
            classifier_cfg.get("heuristic", {}).get("accent_rms_percentile", 85)
        )
        self.ml = MLClassifier.load(model_path)
        self.heuristic = HeuristicClassifier(classifier_cfg.get("heuristic", {}))

    @property
    def mode(self) -> str:
        return "trained" if self.ml is not None else "heuristic"

    def _label(self, feat: dict[str, float]) -> str:
        return self.ml.predict_label(feat) if self.ml else self.heuristic.predict_label(feat)

    def classify_strikes(self, strikes) -> list[str]:
        """Return the symbol sequence for a list of Strike objects."""
        feats = [extract(s.samples, s.sr) for s in strikes]
        labels = [self._label(f) for f in feats]
        threshold = _accent_threshold(feats, self.accent_percentile)
        symbols: list[str] = []
        for feat, label in zip(feats, labels):
            if feat.get("rms", 0.0) >= threshold and label in STRONG_SYMBOL:
                symbols.append(STRONG_SYMBOL[label])
            else:
                symbols.append(LABEL_TO_SYMBOL.get(label, "X"))
        return symbols


# Re-exported for calibrate.py / tests.
__all__ = [
    "FEATURE_NAMES",
    "LABELS",
    "LABEL_TO_SYMBOL",
    "HeuristicClassifier",
    "MLClassifier",
    "StrikeClassifier",
]
