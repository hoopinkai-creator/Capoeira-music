"""Helpers for optional heavy dependencies.

The pure-Python core never imports these. Audio/speech/AI/render modules call
:func:`require` so a missing extra produces a clear, actionable message instead
of a bare ``ModuleNotFoundError``.
"""
from __future__ import annotations

import importlib
import shutil
from types import ModuleType


_EXTRA_HINTS = {
    "librosa": "audio",
    "soundfile": "audio",
    "numpy": "audio",
    "sklearn": "audio",
    "faster_whisper": "speech",
    "anthropic": "ai",
    "cairosvg": "render",
}


def require(module: str) -> ModuleType:
    """Import ``module`` or raise a helpful error naming the pip extra to install."""
    try:
        return importlib.import_module(module)
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without extras
        extra = _EXTRA_HINTS.get(module.split(".")[0])
        hint = f" Install it with: pip install 'capoeira-music[{extra}]'" if extra else ""
        raise RuntimeError(f"Optional dependency '{module}' is not installed.{hint}") from exc


def have(module: str) -> bool:
    """Return True if ``module`` can be imported."""
    try:
        importlib.import_module(module)
        return True
    except ModuleNotFoundError:
        return False


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def require_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path is None:  # pragma: no cover
        raise RuntimeError(
            "ffmpeg is required to decode recordings. Install it "
            "(e.g. 'apt-get install ffmpeg' or 'brew install ffmpeg')."
        )
    return path
