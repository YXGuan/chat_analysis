"""Validate semantic model outputs and conserve counts across hierarchy levels."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "codex_analysis", ROOT / "examples/temporal/codex_analysis.py"
)
analysis_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis_module)


@pytest.mark.parametrize(
    "sample,source,count",
    [
        ("personal", "examples/temporal/sample/conversations.jsonl", 122),
        (
            "research",
            "examples/temporal/reference-research/gpt-6-luna/conversations.jsonl",
            120,
        ),
    ],
)
def test_luna_analysis_covers_exact_source_and_conserves_both_levels(
    sample, source, count
):
    chats = analysis_module.read_chats(ROOT / source)
    result = json.loads((ROOT / f"data/analysis/{sample}.gpt-6-luna.json").read_text())
    topics, assignments = analysis_module.validate_analysis(chats, result)
    assert len(assignments) == count == len(chats)
    profile = json.loads((ROOT / f"ui/public/data/{sample}.json").read_text())
    assert profile["analysis"]["model"] == "gpt-6-luna"
    assert profile["analysis"]["execution"] == "codex-session"
    import hashlib

    assert (
        profile["analysis"]["source_sha256"]
        == hashlib.sha256((ROOT / source).read_bytes()).hexdigest()
    )
    assert (
        profile["analysis"]["analysis_sha256"]
        == hashlib.sha256(
            (ROOT / f"data/analysis/{sample}.gpt-6-luna.json").read_bytes()
        ).hexdigest()
    )
    for timeline in (profile, profile["topic_timeline"]):
        assert sum(u["total"] for u in timeline["users"]) == count
        for user in timeline["users"]:
            assert sum(w["total"] for w in user["weeks"]) == user["total"]
            assert all(sum(w["counts"].values()) == w["total"] for w in user["weeks"])
    assert (
        sum(len(c["chats"]) for c in profile["clusters"] if c["parent_id"] is None)
        == count
    )
    assert (
        sum(len(c["chats"]) for c in profile["clusters"] if c["parent_id"] is not None)
        == count
    )
    assert all(
        topics[a["topic_id"]]["parent_id"] is not None for a in assignments.values()
    )
    json.dumps(profile, allow_nan=False)


@pytest.mark.parametrize(
    "corruption", ["duplicate", "missing", "extra", "parent", "confidence", "user"]
)
def test_invalid_model_output_is_rejected(corruption):
    chats = [{"chat_id": "a", "metadata": {"user": "User 1"}}]
    result = {
        "topics": [
            {"id": "root", "parent_id": None, "name": "Root"},
            {"id": "leaf", "parent_id": "root", "name": "Leaf"},
        ],
        "conversations": [{"chat_id": "a", "topic_id": "leaf", "confidence": 0.8}],
        "users": [{"user": "User 1", "summary": "Observed topics"}],
    }
    broken = copy.deepcopy(result)
    if corruption == "duplicate":
        broken["conversations"] *= 2
    elif corruption == "missing":
        broken["conversations"] = []
    elif corruption == "extra":
        broken["conversations"].append(
            {"chat_id": "invented", "topic_id": "leaf", "confidence": 0.8}
        )
    elif corruption == "parent":
        broken["topics"][0]["parent_id"] = "leaf"
    elif corruption == "confidence":
        broken["conversations"][0]["confidence"] = 1.1
    else:
        broken["users"] *= 2
    with pytest.raises(ValueError):
        analysis_module.validate_analysis(chats, broken)
