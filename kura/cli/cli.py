"""Run the local app or import a conversation history with headless Codex."""

import json
import os
import time
from pathlib import Path

import typer
import uvicorn

from kura.codex import DEFAULT_MODEL
from kura.imports import ImportStore

app = typer.Typer(no_args_is_help=True)
ROOT = Path(__file__).resolve().parents[2]


@app.command()
def start_app(
    dir: str = typer.Option("./checkpoints", help="Legacy checkpoint directory."),
    checkpoint_format: str = typer.Option("jsonl", help="Legacy checkpoint format."),
    port: int = typer.Option(8014, help="Local application port."),
):
    """Open the local app with private imports and saved histories."""
    os.environ["KURA_CHECKPOINT_DIR"] = dir
    os.environ["KURA_CHECKPOINT_FORMAT"] = checkpoint_format
    print(f"Kura: http://127.0.0.1:{port} · headless Codex · {DEFAULT_MODEL}")
    uvicorn.run("kura.cli.server:api", host="127.0.0.1", port=port)


@app.command()
def import_history(
    path: Path = typer.Argument(
        ..., help="ChatGPT export folder, ZIP, or conversations JSON."
    ),
    months: int = typer.Option(
        3, help="Latest 1, 3, 6, or 12 months in the export; 0 for all history."
    ),
    name: str = typer.Option(
        "My ChatGPT history", help="Name in the dataset selector."
    ),
    prepare_only: bool = typer.Option(
        False, help="Import and preview without contacting a model."
    ),
    data_dir: Path = typer.Option(
        ROOT / ".local/kura", help="Private local storage directory."
    ),
):
    """Import and analyze your own export; GPT-6 Luna through Codex is the default."""
    store = ImportStore(data_dir)
    try:
        preview = store.local(path)
        preview = store.preview(preview["id"], months)
        print(
            f"{preview['selected']} readable conversations · {preview['from'][:10]} through {preview['to'][:10]}"
        )
        print(
            f"{preview['selected_skipped']} conversations skipped without readable user text · {DEFAULT_MODEL} · headless Codex"
        )
        print(f"Saved import: {preview['id']} in {data_dir}")
        if prepare_only:
            print(json.dumps(preview, indent=2))
            return
        job = store.start(preview["id"], months, name)
        previous = None
        while job["stage"] not in ("complete", "failed"):
            if previous != job["stage"]:
                print(job["message"], flush=True)
                previous = job["stage"]
            time.sleep(1)
            job = store.job(job["id"])
        if job["stage"] == "failed":
            raise RuntimeError(job["error"])
        print(
            f"Ready: http://127.0.0.1:8014/?dataset={job['dataset_id']}&view=timeline&user=You"
        )
        print(f"Profile: {store.path('jobs', job['id']) / 'profile.json'}")
    except (ValueError, RuntimeError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from None
    finally:
        store.executor.shutdown(wait=True)


if __name__ == "__main__":
    app()
