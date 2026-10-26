"""Build a local temporal Kura report from one or two real WildChat users."""

import argparse
import hashlib
import json
import re
import sys
import webbrowser
from pathlib import Path

# Make direct invocation from any working directory use this checkout.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from kura.temporal import build_temporal_profile  # noqa: E402
from categories import TAXONOMY, assign_categories  # noqa: E402


def read_jsonl(path: Path) -> list[dict]:
    # str.splitlines also splits on valid Unicode separators inside JSON strings.
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, choices=[1, 2], default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--language", default="English")
    parser.add_argument("--min-active-weeks", type=int, default=10)
    parser.add_argument("--min-span-days", type=int, default=84)
    parser.add_argument("--window-weeks", type=int, default=4)
    parser.add_argument("--min-window-chats", type=int, default=5)
    parser.add_argument(
        "--output",
        type=Path,
        help="Results directory; defaults to a directory named for this selection",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Existing Kura conversations.jsonl; skips WildChat downloads",
    )
    parser.add_argument(
        "--assignments",
        type=Path,
        help="JSON object mapping every chat ID to a fixed category name, e.g. a Kura top-level cluster",
    )
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    if (
        args.window_weeks < 1
        or args.min_window_chats < 1
        or args.min_active_weeks < 1
        or args.min_span_days < 0
    ):
        parser.error(
            "Window sizes and chat counts must be positive; span cannot be negative"
        )
    if args.output is None:
        name = (
            "imported"
            if args.input
            else f"wildchat-{args.users}-{args.language.lower()}-seed{args.seed}-w{args.min_active_weeks}-d{args.min_span_days}"
        )
        args.output = Path(__file__).parent / "output" / name
    args.output.mkdir(parents=True, exist_ok=True)
    saved = args.input or args.output / "conversations.jsonl"
    selection = {
        "users": args.users,
        "seed": args.seed,
        "language": args.language,
        "min_active_weeks": args.min_active_weeks,
        "min_span_days": args.min_span_days,
    }
    selection_path = args.output / "selection.json"
    if not args.input and saved.exists() and selection_path.exists():
        if json.loads(selection_path.read_text()) != selection:
            parser.error(
                "This output has a different saved selection. Choose another --output directory."
            )
    if not args.input and saved.exists() and not selection_path.exists():
        parser.error(
            "Saved conversations have no selection manifest. Use --input to rebuild them explicitly."
        )
    if saved.exists():
        conversations = read_jsonl(saved)
        print(f"Reusing {len(conversations)} conversations from {saved}")
    else:
        if args.input:
            parser.error(f"Input does not exist: {saved}")
        sys.path.insert(0, str(ROOT / "examples" / "local"))
        from wildchat import load_wildchat_users

        chats = load_wildchat_users(
            args.users,
            args.language,
            args.seed,
            ROOT / ".cache" / "wildchat",
            min_active_weeks=args.min_active_weeks,
            min_span_days=args.min_span_days,
        )
        if len({c.metadata["user"] for c in chats}) != args.users:
            parser.error(
                "Could not find enough users for this selection; no report was written"
            )
        conversations = [c.model_dump(mode="json") for c in chats]
        saved.write_text(
            "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in conversations)
        )
        selection_path.write_text(json.dumps(selection, indent=2) + "\n")

    if args.assignments:
        supplied = json.loads(args.assignments.read_text())
        metadata = supplied if isinstance(supplied.get("assignments"), dict) else {}
        assignments = metadata.get("assignments", supplied)
        if not isinstance(assignments, dict) or not all(
            isinstance(c, str) and c for c in assignments.values()
        ):
            parser.error("Assignments must map chat IDs to nonempty category strings")
        category_ids = sorted(set(assignments.values()))
        colors = [c["color"] for c in TAXONOMY]
        taxonomy = [
            {"id": c, "name": c, "color": colors[i % len(colors)]}
            for i, c in enumerate(category_ids)
        ]
        if "taxonomy" in metadata:
            taxonomy = metadata["taxonomy"]
            category_ids = [c["id"] for c in taxonomy]
        if any(not re.fullmatch(r"#[0-9a-fA-F]{6}", c["color"]) for c in taxonomy):
            parser.error("Taxonomy colors must be six-digit hex colors")
        notes = metadata.get("notes", {})
        evidence = {
            chat_id: {
                "category": c,
                "matched_terms": [],
                "method": "provided-labels",
                "label_note": notes.get(chat_id, ""),
            }
            for chat_id, c in assignments.items()
        }
        method = "Provided labels" + (
            " · " + metadata["method"] if "method" in metadata else ""
        )
    else:
        evidence = assign_categories(conversations)
        assignments = {chat_id: item["category"] for chat_id, item in evidence.items()}
        taxonomy = [{k: c[k] for k in ("id", "name", "color")} for c in TAXONOMY]
        category_ids = [c["id"] for c in taxonomy]
        method = "Keyword baseline · user messages only"
    # Imported sample provenance lives beside its conversations, rather than being
    # replaced by this invocation's default download settings.
    manifest = saved.parent / "selection.json"
    provenance = json.loads(manifest.read_text()) if manifest.exists() else {}
    profile = build_temporal_profile(
        conversations,
        assignments,
        category_ids,
        args.window_weeks,
        args.min_window_chats,
    )
    profile.update(
        {
            "taxonomy": taxonomy,
            "method": method,
            "source": {
                "name": "AllenAI WildChat-4.8M"
                if not args.input or provenance
                else "Imported Kura conversations",
                "url": "https://huggingface.co/datasets/allenai/WildChat-4.8M"
                if not args.input or provenance
                else "",
                "license": "ODC-BY"
                if not args.input or provenance
                else "Not specified",
                "revision": provenance.get("dataset_revision", "main"),
                "selection": provenance,
                "input_sha256": hashlib.sha256(saved.read_bytes()).hexdigest(),
            },
            "chats": {
                c["chat_id"]: {**c, **evidence[c["chat_id"]]} for c in conversations
            },
        }
    )
    (args.output / "profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n"
    )
    (args.output / "assignments.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    )
    template = (Path(__file__).parent / "report_template.html").read_text()
    head, tail = template.split("__TEMPORAL_DATA__")
    payload = json.dumps(profile, ensure_ascii=False).replace("<", "\\u003c")
    report = (args.output / "report.html").resolve()
    report.write_text(head + payload + tail)
    for user in profile["users"]:
        print(
            f"{user['label']}: {user['total']} chats, {user['active_weeks']} active weeks, {user['first'][:10]} to {user['last'][:10]}"
        )
    print(f"Report: {report}")
    if not args.no_open:
        webbrowser.open(report.as_uri())


if __name__ == "__main__":
    main()
