"""The default model boundary: isolated, structured, headless Codex execution."""

import json
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_ENGINE = "codex"
DEFAULT_MODEL = "gpt-6-luna"
CODEX_VERSION = "0.163.0"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DISABLED_FEATURES = (
    "shell_tool",
    "unified_exec",
    "apps",
    "plugins",
    "hooks",
    "multi_agent",
    "browser_use",
    "computer_use",
    "image_generation",
    "skill_search",
    "view_image",
)


def codex_binary() -> str | None:
    """Prefer the explicit binary, then this repo's compatible CLI, then PATH."""
    local = PROJECT_ROOT / ".local/tools/node_modules/.bin/codex"
    return os.environ.get("KURA_CODEX_BIN") or (
        str(local) if local.is_file() else shutil.which("codex")
    )


def run_json(
    prompt: str,
    schema: dict[str, Any],
    work: Path,
    *,
    model: str = DEFAULT_MODEL,
    timeout: int = 1200,
) -> dict[str, Any]:
    """Return schema-constrained output; never substitute a different model."""
    binary = codex_binary()
    if not binary:
        raise RuntimeError(
            "Codex is missing. Run npm run setup:codex in this repo, then codex login."
        )
    if not model or len(model) > 120 or any(char.isspace() for char in model):
        raise ValueError("Choose a valid Codex model ID.")
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    schema_path, result_path = work / "schema.json", work / "analysis.json"
    schema_path.write_text(json.dumps(schema))
    # A fresh cwd avoids loading project instructions alongside untrusted chats.
    with tempfile.TemporaryDirectory(prefix="kura-codex-") as temporary:
        command = [
            binary,
            "exec",
            "--model",
            model,
            "--ignore-user-config",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "-c",
            'model_reasoning_effort="low"',
            "-c",
            'approval_policy="never"',
            "-c",
            'web_search="disabled"',
            "-c",
            "project_doc_max_bytes=0",
        ]
        for feature in DISABLED_FEATURES:
            command.extend(["--disable", feature])
        command.extend(
            [
                "--json",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(result_path),
                "-",
            ]
        )
        with (
            (work / "events.jsonl").open("w") as events,
            (work / "stderr.log").open("w") as errors,
        ):
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=events,
                stderr=errors,
                text=True,
                cwd=temporary,
                start_new_session=True,
            )
            try:
                process.communicate(prompt, timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                raise RuntimeError(
                    "Codex analysis timed out. Your import is saved; retry with a shorter date range."
                ) from None
        if process.returncode:
            diagnostic = (work / "stderr.log").read_text() + (
                work / "events.jsonl"
            ).read_text()
            if any(
                term in diagnostic.lower()
                for term in ("not supported", "model_not_found", "does not exist")
            ):
                raise RuntimeError(
                    f"Codex could not use {model}. Run npm run setup:codex to install the compatible CLI, check codex login status, then retry. No fallback model was used."
                )
            if "401" in diagnostic or "not logged in" in diagnostic.lower():
                raise RuntimeError(
                    "Codex needs a login. Run codex login in your terminal, then retry this saved import."
                )
            raise RuntimeError(
                "Headless Codex failed. Check codex login status, then retry. Your import is saved."
            )
    try:
        result = json.loads(result_path.read_text())
    except (OSError, ValueError):
        raise RuntimeError(
            "Codex did not return valid analysis JSON. Your import is saved; retry analysis."
        ) from None
    if not isinstance(result, dict):
        raise RuntimeError("Codex returned an invalid analysis object.")
    return result
