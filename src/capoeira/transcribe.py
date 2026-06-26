"""Speech-to-text for class recordings (faster-whisper).

Rhythm comes from the audio analysis track; transcription exists to capture the
*spoken* layer: Brazilian-Portuguese terms, the instructor's playing
instructions, and history / cultural context. Whisper auto-detects Portuguese
vs English per segment, which we keep so the glossary can pick out PT terms.

faster-whisper runs locally (no API key) and downloads its model on first use.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .deps import require


@dataclass
class Segment:
    start: float
    end: float
    text: str
    language: str = ""


@dataclass
class Transcript:
    segments: list[Segment] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments).strip()

    def language_spans(self, language: str) -> list[Segment]:
        return [s for s in self.segments if s.language == language]


def transcribe(wav_path: Path, speech_cfg: dict[str, Any]) -> Transcript:
    """Transcribe a WAV with faster-whisper. Returns a :class:`Transcript`."""
    fw = require("faster_whisper")
    model_size = speech_cfg.get("whisper_model", "small")
    model = fw.WhisperModel(model_size, device="auto", compute_type="auto")

    # Let whisper auto-detect; we tag each segment's language for the glossary.
    segments, info = model.transcribe(str(wav_path), vad_filter=True, word_timestamps=False)
    default_lang = getattr(info, "language", "") or ""

    out: list[Segment] = []
    for seg in segments:
        out.append(
            Segment(
                start=float(seg.start or 0.0),
                end=float(seg.end or 0.0),
                text=seg.text or "",
                language=getattr(seg, "language", "") or default_lang,
            )
        )
    return Transcript(segments=out)
