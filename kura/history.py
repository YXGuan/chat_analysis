"""Read ChatGPT exports without attachments or discarded conversation branches."""

import calendar
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

MAX_EXPORT_BYTES = 256 * 1024 * 1024
CHATGPT_SOURCE = {
    "name": "Your ChatGPT history",
    "kind": "chatgpt",
    "url": "",
    "license": "Private export",
}


def timestamp(value: Any) -> datetime:
    """Normalize an export timestamp to UTC."""
    if isinstance(value, (float, int)):
        return datetime.fromtimestamp(value, timezone.utc)
    if isinstance(value, str):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (
            result.replace(tzinfo=timezone.utc)
            if result.tzinfo is None
            else result.astimezone(timezone.utc)
        )
    raise ValueError("A conversation is missing a valid date.")


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content") or {}
    if not isinstance(content, dict):
        return ""
    if content.get("content_type") not in (None, "text", "multimodal_text"):
        return ""
    parts = content.get("parts", [])
    texts = [part for part in parts if isinstance(part, str)]
    if not texts and isinstance(content.get("text"), str):
        texts.append(content["text"])
    return "\n".join(texts).strip()


def normalize_conversation(row: dict[str, Any]) -> dict[str, Any] | None:
    """Retain visible user/assistant text on the currently selected branch."""
    mapping = row.get("mapping")
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError("Expected a ChatGPT export with conversation mappings.")
    current = row.get("current_node")
    if current not in mapping:
        parents = {node.get("parent") for node in mapping.values()}
        leaves = [(key, node) for key, node in mapping.items() if key not in parents]
        if not leaves:
            raise ValueError(
                "The export contains a conversation with no readable branch."
            )
        current = max(
            leaves,
            key=lambda pair: (
                (pair[1].get("message") or {}).get("create_time") or 0,
                pair[0],
            ),
        )[0]
    branch: list[dict[str, Any]] = []
    visited: set[str] = set()
    while current is not None:
        if current in visited or current not in mapping:
            raise ValueError("The export contains a broken conversation branch.")
        visited.add(current)
        node = mapping[current]
        message = node.get("message")
        if isinstance(message, dict):
            branch.append(message)
        current = node.get("parent")
    messages = []
    for message in reversed(branch):
        role = (message.get("author") or {}).get("role")
        if role not in ("user", "assistant") or (message.get("metadata") or {}).get(
            "is_visually_hidden_from_conversation"
        ):
            continue
        text = _message_text(message)
        if text:
            messages.append({"role": role, "content": text})
    if not any(message["role"] == "user" for message in messages):
        return None
    chat_id = row.get("conversation_id") or row.get("id")
    if not isinstance(chat_id, str) or not chat_id:
        raise ValueError("A conversation is missing its ID.")
    created = row.get("create_time") or next(
        (m.get("create_time") for m in reversed(branch) if m.get("create_time")), None
    )
    return {
        "chat_id": chat_id,
        "created_at": timestamp(created).isoformat(),
        "metadata": {
            "user": "You",
            "source": "chatgpt",
            "title": str(row.get("title") or "Untitled conversation"),
        },
        "messages": messages,
    }


def read_export_files(
    files: Iterable[tuple[str, bytes]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Combine JSON shards or ZIP exports, deduplicating matching conversations."""
    rows: list[dict[str, Any]] = []
    checksums: list[str] = []
    file_count = 0
    total_bytes = 0

    def read_json(name: str, content: bytes) -> None:
        nonlocal file_count, total_bytes
        total_bytes += len(content)
        if total_bytes > MAX_EXPORT_BYTES:
            raise ValueError("Conversation JSON files exceed the 256 MB import limit.")
        try:
            value = json.loads(content)
        except (ValueError, UnicodeDecodeError) as error:
            raise ValueError(f"{Path(name).name} is not valid JSON.") from error
        if not isinstance(value, list) or any(
            not isinstance(row, dict) for row in value
        ):
            raise ValueError(
                "Choose conversations.json, the conversations-*.json files, or the original export ZIP."
            )
        rows.extend(value)
        checksums.append(hashlib.sha256(content).hexdigest())
        file_count += 1

    for name, content in files:
        if name.lower().endswith(".zip"):
            import io

            try:
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    members = [
                        info
                        for info in archive.infolist()
                        if not info.is_dir()
                        and Path(info.filename).name.startswith("conversations")
                        and info.filename.lower().endswith(".json")
                    ]
                    if (
                        sum(info.file_size for info in members) + total_bytes
                        > MAX_EXPORT_BYTES
                    ):
                        raise ValueError(
                            "Conversation JSON files exceed the 256 MB import limit."
                        )
                    for info in sorted(members, key=lambda info: info.filename):
                        read_json(info.filename, archive.read(info))
            except zipfile.BadZipFile as error:
                raise ValueError("This file is not a readable ZIP export.") from error
        elif name.lower().endswith(".json"):
            read_json(name, content)
        else:
            raise ValueError("Choose a ChatGPT JSON export or ZIP file.")
    if not rows:
        raise ValueError(
            "No conversations found. Choose conversations.json, all conversation shards, or the export ZIP."
        )
    chats: dict[str, dict[str, Any]] = {}
    skipped = duplicates = 0
    dates: list[datetime] = []
    skipped_dates: list[str] = []
    for row in rows:
        if row.get("create_time"):
            dates.append(timestamp(row["create_time"]))
        chat = normalize_conversation(row)
        if chat is None:
            skipped += 1
            if row.get("create_time"):
                skipped_dates.append(timestamp(row["create_time"]).isoformat())
            continue
        existing = chats.get(chat["chat_id"])
        if existing is not None:
            if existing != chat:
                raise ValueError(
                    "Two files contain different versions of the same conversation. Import one export at a time."
                )
            duplicates += 1
        else:
            chats[chat["chat_id"]] = chat
    if not chats:
        raise ValueError(
            "No readable user text was found. Image, audio, and attachment-only chats are skipped."
        )
    ordered = sorted(
        chats.values(), key=lambda chat: (chat["created_at"], chat["chat_id"])
    )
    return ordered, {
        "files": file_count,
        "total": len(rows),
        "readable": len(ordered),
        "skipped": skipped,
        "duplicates": duplicates,
        "skipped_dates": skipped_dates,
        "first": min(dates).isoformat() if dates else ordered[0]["created_at"],
        "last": max(dates).isoformat() if dates else ordered[-1]["created_at"],
        "source_sha256": hashlib.sha256(
            "\n".join(sorted(checksums)).encode()
        ).hexdigest(),
    }


def read_export_path(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load a local export folder, a JSON file, or an export ZIP."""
    path = path.expanduser().resolve()
    if path.is_dir():
        files = sorted(path.glob("conversations*.json"))
        if not files:
            raise ValueError("This folder has no conversations*.json export files.")
    elif path.is_file():
        files = [path]
    else:
        raise ValueError("That export path does not exist.")
    if sum(file.stat().st_size for file in files) > MAX_EXPORT_BYTES:
        raise ValueError(
            "This export exceeds the 256 MB import limit. Choose its conversation JSON files instead."
        )
    return read_export_files((file.name, file.read_bytes()) for file in files)


def select_period(
    chats: list[dict[str, Any]], metadata: dict[str, Any], months: int = 3
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Anchor calendar-month windows to the latest date in the supplied export."""
    if months not in (0, 1, 3, 6, 12):
        raise ValueError("Choose all history, or the latest 1, 3, 6, or 12 months.")
    last = timestamp(metadata["last"])
    if months:
        year, month = divmod(last.year * 12 + last.month - 1 - months, 12)
        first = last.replace(
            year=year,
            month=month + 1,
            day=min(last.day, calendar.monthrange(year, month + 1)[1]),
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    else:
        first = timestamp(metadata["first"])
    selected = [
        chat for chat in chats if first <= timestamp(chat["created_at"]) <= last
    ]
    skipped = sum(
        first <= timestamp(date) <= last for date in metadata.get("skipped_dates", [])
    )
    return selected, {
        **{key: value for key, value in metadata.items() if key != "skipped_dates"},
        "months": months,
        "from": first.isoformat(),
        "to": last.isoformat(),
        "selected": len(selected),
        "selected_skipped": skipped,
        "selected_messages": sum(len(chat["messages"]) for chat in selected),
    }
