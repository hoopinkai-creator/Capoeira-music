"""Command-line interface for the Capoeira Music pipeline.

    capoeira status                       # summarise the living course
    capoeira process [CLASS_ID]           # process recordings -> update course
    capoeira render                       # (re)render all notation images
    capoeira canva-sync                   # build the Canva payload
    capoeira calibrate extract <INPUT>    # save strike clips to label
    capoeira calibrate label              # label pending clips interactively
    capoeira calibrate train              # train the strike classifier
"""
from __future__ import annotations

import click

from .config import Config
from .course import Course
from .deps import have, have_ffmpeg


def _course(cfg: Config) -> Course:
    return Course.load(cfg.course_json)


@click.group()
@click.option("--config", "config_path", default=None, help="Path to config.yaml")
@click.pass_context
def cli(ctx: click.Context, config_path: str | None) -> None:
    """Turn recorded Capoeira classes into notation + a living course."""
    ctx.obj = Config.load(config_path)


@cli.command()
@click.pass_obj
def status(cfg: Config) -> None:
    """Show a summary of the living course."""
    course = _course(cfg)
    d = course.data
    click.echo(f"Course: {d.get('title')}")
    click.echo(f"  Toques:       {len(d['toques'])} "
               f"({sum(len(t['variations']) for t in d['toques'])} variations)")
    click.echo(f"  Glossary:     {len(d['glossary'])} terms")
    click.echo(f"  Instructions: {len(d['instructions'])}")
    click.echo(f"  Culture:      {len(d['culture'])}")
    click.echo(f"  Classes:      {len(d['classes'])}")
    click.echo(f"  Canva design: {course.canva_design_id or '(not yet created)'}")
    click.echo("")
    click.echo("Environment:")
    click.echo(f"  ffmpeg:        {'yes' if have_ffmpeg() else 'NO (needed for audio)'}")
    click.echo(f"  librosa:       {'yes' if have('librosa') else 'no  (pip install .[audio])'}")
    click.echo(f"  faster-whisper:{'yes' if have('faster_whisper') else ' no (pip install .[speech])'}")
    click.echo(f"  cairosvg:      {'yes' if have('cairosvg') else 'no  (pip install .[render])'}")


@cli.command()
@click.argument("class_id", required=False)
@click.pass_obj
def process(cfg: Config, class_id: str | None) -> None:
    """Process recordings (all classes, or one CLASS_ID) and update the course."""
    from .ingest import discover_classes
    from .pipeline import process_class

    course = _course(cfg)
    classes = discover_classes(cfg.recordings_dir)
    if class_id:
        classes = [c for c in classes if c.class_id == class_id]
    if not classes:
        click.echo(f"No recordings found under {cfg.recordings_dir}/")
        click.echo("Create one folder per class, e.g. recordings/2026-06-26-angola/memo.m4a")
        return

    for rec in classes:
        click.echo(f"\n=> {rec.class_id}  ({rec.date}, {len(rec.memos)} memo(s))")
        result = process_class(cfg, course, rec)
        if result.classifier_mode:
            click.echo(f"   classifier: {result.classifier_mode}")
        click.echo(f"   sequences:  +{result.sequences_added} new, "
                   f"{result.sequences_duplicate} duplicate")
        click.echo(f"   glossary:   +{result.glossary_added}   "
                   f"instructions: +{result.instructions_added}   "
                   f"culture: +{result.culture_added}")
        for w in result.warnings:
            click.echo(f"   ! {w}")

    course.save()
    click.echo(f"\nSaved {cfg.course_json}")


@cli.command()
@click.pass_obj
def render(cfg: Config) -> None:
    """(Re)render all notation images referenced by the course."""
    from .canva_sync import ensure_notation_images

    course = _course(cfg)
    n = ensure_notation_images(cfg, course)
    course.save()
    click.echo(f"Rendered {n} notation image(s) into {cfg.notation_dir}/")


@cli.command(name="canva-sync")
@click.pass_obj
def canva_sync(cfg: Config) -> None:
    """Build the Canva payload (then the Canva integration updates the design)."""
    from .canva_sync import write_payload

    course = _course(cfg)
    out = write_payload(cfg, course)
    course.save()
    click.echo(f"Wrote Canva payload: {out}")
    click.echo("Next: hand this payload to the Canva integration to create/update the design.")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Bind address")
@click.option("--port", default=8000, type=int, help="Port")
@click.pass_context
def serve(ctx: click.Context, host: str, port: int) -> None:
    """Serve the living-course web UI on http://localhost:<port>."""
    from .webapp import serve as _serve

    click.echo(f"Serving Capoeira course UI on http://localhost:{port}  (Ctrl-C to stop)")
    _serve(host=host, port=port, config_path=ctx.parent.params.get("config_path"))


@cli.group()
def calibrate() -> None:
    """Label real strikes and train the rhythm classifier."""


@calibrate.command("extract")
@click.argument("input_id", required=False)
@click.pass_obj
def calibrate_extract(cfg: Config, input_id: str | None) -> None:
    """Detect strikes in recordings and save clips to label."""
    from .calibrate import extract_class
    from .ingest import discover_classes

    classes = discover_classes(cfg.recordings_dir)
    if input_id:
        classes = [c for c in classes if c.class_id == input_id]
    if not classes:
        click.echo("No recordings found to extract from.")
        return
    total = sum(extract_class(cfg, rec) for rec in classes)
    click.echo(f"Saved {total} strike clip(s) to {cfg.calibration_dir}/")
    click.echo("Next: 'capoeira calibrate label' to label them.")


@calibrate.command("label")
@click.pass_obj
def calibrate_label(cfg: Config) -> None:
    """Interactively label pending strike clips."""
    from .calibrate import label_interactive, pending

    if not pending(cfg):
        click.echo("No pending clips. Run 'capoeira calibrate extract' first.")
        return
    n = label_interactive(cfg)
    click.echo(f"\nLabeled {n} clip(s). Run 'capoeira calibrate train' next.")


@calibrate.command("cluster")
@click.argument("class_id")
@click.option("-k", "n_clusters", default=3, type=int, help="Number of sound clusters")
@click.pass_obj
def calibrate_cluster(cfg: Config, class_id: str, n_clusters: int) -> None:
    """Group a class's strikes into K sounds and export one audio sample per cluster."""
    from .calibrate import cluster_strikes
    from .ingest import discover_classes

    rec = next((c for c in discover_classes(cfg.recordings_dir) if c.class_id == class_id), None)
    if rec is None:
        click.echo(f"No class folder named {class_id} under {cfg.recordings_dir}/")
        return
    reps = cluster_strikes(cfg, rec, k=n_clusters)
    for r in reps:
        click.echo(f"  cluster {r['cluster']}: {r['size']} strikes  ->  {r['wav']}")
    click.echo("\nListen to each sample, then label them, e.g.:")
    click.echo(f"  capoeira calibrate label-clusters {class_id} 0=chi 1=tom 2=tim")


@calibrate.command("label-clusters")
@click.argument("class_id")
@click.argument("labels", nargs=-1)  # e.g. 0=chi 1=tom 2=tim
@click.pass_obj
def calibrate_label_clusters(cfg: Config, class_id: str, labels: tuple[str, ...]) -> None:
    """Assign chi/tom/tim to clusters and train the classifier from them."""
    from .calibrate import train_from_cluster_labels

    mapping: dict[int, str] = {}
    for pair in labels:
        if "=" not in pair:
            click.echo(f"Bad label '{pair}', expected like 0=chi"); return
        idx, lab = pair.split("=", 1)
        mapping[int(idx)] = lab.strip().lower()
    report = train_from_cluster_labels(cfg, class_id, mapping)
    if not report.get("trained"):
        click.echo(f"Not trained: {report.get('reason')}"); return
    click.echo(f"Trained on {report['n']} strikes {report['by_label']}")
    click.echo(f"Saved model: {report['model']}.  Now run: capoeira process {class_id}")


@calibrate.command("train")
@click.pass_obj
def calibrate_train(cfg: Config) -> None:
    """Train and save the strike classifier from labeled clips."""
    from .calibrate import train

    report = train(cfg)
    if not report.get("trained"):
        click.echo(f"Not trained: {report.get('reason')}")
        return
    click.echo(f"Trained on {report['n']} strikes {report['by_label']}")
    click.echo(f"Saved model: {report['model']}")


if __name__ == "__main__":  # pragma: no cover
    cli()
