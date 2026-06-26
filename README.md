# Capoeira Music — Notation & Living Course

Turn recorded Capoeira music classes into berimbau **notation** and a **living
course document** that grows after every class.

You record a class with the iPhone Voice Memos app, drop the file(s) into a
class folder, and the pipeline:

1. **Listens to the audio** and detects each berimbau strike, classifying it
   into the notation symbols (`X`, `▽`, `△`, `▲`, `▽ˣ`).
2. **Transcribes the instructor's speech** to capture Brazilian-Portuguese
   terms (with English translations) and spoken instructions + history/culture.
3. **De-duplicates whole rhythms** — a toque is recorded once; genuinely
   different sequences are added as flagged **variations**. (Repeated strikes
   *within* a sequence are always preserved.)
4. **Renders notation** as clean vector images (and a ready-to-type text form).
5. **Maintains a Canva course document** that is updated each class.

## Notation key

| Symbol | Name | Syllable | Berimbau sound |
|:------:|------|:--------:|----------------|
| `X`  | chidão | **chi** | buzz / scratch (dobrão rests lightly on the string) |
| `▽`  | salto  | **tom** | open low tone (string open) |
| `△`  | preso  | **tim** | pressed high tone (dobrão pressed) |
| `▲`  | preso (strong) | **tim** | emphasized pressed high tone |
| `▽ˣ` | hammeron | **tom** | accented strike |

Seed rhythms (from the original class notes):

- **Angola** — `X X ▽ △` — *chi chi tom tim*
- **São Bento Pequeno** — `X X ▲ ▽` — *chi chi tim tom*
- **Angola do brada** — `X X ▽ △ △` — *chi chi tom tim tim*

## Install

The pure-Python core (notation, course, rendering) needs almost nothing. Audio,
speech, and AI features are optional extras.

```bash
pip install -e .                 # core + SVG notation + CLI
pip install -e '.[render]'       # + PNG notation images (cairosvg)
pip install -e '.[audio]'        # + strike detection/classification (librosa, sklearn)
pip install -e '.[speech]'       # + speech-to-text (faster-whisper)
pip install -e '.[ai]'           # + PT->EN translation & note structuring (anthropic)
pip install -e '.[all,dev]'      # everything + pytest

# system dependency for decoding recordings:
#   macOS:  brew install ffmpeg
#   Debian: apt-get install ffmpeg

# for AI features:
export ANTHROPIC_API_KEY=sk-...
```

Check what's available any time:

```bash
capoeira status
```

## Recording layout — one folder per class

Create **one folder per class** under `recordings/`. You can drop **multiple
memos** into the same class folder; they're all treated as that one class. Put a
date in the folder name and it's picked up automatically.

```
recordings/
  2026-06-26-angola-intro/
    part-1.m4a
    part-2.m4a
  2026-07-03-sao-bento/
    lesson.m4a
```

(A loose audio file dropped directly in `recordings/` becomes its own class.)

## Usage

```bash
capoeira process                 # process every class, update data/course.json
capoeira process 2026-06-26-angola-intro   # just one class
capoeira render                  # (re)render all notation images
capoeira canva-sync              # build output/canva_payload.json for Canva
capoeira status                  # summarise the living course
```

Processing is **idempotent**: each memo is tracked by content hash, so
re-running only processes new memos. Add a memo to an existing class folder and
just that memo is processed, still attributed to the class.

### Calibrating the rhythm classifier (recommended)

Classifying berimbau strikes purely from audio is hard, so the classifier is
calibrated on **your** instrument and mic. Out of the box it uses heuristics;
labeling 1–2 classes makes it reliable.

```bash
capoeira calibrate extract 2026-06-26-angola-intro   # save strike clips to label
capoeira calibrate label                              # listen + type chi/tom/tim/accent
capoeira calibrate train                              # train data/models/strike_clf.pkl
```

After training, `capoeira process` automatically uses the trained model
(`capoeira status` / the `process` output shows `classifier: trained`).

## The living course

`data/course.json` is the single source of truth — version-controlled, so every
class is a clean git diff. It holds the toques (with variations), the
Portuguese↔English glossary, playing instructions, history/culture notes, and a
class log. Notation images live in `output/notation/`.

## Canva course document

`capoeira canva-sync` writes `output/canva_payload.json`: ordered sections
(notation key, toques, glossary, instructions, culture, class log). Each toque
variation carries both a **typed-text notation form** (`notation_text` /
`notation_lines` — the symbols over the syllables, no image needed) and an
optional **notation PNG**. The Canva design is created/updated from this payload
via the Canva integration; the design id is stored back in `course.json` so
later classes update the **same** living document.

## How it fits together

```
recordings/<class>/*.m4a
   │ ingest (ffmpeg -> wav, per-class folders, hash dedup)
   ├── AUDIO  : onset detect -> features -> classify -> symbol sequences
   └── SPEECH : faster-whisper -> glossary (PT->EN) + instructions/culture
        │
        ▼ de-dup (whole-sequence) + variation detection
   data/course.json  ── render notation ──► output/notation/*.svg|png
        │
        ▼ canva-sync
   output/canva_payload.json ──► Canva living course document
```

## Notes & limitations

- **Audio classification is experimental.** Speech transcription is used for the
  spoken layer (terms, instructions, culture), not for the rhythm. Calibration
  is what makes strike classification trustworthy.
- Every heavy dependency is optional; missing ones are reported by
  `capoeira status` and the pipeline skips the corresponding track with a
  warning instead of failing.

## Tests

```bash
pip install -e '.[dev]'
pytest
```
