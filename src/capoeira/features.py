"""Per-strike acoustic feature extraction.

Each detected strike is reduced to a feature vector capturing the cues that
separate the three berimbau sounds:

  * chi (buzz / X)   -> noisy, high zero-crossing rate, no clear pitch
  * tom (open / ▽)   -> low fundamental pitch, resonant
  * tim (pressed / △) -> higher fundamental pitch

Returned as both a named dict (for heuristics / labeling) and an ordered numeric
vector (for the scikit-learn classifier). Keep FEATURE_NAMES in sync with
:func:`feature_vector`.
"""
from __future__ import annotations

from typing import Any

from .deps import require

FEATURE_NAMES = [
    "rms",
    "zcr",
    "centroid",
    "bandwidth",
    "rolloff",
    "flatness",
    "pitch_hz",
    "pitch_conf",
    "mfcc1",
    "mfcc2",
    "mfcc3",
    "mfcc4",
]


def extract(samples, sr: int) -> dict[str, float]:
    """Compute the named feature dict for one strike window."""
    librosa = require("librosa")
    np = require("numpy")

    y = np.asarray(samples, dtype=float)
    if y.size == 0 or float(np.max(np.abs(y))) == 0.0:
        return {name: 0.0 for name in FEATURE_NAMES}
    y = y / (np.max(np.abs(y)) + 1e-9)

    rms = float(np.sqrt(np.mean(y ** 2)))
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(y)[0]))
    centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)))
    rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr)))
    flatness = float(np.mean(librosa.feature.spectral_flatness(y=y)))

    # Fundamental pitch via YIN; guard against the no-pitch (buzz) case.
    try:
        f0 = librosa.yin(y, fmin=80, fmax=1000, sr=sr)
        f0 = f0[np.isfinite(f0)]
        pitch_hz = float(np.median(f0)) if f0.size else 0.0
        # Confidence proxy: how stable the pitch track is.
        pitch_conf = float(1.0 / (1.0 + np.std(f0))) if f0.size else 0.0
    except Exception:
        pitch_hz, pitch_conf = 0.0, 0.0

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=4)
    mfcc_means = [float(np.mean(mfcc[i])) for i in range(4)]

    return {
        "rms": rms,
        "zcr": zcr,
        "centroid": centroid,
        "bandwidth": bandwidth,
        "rolloff": rolloff,
        "flatness": flatness,
        "pitch_hz": pitch_hz,
        "pitch_conf": pitch_conf,
        "mfcc1": mfcc_means[0],
        "mfcc2": mfcc_means[1],
        "mfcc3": mfcc_means[2],
        "mfcc4": mfcc_means[3],
    }


def feature_vector(feat: dict[str, float]) -> list[float]:
    """Ordered numeric vector matching FEATURE_NAMES (for the ML classifier)."""
    return [feat.get(name, 0.0) for name in FEATURE_NAMES]
