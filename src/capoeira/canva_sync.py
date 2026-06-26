"""Build the structured payload that drives the living Canva course document.

This module is intentionally integration-agnostic: it turns ``course.json`` into
``output/canva_payload.json`` (ordered sections + the notation PNG paths each
page needs) and makes sure every referenced PNG has been rendered.

The actual Canva design is created/updated from this payload via the Canva
integration available in the assistant session (the design id is stored back in
``course.json`` so updates target the same living document). A later automation
upgrade can POST this same payload to the Canva Connect REST API.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Config
from .course import Course
from .deps import have
from .notation import syllables_for
from .render import render_sequence


def _slug(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "_" for c in text]
    return "".join(keep).strip("_").replace("__", "_") or "toque"


def _rel_to_root(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def ensure_notation_images(cfg: Config, course: Course) -> int:
    """Render any missing notation images referenced by the course. Returns count."""
    rendered = 0
    for toque in course.toques():
        for var in toque.variations:
            if var.notation_png:
                png = cfg.root / var.notation_png
            else:
                png = cfg.notation_dir / f"{_slug(toque.name)}_{_slug('_'.join(var.sequence))}.png"
            svg = png.with_suffix(".svg")
            if not svg.exists() or (have("cairosvg") and not png.exists()):
                render_sequence(
                    var.sequence, svg, title=toque.name,
                    syllables=var.syllables or syllables_for(var.sequence),
                    out_png=png if have("cairosvg") else None,
                )
                rendered += 1
            course.set_variation_png(toque.name, var.sequence, _rel_to_root(png, cfg.root))
    return rendered


def build_payload(cfg: Config, course: Course) -> dict[str, Any]:
    """Assemble the ordered Canva document payload from the course knowledge base."""
    ensure_notation_images(cfg, course)

    toque_pages = []
    for toque in course.toques():
        variations = []
        for i, var in enumerate(toque.variations, start=1):
            syl = var.syllables or syllables_for(var.sequence)
            variations.append({
                "label": "main" if i == 1 else f"variation {i}",
                "sequence": var.sequence,
                "syllables": syl,
                # Ready-to-type text form, so the Canva doc can render notation as
                # typed vector text (symbols over syllables) with no image upload.
                "notation_text": "  ".join(var.sequence),
                "notation_lines": [" ".join(var.sequence), syl],
                # Optional richer asset; ignore if typing the text form instead.
                "notation_png": var.notation_png,
                "notes": var.notes,
                "first_seen": var.first_seen,
            })
        toque_pages.append({
            "name": toque.name,
            "category": toque.category,
            "variations": variations,
        })

    payload = {
        "title": course.data.get("title", "Capoeira Music — Living Course"),
        "notation_key": course.data.get("notation_key", {}),
        "sections": [
            {"type": "title", "title": course.data.get("title", "Capoeira Music — Living Course"),
             "subtitle": "A living course, updated each class"},
            {"type": "notation_key", "title": "Notation Key",
             "entries": course.data.get("notation_key", {})},
            {"type": "toques", "title": "Toques (Rhythms)", "pages": toque_pages},
            {"type": "glossary", "title": "Portuguese-English Glossary",
             "entries": course.data.get("glossary", [])},
            {"type": "instructions", "title": "Playing Instructions",
             "entries": course.data.get("instructions", [])},
            {"type": "culture", "title": "History & Culture",
             "entries": course.data.get("culture", [])},
            {"type": "classes", "title": "Class Log", "entries": course.data.get("classes", [])},
        ],
        "existing_design_id": course.canva_design_id,
    }
    return payload


def write_payload(cfg: Config, course: Course) -> Path:
    """Build the payload and write it to ``output/canva_payload.json``."""
    payload = build_payload(cfg, course)
    out = cfg.output_dir / "canva_payload.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return out
