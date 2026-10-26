"""Native export parsing and local job boundaries use only synthetic fixtures."""

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from kura.history import read_export_files, select_period
from kura.imports import ImportStore


def conversation(key="a", date="2026-09-17T12:00:00+00:00", text="Explain a topic"):
    from datetime import datetime

    return {
        "id": key,
        "title": "Synthetic chat",
        "create_time": datetime.fromisoformat(date).timestamp(),
        "current_node": "answer",
        "mapping": {
            "root": {"parent": None, "message": None},
            "user": {
                "parent": "root",
                "message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": [text]},
                },
            },
            "answer": {
                "parent": "user",
                "message": {
                    "author": {"role": "assistant"},
                    "content": {"content_type": "text", "parts": ["Visible answer"]},
                },
            },
            "discarded": {
                "parent": "root",
                "message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["Discarded branch"]},
                },
            },
        },
    }


def export(rows):
    return json.dumps(rows, ensure_ascii=False).encode()


def test_selected_branch_and_text_only_preserve_unicode_and_source_ids(tmp_path):
    row = conversation(text="Unicode\u2028paragraph\u2029and embedded\nnewlines")
    chats, metadata = read_export_files([("conversations.json", export([row]))])
    assert [message["content"] for message in chats[0]["messages"]] == [
        "Unicode\u2028paragraph\u2029and embedded\nnewlines",
        "Visible answer",
    ]
    store = ImportStore(tmp_path)
    try:
        preview = store.save_import(chats, metadata)
        assert store.read(preview["id"])[0] == chats
        assert chats[0]["chat_id"] == "a"
    finally:
        store.executor.shutdown()


def test_shards_and_zip_skip_attachments_and_matching_duplicates():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("nested/conversations-000.json", export([conversation("a")]))
        archive.writestr("nested/conversations-001.json", export([conversation("b")]))
        archive.writestr("nested/image.png", b"attachment")
        archive.writestr("nested/user.json", b"not conversation data")
    chats, metadata = read_export_files(
        [
            ("export.zip", buffer.getvalue()),
            ("conversations.json", export([conversation("a")])),
        ]
    )
    assert len(chats) == 2 and metadata["duplicates"] == 1 and metadata["files"] == 3
    changed = conversation("a", text="Different version")
    with pytest.raises(ValueError, match="different versions"):
        read_export_files([("a.json", export([conversation("a"), changed]))])


def test_month_window_uses_latest_export_date_and_includes_boundary_day():
    rows = [
        conversation("old", "2026-06-16T23:59:59+00:00"),
        conversation("boundary", "2026-06-17T00:00:00+00:00"),
        conversation("latest"),
    ]
    chats, metadata = read_export_files([("conversations.json", export(rows))])
    selected, preview = select_period(chats, metadata, 3)
    assert [chat["chat_id"] for chat in selected] == ["boundary", "latest"]
    assert preview["from"] == "2026-06-17T00:00:00+00:00"
    assert select_period(chats, metadata, 0)[0] == chats
    with pytest.raises(ValueError, match="Choose"):
        select_period(chats, metadata, -1)


def test_month_end_clamps_and_no_text_is_reported():
    rows = [
        conversation("latest", "2026-05-31T12:00:00+00:00"),
        conversation("image", "2026-05-30T12:00:00+00:00"),
    ]
    rows[1]["mapping"]["user"]["message"]["content"] = {
        "content_type": "multimodal_text",
        "parts": [{"asset_pointer": "ignored"}],
    }
    chats, metadata = read_export_files([("conversations.json", export(rows))])
    _, preview = select_period(chats, metadata, 3)
    assert preview["from"].startswith("2026-02-28")
    assert preview["selected_skipped"] == 1 and preview["selected"] == 1


def test_cycles_invalid_files_and_zip_size_are_rejected(monkeypatch):
    broken = conversation()
    broken["mapping"]["user"]["parent"] = "answer"
    with pytest.raises(ValueError, match="broken"):
        read_export_files([("conversations.json", export([broken]))])
    with pytest.raises(ValueError, match="valid JSON"):
        read_export_files([("conversations.json", b"not json")])
    with pytest.raises(ValueError, match="Choose"):
        read_export_files([("other.json", b"{}")])
    # Reject oversize ZIP members by header before reading their JSON.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("conversations.json", export([conversation()]))
    monkeypatch.setattr("kura.history.MAX_EXPORT_BYTES", 100)
    with pytest.raises(ValueError, match="limit"):
        read_export_files([("export.zip", buffer.getvalue())])


def test_api_upload_preview_failure_recovery_and_origin_boundary(tmp_path):
    from kura.cli.server import create_app

    calls = []

    def fail(chats, output, work, **kwargs):
        calls.append(chats)
        raise RuntimeError("Synthetic model unavailable; import saved.")

    store = ImportStore(tmp_path, runner=fail)
    client = TestClient(create_app(store=store))
    try:
        assert client.get("/api/status").json()["model"] == "gpt-6-luna"
        assert (
            client.post(
                "/api/imports/local",
                json={"path": "/anywhere"},
                headers={"origin": "https://example.com"},
            ).status_code
            == 403
        )
        assert client.get("/api/jobs/../private").status_code in (400, 404)
        response = client.post(
            "/api/imports",
            files=[
                (
                    "files",
                    (
                        "conversations.json",
                        export([conversation()]),
                        "application/json",
                    ),
                )
            ],
        )
        assert response.status_code == 200
        preview = response.json()
        assert preview["selected"] == 1
        assert (
            client.get(f"/api/imports/{preview['id']}?months=6").json()["months"] == 6
        )
        result = client.post(
            f"/api/imports/{preview['id']}/analyze",
            json={"months": 3, "name": "Synthetic"},
        ).json()
        store.executor.shutdown(wait=True)
        job = client.get(f"/api/jobs/{result['id']}").json()
        assert job["stage"] == "failed" and "import saved" in job["error"]
        assert len(calls) == 1
        assert client.get(f"/api/imports/{preview['id']}").status_code == 200
        assert client.get("/api/datasets").json() == []
        assert client.get(f"/api/datasets/{result['id']}").status_code == 400
    finally:
        store.executor.shutdown(wait=True)
