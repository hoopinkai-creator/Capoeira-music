"""A small Flask web UI for the living Capoeira course.

Run with ``capoeira serve`` (or ``python -m capoeira.webapp``). It shows the
course knowledge base with notation rendered inline as SVG (no image files
needed), lets you upload class snippets into a class folder, and run processing.

Notation is rendered directly from each sequence via :func:`render.build_svg`,
so the dashboard works even without the audio/render extras installed.
"""
from __future__ import annotations

import html
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, url_for

from .config import Config
from .course import Course
from .deps import have, have_ffmpeg
from .notation import SYMBOLS, syllables_for
from .render import build_svg

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Capoeira Music — Living Course</title>
<style>
  :root { --ink:#1a2b6b; --accent:#b5341d; --bg:#fbfaf6; --card:#fff; --muted:#5b6175; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: Georgia, 'Times New Roman', serif; background:var(--bg); color:#1c1c22; }
  header { background:var(--ink); color:#fff; padding:20px 24px; }
  header h1 { margin:0; font-size:24px; }
  header p { margin:4px 0 0; opacity:.85; font-size:14px; }
  .wrap { max-width: 960px; margin: 0 auto; padding: 20px 16px 60px; }
  .badges { margin:12px 0 0; }
  .badge { display:inline-block; font-family:system-ui,sans-serif; font-size:12px;
           padding:3px 9px; border-radius:999px; margin:3px 4px 0 0; }
  .ok { background:#1f7a40; color:#fff; } .no { background:#9a3b2c; color:#fff; }
  h2 { color:var(--ink); border-bottom:2px solid var(--ink); padding-bottom:6px; margin-top:34px; }
  .card { background:var(--card); border:1px solid #e7e3d6; border-radius:10px;
          padding:16px 18px; margin:14px 0; box-shadow:0 1px 2px rgba(0,0,0,.04); }
  .toque-name { font-size:19px; font-weight:bold; color:var(--ink); }
  .cat { font-family:system-ui,sans-serif; font-size:11px; text-transform:uppercase;
         letter-spacing:.04em; color:var(--muted); margin-left:8px; }
  .variation { margin:12px 0; padding:10px 0; border-top:1px dashed #e0dccc; }
  .variation:first-of-type { border-top:none; }
  .vlabel { font-family:system-ui,sans-serif; font-size:12px; color:var(--accent); }
  .notes { color:var(--muted); font-size:14px; margin-top:4px; }
  table { width:100%; border-collapse:collapse; font-size:15px; }
  td { padding:7px 8px; border-bottom:1px solid #eee; vertical-align:top; }
  td.term { font-weight:bold; color:var(--ink); width:34%; }
  ul.notes-list { margin:0; padding-left:20px; } ul.notes-list li { margin:5px 0; }
  .date { font-family:system-ui,sans-serif; font-size:11px; color:var(--muted); }
  form.upload { font-family:system-ui,sans-serif; font-size:14px; }
  form.upload input, form.upload button { font-size:14px; padding:7px 10px; margin:4px 6px 4px 0; }
  button { background:var(--ink); color:#fff; border:none; border-radius:6px; cursor:pointer; }
  button.secondary { background:#fff; color:var(--ink); border:1px solid var(--ink); }
  .flash { background:#fffbe6; border:1px solid #e6d98a; padding:10px 12px; border-radius:8px;
           font-family:system-ui,sans-serif; font-size:14px; margin:12px 0; }
  .empty { color:var(--muted); font-style:italic; }
  .key { display:flex; flex-wrap:wrap; gap:14px; font-family:system-ui,sans-serif; font-size:13px; }
  .key div { display:flex; align-items:center; gap:8px; }
  svg { vertical-align:middle; }
</style>
</head>
<body>
<header>
  <h1>{{ course.title }}</h1>
  <p>A living course, updated each class — served locally.</p>
  <div class="badges">
    {% for name, ok in env %}
      <span class="badge {{ 'ok' if ok else 'no' }}">{{ name }}: {{ 'yes' if ok else 'no' }}</span>
    {% endfor %}
  </div>
</header>
<div class="wrap">

  {% if message %}<div class="flash">{{ message }}</div>{% endif %}

  <h2>Add a class snippet</h2>
  <div class="card">
    <form class="upload" method="post" action="{{ url_for('upload') }}" enctype="multipart/form-data">
      <label>Class folder:
        <input type="text" name="class_id" placeholder="2026-06-26-angola" required>
      </label>
      <input type="file" name="files" accept="audio/*" multiple required>
      <label style="font-family:system-ui,sans-serif;font-size:13px;">
        <input type="checkbox" name="process" value="1" style="margin:0 4px 0 0;"> process now
      </label>
      <button type="submit">Upload</button>
    </form>
    <p class="notes" style="font-family:system-ui,sans-serif;">
      Voice Memos export as .m4a. Multiple files go into the same class.
      Processing needs ffmpeg + the audio/speech extras
      ({{ 'available' if can_process else 'not installed here — upload still works' }}).
    </p>
    {% if classes_on_disk %}
    <form class="upload" method="post" action="{{ url_for('process_route') }}" style="margin-top:8px;">
      <label>Process existing class:
        <select name="class_id">
          {% for c in classes_on_disk %}<option value="{{ c }}">{{ c }}</option>{% endfor %}
        </select>
      </label>
      <button class="secondary" type="submit">Process</button>
    </form>
    {% endif %}
  </div>

  <h2>Notation Key</h2>
  <div class="card">
    <div class="key">
      {% for sym, info in key %}
        <div>{{ info.svg|safe }}<span><b>{{ info.name }}</b>{% if info.syllable %} · “{{ info.syllable }}”{% endif %}<br>
          <span class="date">{{ info.sound }}</span></span></div>
      {% endfor %}
    </div>
  </div>

  <h2>Toques (Rhythms) — {{ course.toques|length }}</h2>
  {% if not course.toques %}<p class="empty">No toques yet.</p>{% endif %}
  {% for t in course.toques %}
    <div class="card">
      <div class="toque-name">{{ t.name }}<span class="cat">{{ t.category }}</span></div>
      {% for v in t.variations %}
        <div class="variation">
          <div class="vlabel">{{ 'main' if loop.first else 'variation ' ~ loop.index }}
            {% if v.first_seen %}· first seen {{ v.first_seen }}{% endif %}</div>
          {{ v.svg|safe }}
          {% if v.notes %}<div class="notes">{{ v.notes }}</div>{% endif %}
        </div>
      {% endfor %}
    </div>
  {% endfor %}

  <h2>Portuguese–English Glossary — {{ course.glossary|length }}</h2>
  <div class="card">
    {% if course.glossary %}
    <table>
      {% for g in course.glossary %}
      <tr><td class="term">{{ g.term }}</td><td>{{ g.english }}
        {% if g.context %}<br><span class="date">{{ g.context }}</span>{% endif %}</td></tr>
      {% endfor %}
    </table>
    {% else %}<p class="empty">No terms yet.</p>{% endif %}
  </div>

  <h2>Playing Instructions — {{ course.instructions|length }}</h2>
  <div class="card">
    {% if course.instructions %}
    <ul class="notes-list">{% for i in course.instructions %}
      <li>{{ i.text }} <span class="date">({{ i.class_date }})</span></li>{% endfor %}</ul>
    {% else %}<p class="empty">No instructions yet.</p>{% endif %}
  </div>

  <h2>History &amp; Culture — {{ course.culture|length }}</h2>
  <div class="card">
    {% if course.culture %}
    <ul class="notes-list">{% for c in course.culture %}
      <li>{{ c.text }} <span class="date">({{ c.class_date }})</span></li>{% endfor %}</ul>
    {% else %}<p class="empty">No notes yet.</p>{% endif %}
  </div>

  <h2>Class Log — {{ course.classes|length }}</h2>
  <div class="card">
    {% if course.classes %}
    <ul class="notes-list">{% for c in course.classes %}
      <li><b>{{ c.date }}</b> — {{ c.file }}{% if c.summary %}: {{ c.summary }}{% endif %}</li>{% endfor %}</ul>
    {% else %}<p class="empty">No classes processed yet.</p>{% endif %}
  </div>

</div>
</body>
</html>
"""


def create_app(config_path: str | None = None) -> Flask:
    app = Flask(__name__)
    cfg = Config.load(config_path)

    def _render(message: str = "") -> str:
        course = Course.load(cfg.course_json)
        d = course.data

        # Attach an inline SVG to every variation + notation-key entry.
        toques = course.toques()
        toque_view = []
        for t in toques:
            vs = []
            for v in t.variations:
                vs.append({
                    "first_seen": v.first_seen,
                    "notes": v.notes,
                    "svg": build_svg(v.sequence, title="", syllables=v.syllables or syllables_for(v.sequence)),
                })
            toque_view.append({"name": t.name, "category": t.category, "variations": vs})

        key = []
        for sym, info in SYMBOLS.items():
            key.append((sym, {
                "name": info["name"], "syllable": info["syllable"], "sound": info["sound"],
                "svg": build_svg([sym], title=""),
            }))

        course_view = {
            "title": d.get("title", "Capoeira Music — Living Course"),
            "toques": toque_view,
            "glossary": d.get("glossary", []),
            "instructions": d.get("instructions", []),
            "culture": d.get("culture", []),
            "classes": d.get("classes", []),
        }
        env = [
            ("ffmpeg", have_ffmpeg()),
            ("librosa", have("librosa")),
            ("faster-whisper", have("faster_whisper")),
            ("cairosvg", have("cairosvg")),
            ("AI", have("anthropic")),
        ]
        from .ingest import discover_classes
        classes_on_disk = [c.class_id for c in discover_classes(cfg.recordings_dir)]
        can_process = have_ffmpeg() and have("librosa")
        return render_template_string(
            PAGE, course=course_view, env=env, key=key, message=message,
            can_process=can_process, classes_on_disk=classes_on_disk,
            url_for=url_for,
        )

    @app.route("/")
    def index():
        return _render(request.args.get("msg", ""))

    @app.route("/upload", methods=["POST"])
    def upload():
        class_id = (request.form.get("class_id") or "").strip()
        files = request.files.getlist("files")
        if not class_id or not files:
            return redirect(url_for("index", msg="Provide a class name and at least one file."))
        dest = cfg.recordings_dir / class_id
        dest.mkdir(parents=True, exist_ok=True)
        saved = 0
        for f in files:
            if not f.filename:
                continue
            f.save(str(dest / Path(f.filename).name))
            saved += 1
        msg = f"Uploaded {saved} file(s) to recordings/{class_id}/."
        if request.form.get("process"):
            msg += " " + _process(cfg, class_id)
        return redirect(url_for("index", msg=msg))

    @app.route("/process", methods=["POST"])
    def process_route():
        class_id = (request.form.get("class_id") or "").strip() or None
        return redirect(url_for("index", msg=_process(cfg, class_id)))

    return app


def _process(cfg: Config, class_id: str | None) -> str:
    """Run the pipeline for a class (or all) and return a short status string."""
    from .ingest import discover_classes
    from .pipeline import process_class

    course = Course.load(cfg.course_json)
    classes = discover_classes(cfg.recordings_dir)
    if class_id:
        classes = [c for c in classes if c.class_id == class_id]
    if not classes:
        return "No matching recordings to process."
    parts = []
    for rec in classes:
        r = process_class(cfg, course, rec)
        parts.append(
            f"{rec.class_id}: +{r.sequences_added} rhythm(s), {r.sequences_duplicate} dup, "
            f"+{r.glossary_added} terms, +{r.instructions_added} instr"
            + (f" [{'; '.join(r.warnings)}]" if r.warnings else "")
        )
    course.save()
    return "Processed — " + " | ".join(parts)


def serve(host: str = "0.0.0.0", port: int = 8000, config_path: str | None = None) -> None:
    create_app(config_path).run(host=host, port=port, debug=False)


if __name__ == "__main__":  # pragma: no cover
    serve()
