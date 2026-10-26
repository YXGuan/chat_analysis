"""Check exact-model headless boundaries and large-export ID conservation."""

import json
import re
from pathlib import Path


from kura import analysis
from kura.codex import DEFAULT_ENGINE, DEFAULT_MODEL, run_json


def test_headless_command_is_exact_model_isolated_and_structured(tmp_path, monkeypatch):
    captured = {}

    class Process:
        pid = 123
        returncode = 0

        def __init__(self, command, **kwargs):
            captured.update(command=command, **kwargs)
            Path(command[command.index("--output-last-message") + 1]).write_text(
                '{"result": "ok"}'
            )

        def communicate(self, prompt, timeout):
            captured.update(prompt=prompt, timeout=timeout)

    monkeypatch.setattr("kura.codex.codex_binary", lambda: "/test/codex")
    monkeypatch.setattr("kura.codex.subprocess.Popen", Process)
    assert run_json("Synthetic input", {"type": "object"}, tmp_path) == {"result": "ok"}
    command = captured["command"]
    assert DEFAULT_ENGINE == "codex" and DEFAULT_MODEL == "gpt-6-luna"
    assert command[command.index("--model") + 1] == DEFAULT_MODEL
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--ignore-user-config" in command and "--ephemeral" in command
    assert (
        'model_reasoning_effort="low"' in command and 'web_search="disabled"' in command
    )
    assert "--output-schema" in command
    assert captured["start_new_session"] is True
    assert str(captured["cwd"]) != str(tmp_path)


def test_batched_annotations_restore_exact_source_ids_and_retry_missing_entries(
    tmp_path, monkeypatch
):
    chats = [
        {
            "chat_id": f"native-uuid-{i}-long",
            "metadata": {"user": "You"},
            "created_at": "2026-08-01T00:00:00Z",
            "messages": [{"role": "user", "content": f"Synthetic subject {i}"}],
        }
        for i in range(85)
    ]
    taxonomy = {
        "title": "Synthetic history",
        "topics": [
            {
                "id": "root",
                "parent_id": None,
                "name": "Root",
                "description": "Broad subject",
            },
            {
                "id": "leaf",
                "parent_id": "root",
                "name": "Leaf",
                "description": "Specific subject",
            },
        ],
        "users": [{"user": "You", "summary": "Synthetic activity"}],
    }
    calls = []

    def runner(prompt, schema, work, **kwargs):
        calls.append((work.name, kwargs["model"]))
        if work.name == "taxonomy":
            work.mkdir(parents=True, exist_ok=True)
            (work / "analysis.json").write_text(json.dumps(taxonomy))
            return taxonomy
        properties = schema["properties"]["conversations"]["items"]["properties"]
        assert properties["topic_id"]["enum"] == ["leaf"]
        assert all(key.startswith("c") for key in properties["chat_id"]["enum"])
        ids = list(dict.fromkeys(re.findall(r'"chat_id": "(c\d+)"', prompt)))
        if work.name == "batch-001":
            ids = ids[:-1]  # Exercise explicit batch coverage retry.
        return {
            "conversations": [
                {
                    "chat_id": key,
                    "topic_id": "leaf",
                    "summary": "Synthetic summary",
                    "confidence": 0.8,
                    "note": "",
                }
                for key in ids
            ]
        }

    monkeypatch.setattr(analysis, "run_json", runner)
    output = tmp_path / "profile.json"
    profile = analysis.analyze_chats(
        chats,
        output,
        tmp_path / "work",
        source={"name": "Private", "url": "", "license": "Private"},
    )
    assert set(profile["chats"]) == {chat["chat_id"] for chat in chats}
    assert profile["users"][0]["total"] == 85
    assert calls == [
        ("taxonomy", DEFAULT_MODEL),
        ("batch-001", DEFAULT_MODEL),
        ("retry", DEFAULT_MODEL),
        ("batch-002", DEFAULT_MODEL),
        ("batch-003", DEFAULT_MODEL),
    ]
    assert profile["analysis"]["execution"] == "local-codex-cli"
    assert json.loads(output.read_text())["source"]["name"] == "Private"

    calls.clear()
    restored = analysis.analyze_chats(chats, output, tmp_path / "work")
    assert not calls  # A retry reuses validated taxonomy and annotation checkpoints.
    assert set(restored["chats"]) == set(profile["chats"])
