"""Check that prospective Git contents exclude private data and local imports."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_MANIFEST = ROOT / "public-data-manifest.json"
PRIVATE_DIRS = {
    ".local",
    ".cache",
    ".codex",
    ".aws",
    ".ssh",
    ".venv",
    ".playwright-mcp",
    ".pytest_cache",
    ".ruff_cache",
}
APPROVED_DEMO_SOURCE = "https://huggingface.co/datasets/allenai/WildChat-4.8M"
APPROVED_CONVERSATIONS = {
    "examples/temporal/sample/conversations.jsonl",
    "examples/temporal/reference-research/gpt-6-luna/conversations.jsonl",
}
APPROVED_ANALYSES = {
    "data/analysis/personal.gpt-6-luna.json",
    "data/analysis/research.gpt-6-luna.json",
}
PRIVATE_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".har",
    ".zip",
    ".tar",
    ".tgz",
    ".gz",
    ".db-wal",
    ".db-shm",
    ".sqlite-wal",
    ".sqlite-shm",
    ".sqlite3-wal",
    ".sqlite3-shm",
}


def main() -> None:
    """Reject private file paths, saved notebook outputs, and private UI profiles."""
    paths = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    problems = []
    approved_data = json.loads(DATA_MANIFEST.read_text())
    for name in sorted(set(filter(None, paths))):
        path = Path(name)
        if (
            PRIVATE_DIRS.intersection(path.parts)
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.suffix in PRIVATE_SUFFIXES
            or name.startswith("data/analysis/")
            and name not in APPROVED_ANALYSES
        ):
            problems.append(f"Private or unreviewed generated file: {name}")
        file = ROOT / path
        if not file.is_file():
            continue
        if (
            name in approved_data
            and hashlib.sha256(file.read_bytes()).hexdigest() != approved_data[name]
        ):
            problems.append(
                f"Reviewed public dataset changed; review before updating its checksum: {name}"
            )
        if path.suffix == ".ipynb":
            cells = json.loads(file.read_text())["cells"]
            if any(
                cell.get("outputs") or cell.get("execution_count") is not None
                for cell in cells
            ):
                problems.append(
                    f"Notebook has saved outputs or execution state: {name}"
                )
        if (
            name.startswith(("ui/public/data/", "kura/static/dist/data/"))
            and path.suffix == ".json"
        ):
            data = json.loads(file.read_text())
            source = data.get("source", {})
            if (
                source.get("kind") == "chatgpt"
                or source.get("url") != APPROVED_DEMO_SOURCE
            ):
                problems.append(
                    f"Public demo has a private or unreviewed source: {name}"
                )
        if name.startswith("examples/") and path.name == "conversations.jsonl":
            if name not in APPROVED_CONVERSATIONS:
                problems.append(f"Unreviewed conversation export: {name}")
    if problems:
        raise SystemExit("\n".join(problems))
    print(
        f"Publication privacy checks passed for {len(set(filter(None, paths)))} candidate files."
    )


if __name__ == "__main__":
    main()
