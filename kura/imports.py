"""Private on-disk imports, durable job status, and saved analysis datasets."""

import hashlib
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from kura.analysis import analyze_chats
from kura.codex import DEFAULT_MODEL
from kura.history import (
    CHATGPT_SOURCE,
    read_export_files,
    read_export_path,
    select_period,
)


def atomic_json(path: Path, value: Any) -> None:
    """Publish a complete JSON file using an atomic replacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


class ImportStore:
    """Keep uploaded text outside the public frontend and reuse saved imports."""

    def __init__(self, root: Path, runner: Callable = analyze_chats):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.runner = runner
        self.executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="kura-analysis"
        )
        self.lock = threading.Lock()
        # A restarted server cannot resume a running CLI process automatically.
        for path in self.root.glob("jobs/*/status.json"):
            job = json.loads(path.read_text())
            if job["stage"] in ("queued", "analyzing", "validating"):
                owner = job.get("owner_pid")
                if owner:
                    try:
                        os.kill(owner, 0)
                        continue
                    except ProcessLookupError:
                        pass
                    except PermissionError:
                        continue
                job.update(
                    stage="failed",
                    error="The local server stopped. Your import is saved; retry analysis.",
                    message="Analysis interrupted",
                )
                atomic_json(path, job)

    def path(self, group: str, key: str) -> Path:
        """Resolve an opaque identifier without accepting user-controlled paths."""
        if not re.fullmatch(r"[a-f0-9]{32}", key):
            raise ValueError("Invalid saved import ID.")
        return self.root / group / key

    def save_import(
        self, chats: list[dict[str, Any]], metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Persist normalized conversation text and return the three-month preview."""
        key = uuid4().hex
        directory = self.path("imports", key)
        directory.mkdir(parents=True)
        (directory / "conversations.jsonl").write_text(
            "".join(json.dumps(chat, ensure_ascii=False) + "\n" for chat in chats)
        )
        atomic_json(directory / "metadata.json", metadata)
        return self.preview(key)

    def upload(self, files: list[tuple[str, bytes]]) -> dict[str, Any]:
        """Import JSON shards or a ZIP without extracting attachment files."""
        return self.save_import(*read_export_files(files))

    def local(self, path: Path) -> dict[str, Any]:
        """Import the conversation files from a user-selected local export path."""
        return self.save_import(*read_export_path(path))

    def read(self, key: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        directory = self.path("imports", key)
        if not (directory / "metadata.json").exists():
            raise ValueError(
                "This saved import was not found. Choose the export again."
            )
        with (directory / "conversations.jsonl").open() as source:
            chats = [json.loads(line) for line in source if line.strip()]
        return chats, json.loads((directory / "metadata.json").read_text())

    def preview(self, key: str, months: int = 3) -> dict[str, Any]:
        """Show full-export and selected-window counts before any model call."""
        chats, metadata = self.read(key)
        _, preview = select_period(chats, metadata, months)
        return {"id": key, **preview, "engine": "codex", "model": DEFAULT_MODEL}

    def start(
        self, key: str, months: int = 3, name: str = "My ChatGPT history"
    ) -> dict[str, Any]:
        """Queue one validated analysis, reusing active or completed identical jobs."""
        chats, metadata = self.read(key)
        selected, preview = select_period(chats, metadata, months)
        if not selected:
            raise ValueError("No readable conversations in this date range.")
        digest = hashlib.sha256(
            json.dumps([selected, DEFAULT_MODEL], sort_keys=True).encode()
        ).hexdigest()
        with self.lock:
            previous = None
            jobs = [
                json.loads(path.read_text())
                for path in self.root.glob("jobs/*/status.json")
            ]
            for job in sorted(jobs, key=lambda job: job["created_at"], reverse=True):
                if job.get("digest") != digest:
                    continue
                if job["stage"] != "failed":
                    return job
                if previous is None:
                    previous = job
            job_id = uuid4().hex
            job = {
                "id": job_id,
                "owner_pid": os.getpid(),
                "work_id": (previous.get("work_id") or previous["id"])
                if previous
                else job_id,
                "import_id": key,
                "dataset_id": job_id,
                "name": name.strip()[:100] or "My ChatGPT history",
                "months": months,
                "stage": "queued",
                "message": "Waiting to start analysis…",
                "error": None,
                "digest": digest,
                "model": DEFAULT_MODEL,
                "engine": "codex",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "preview": preview,
            }
            directory = self.path("jobs", job_id)
            atomic_json(directory / "status.json", job)
            self.executor.submit(self._run, job, selected)
            return job

    def _run(self, job: dict[str, Any], chats: list[dict[str, Any]]) -> None:
        directory = self.path("jobs", job["id"])
        status = directory / "status.json"

        def progress(stage: str, message: str) -> None:
            job.update(stage=stage, message=message)
            atomic_json(status, job)

        try:
            output = directory / "profile.json"
            profile = self.runner(
                chats,
                output,
                self.path("jobs", job.get("work_id", job["id"])),
                source=CHATGPT_SOURCE,
                progress=progress,
            )
            profile["import"] = {
                "name": job["name"],
                "period": job["preview"],
                "kind": "chatgpt",
            }
            atomic_json(output, profile)
            progress(
                "complete",
                f"Ready: {len(chats)} conversations, {len(profile['taxonomy'])} themes.",
            )
        except Exception as error:
            # Never include exception payloads from imported content in the API.
            message = (
                str(error)
                if isinstance(error, (ValueError, RuntimeError))
                else "Analysis failed. Your export is saved; retry analysis."
            )
            job.update(error=message)
            progress("failed", "Analysis could not finish")

    def job(self, key: str) -> dict[str, Any]:
        path = self.path("jobs", key) / "status.json"
        if not path.exists():
            raise ValueError("Analysis job not found.")
        return json.loads(path.read_text())

    def datasets(self) -> list[dict[str, Any]]:
        """List completed private datasets, newest first."""
        jobs = [
            json.loads(path.read_text())
            for path in self.root.glob("jobs/*/status.json")
        ]
        return [
            {
                "id": job["dataset_id"],
                "name": job["name"],
                "created_at": job["created_at"],
                "chats": job["preview"]["selected"],
                "source": "chatgpt",
            }
            for job in sorted(jobs, key=lambda job: job["created_at"], reverse=True)
            if job["stage"] == "complete"
        ]

    def profile(self, key: str) -> dict[str, Any]:
        job = self.job(key)
        if job["stage"] != "complete":
            raise ValueError("This dataset is not ready yet.")
        return json.loads((self.path("jobs", key) / "profile.json").read_text())
