"""Exercise the standalone builder with real-world text and supplied labels."""

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_offline_report_preserves_unicode_and_cannot_close_the_data_script(tmp_path):
    text = (
        'Text with Unicode\u2028separator and </script><script>alert("chat")</script>'
    )
    source = tmp_path / "conversations.jsonl"
    chat = {
        "chat_id": "one",
        "created_at": "2024-01-01T00:30:00+02:00",
        "metadata": {"user": "User 1"},
        "messages": [{"role": "user", "content": text}],
    }
    source.write_text(json.dumps(chat, ensure_ascii=False) + "\n")
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"one": "Writing"}))
    output = tmp_path / "report"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "examples/temporal/run.py"),
            "--input",
            str(source),
            "--assignments",
            str(labels),
            "--output",
            str(output),
            "--no-open",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    profile = json.loads((output / "profile.json").read_text())
    assert profile["chats"]["one"]["messages"][0]["content"] == text
    assert profile["users"][0]["weeks"][0]["week"] == "2023-12-25"
    assert profile["users"][0]["first"] == "2023-12-31T22:30:00+00:00"
    html = (output / "report.html").read_text()
    payload = html.split('<script id="temporal-data" type="application/json">')[
        1
    ].split("</script>")[0]
    assert json.loads(payload)["chats"]["one"]["messages"][0]["content"] == text
    assert "</script><script>alert" not in html
    assert profile["source"]["name"] == "Imported Kura conversations"


def test_bundled_real_sample_has_complete_labels_and_usable_windows():
    from kura.temporal import build_temporal_profile

    sample = ROOT / "examples/temporal/sample"
    with (sample / "conversations.jsonl").open() as source:
        chats = [json.loads(line) for line in source]
    labels = json.loads((sample / "labels.json").read_text())
    result = build_temporal_profile(
        chats, labels["assignments"], [c["id"] for c in labels["taxonomy"]]
    )
    assert [u["total"] for u in result["users"]] == [33, 89]
    assert all(
        u["active_weeks"] >= 10 and u["comparison"]["sufficient"]
        for u in result["users"]
    )
    assert len(labels["assignments"]) == len(chats) == 122
    assert len({c["metadata"]["source_user_id"] for c in chats}) == 2
