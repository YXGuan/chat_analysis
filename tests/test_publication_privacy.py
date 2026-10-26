"""Ensure publication checks reject accidental private files and data copies."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "publication_check", ROOT / "scripts/check_publication.py"
)
publication_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publication_check)


@pytest.mark.parametrize(
    "name,contents,error",
    [
        (".local/kura/export.json", "{}", "Private or unreviewed"),
        (
            "ui/public/data/private.json",
            json.dumps({"source": {"kind": "chatgpt"}, "chats": {}}),
            "private or unreviewed source",
        ),
        (
            "notebook.ipynb",
            json.dumps({"cells": [{"outputs": [{"text": "saved output"}]}]}),
            "saved outputs",
        ),
        (
            "ui/public/data/personal.json",
            json.dumps(
                {"source": {"url": publication_check.APPROVED_DEMO_SOURCE}, "chats": {}}
            ),
            "Reviewed public dataset changed",
        ),
    ],
)
def test_publication_check_rejects_private_content(
    tmp_path, monkeypatch, name, contents, error
):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    file = tmp_path / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(contents)
    monkeypatch.setattr(publication_check, "ROOT", tmp_path)
    with pytest.raises(SystemExit, match=error):
        publication_check.main()


def test_publication_check_rejects_forced_tracked_private_files(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".local/\n")
    private = tmp_path / ".local/export.json"
    private.parent.mkdir()
    private.write_text("{}")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "-f", ".local/export.json"], check=True
    )
    monkeypatch.setattr(publication_check, "ROOT", tmp_path)
    with pytest.raises(SystemExit, match="Private or unreviewed"):
        publication_check.main()
