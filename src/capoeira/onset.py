"""Strike onset detection + phrase segmentation.

Finds each berimbau strike in a decoded WAV, slices a short window around it for
feature extraction, and groups consecutive strikes into *phrases* (sequences)
using inter-onset gaps. A long gap marks a phrase boundary, so when the whole
toque is played again it is detected as a repeat of the sequence rather than as
new content.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .deps import require


@dataclass
class Strike:
    time: float          # onset time in seconds
    samples: Any         # np.ndarray window around the onset
    sr: int


def load_audio(wav_path: Path, sample_rate: int):
    librosa = require("librosa")
    y, sr = librosa.load(str(wav_path), sr=sample_rate, mono=True)
    return y, sr


def detect_strikes(wav_path: Path, audio_cfg: dict[str, Any]) -> list[Strike]:
    """Detect onsets and return one :class:`Strike` per detected hit."""
    librosa = require("librosa")
    sr = int(audio_cfg.get("sample_rate", 16000))
    y, sr = load_audio(Path(wav_path), sr)

    onset_cfg = audio_cfg.get("onset", {})
    onset_frames = librosa.onset.onset_detect(
        y=y,
        sr=sr,
        backtrack=True,
        delta=onset_cfg.get("delta", 0.06),
        wait=onset_cfg.get("wait", 2),
        pre_max=onset_cfg.get("pre_max", 3),
        post_max=onset_cfg.get("post_max", 3),
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    window = float(audio_cfg.get("strike_window_seconds", 0.25))
    win_samples = int(window * sr)
    strikes: list[Strike] = []
    for t in onset_times:
        start = int(t * sr)
        seg = y[start : start + win_samples]
        if len(seg) < win_samples // 4:
            continue  # too short (end of file) to be a real strike
        strikes.append(Strike(time=float(t), samples=seg, sr=sr))
    return strikes


def group_phrases(strikes: list[Strike], phrase_gap_seconds: float) -> list[list[Strike]]:
    """Split strikes into phrases wherever the gap exceeds ``phrase_gap_seconds``."""
    phrases: list[list[Strike]] = []
    current: list[Strike] = []
    prev_t: float | None = None
    for s in strikes:
        if prev_t is not None and (s.time - prev_t) > phrase_gap_seconds and current:
            phrases.append(current)
            current = []
        current.append(s)
        prev_t = s.time
    if current:
        phrases.append(current)
    return phrases
