"""Build a single-file HTML report from Kura's output files.

The report has the data and chart libraries built in, so it opens straight
from disk. There is nothing to upload and no server to run.
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import requests

TEMPLATE = Path(__file__).parent / "report_template.html"
LIBRARIES = {
    "d3-7.9.0.min.js": "https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js",
    "d3-sankey-0.12.3.min.js": "https://cdn.jsdelivr.net/npm/d3-sankey@0.12.3/dist/d3-sankey.min.js",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read one JSON object per line."""
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def _user_order(label: str) -> int:
    """Sort "User 2" before "User 10"."""
    last = label.split()[-1]
    return int(last) if last.isdigit() else 0


def sample_label(folder: str) -> str:
    """Describe a results folder by its name, such as "WildChat, 3 English users"."""
    users = re.fullmatch(r"wildchat-(\d+)-(.+?)-users(?:-about-(.+?))?(?:-seed(\d+))?", folder)
    if users:
        count, language, topic, seed = users.groups()
        label = f"WildChat, {count} {language.title()} {'user' if count == '1' else 'users'}"
        if topic:
            label += f" about {topic.replace('-', ' ')}"
        return f"{label}, seed {seed}" if seed else label
    random_chats = re.fullmatch(r"wildchat-(\d+)", folder)
    if random_chats:
        return f"WildChat, {int(random_chats.group(1)):,} random chats"
    if folder == "synthetic":
        return "Synthetic chats"
    return folder


def _library_tags(cache_dir: Path) -> str:
    """Return script tags for the chart libraries.

    Each library is downloaded once and then built into every report, so
    reports also work offline. If a download fails, the report links to it instead.
    """
    tags = []
    for name, url in LIBRARIES.items():
        path = cache_dir / name
        try:
            if not path.exists():
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(response.text)
            code = path.read_text().replace("</script", "<\\/script")
            tags.append(f"<script>{code}</script>")
        except (OSError, requests.RequestException):
            tags.append(f'<script src="{url}"></script>')
    return "\n".join(tags)


def write_report(output_dir: Path, cache_dir: Path) -> Path:
    """Write report.html into a results folder (output/<sample>/<model>/) and return its path."""
    clusters = _read_jsonl(output_dir / "dimensionality.jsonl")
    summaries = {s["chat_id"]: s for s in _read_jsonl(output_dir / "summaries.jsonl")}
    conversations = _read_jsonl(output_dir / "conversations.jsonl")

    chats = {}
    for conversation in conversations:
        metadata = conversation["metadata"]
        messages = conversation["messages"]
        chats[conversation["chat_id"]] = {
            "user": metadata.get("user"),
            "date": conversation["created_at"][:10],
            "turns": metadata.get("turns") or sum(m["role"] == "user" for m in messages),
            "summary": summaries.get(conversation["chat_id"], {}).get("summary", ""),
            "messages": [[m["role"], m["content"]] for m in messages],
        }

    users = []
    labels = {c["metadata"]["user"] for c in conversations if c["metadata"].get("user")}
    for label in sorted(labels, key=_user_order):
        mine = [c for c in conversations if c["metadata"].get("user") == label]
        dates = sorted(c["created_at"][:10] for c in mine)
        country = Counter(c["metadata"].get("country") or "Unknown" for c in mine).most_common(1)[0][0]
        about = next((c["metadata"]["user_summary"] for c in mine if c["metadata"].get("user_summary")), "")
        users.append({
            "label": label, "chats": len(mine), "first": dates[0], "last": dates[-1],
            "country": country, "about": about,
        })

    data = {
        "title": "Kura cluster report",
        "subtitle": f"{sample_label(output_dir.parent.name)} · {len(conversations):,} chats · {output_dir.name}",
        "users": users,
        "clusters": [
            {
                "id": c["id"],
                "name": c["name"],
                "description": c["description"],
                "parent": c["parent_id"],
                "level": c["level"],
                "x": c["x_coord"],
                "y": c["y_coord"],
                "chats": c["chat_ids"],
            }
            for c in clusters
        ],
        "chats": chats,
    }
    # "<" is escaped so chat text like "</script>" can't end the data block early
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")

    # Split on the placeholders first, so nothing inserted can be mistaken for one
    head, rest = TEMPLATE.read_text().split("__LIBRARIES__")
    middle, tail = rest.split("__KURA_DATA__")
    path = output_dir / "report.html"
    path.write_text(head + _library_tags(cache_dir) + middle + payload + tail)
    return path
