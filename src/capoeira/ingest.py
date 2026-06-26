"""Locate and decode class recordings.

Input layout — **one folder per class** (the user can drop multiple Voice Memos
into the same class folder):

    recordings/
      2026-06-26-angola-intro/
        memo-1.m4a
        memo-2.m4a
      2026-07-03-sao-bento/
        lesson.m4a

A *class* is a subfolder of ``recordings/``. Every audio file inside it is a
memo belonging to that class. Loose audio files placed directly in
``recordings/`` are each treated as their own single-memo class.

Idempotency: each memo is tracked by content hash, so re-running only processes
memos not yet recorded in ``course.json``; adding a new memo to an existing
class folder processes just that memo while still attributing it to the class.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from .deps import require_ffmpeg

AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".aac", ".caf", ".mp4", ".m4v", ".ogg", ".flac"}
_DATE_RE = re.compile(r"(20\d{2})[-_./]?(\d{2})[-_./]?(\d{2})")


def file_hash(path: Path, chunk: int = 1 << 20) -> str:
    """Short content hash used for idempotent processing."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while data := f.read(chunk):
            h.update(data)
    return h.hexdigest()[:16]


def parse_date(name: str, fallback_path: Path | None = None) -> str:
    """Extract YYYY-MM-DD from a folder/file name, else the file's mtime, else today."""
    m = _DATE_RE.search(name)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
        except ValueError:
            pass
    if fallback_path is not None and fallback_path.exists():
        return datetime.fromtimestamp(fallback_path.stat().st_mtime).date().isoformat()
    return date.today().isoformat()


@dataclass
class Memo:
    path: Path
    hash: str = ""

    def __post_init__(self) -> None:
        if not self.hash:
            self.hash = file_hash(self.path)


@dataclass
class ClassRecording:
    class_id: str            # folder name (or file stem for loose files)
    date: str
    memos: list[Memo] = field(default_factory=list)

    @property
    def title(self) -> str:
        """Human-friendly class title derived from the folder name."""
        name = _DATE_RE.sub("", self.class_id).strip(" -_./")
        name = name.replace("-", " ").replace("_", " ").strip()
        return name.title() if name else self.class_id


def _audio_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTS)


def discover_classes(recordings_dir: Path) -> list[ClassRecording]:
    """Return every class found under ``recordings_dir`` (folders + loose files)."""
    recordings_dir = Path(recordings_dir)
    if not recordings_dir.exists():
        return []

    classes: list[ClassRecording] = []

    # One folder per class.
    for sub in sorted(p for p in recordings_dir.iterdir() if p.is_dir()):
        files = _audio_files(sub)
        if not files:
            continue
        classes.append(
            ClassRecording(
                class_id=sub.name,
                date=parse_date(sub.name, files[0]),
                memos=[Memo(path=p) for p in files],
            )
        )

    # Loose audio files placed directly in recordings/ -> one class each.
    for p in _audio_files(recordings_dir):
        classes.append(
            ClassRecording(
                class_id=p.stem,
                date=parse_date(p.stem, p),
                memos=[Memo(path=p)],
            )
        )

    return classes


def to_wav(path: Path, sample_rate: int, out_dir: Path | None = None) -> Path:
    """Decode any audio file to 16 kHz mono WAV via ffmpeg. Returns the wav path."""
    ffmpeg = require_ffmpeg()
    out_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="capoeira_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{path.stem}.{file_hash(path)}.wav"
    if out.exists():
        return out
    subprocess.run(
        [ffmpeg, "-y", "-i", str(path), "-ac", "1", "-ar", str(sample_rate), str(out)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return out
