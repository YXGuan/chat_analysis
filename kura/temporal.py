"""Compare fixed conversation categories over calendar weeks.

Category assignments come from the caller, so a Kura cluster hierarchy, reviewed
labels, or a lightweight local classifier can all use the same temporal view.
Naive timestamps in WildChat are interpreted as UTC. Weeks start on Monday.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence


def _utc_timestamp(value: str | datetime) -> datetime:
    stamp = (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, str)
        else value
    )
    return (
        stamp.replace(tzinfo=timezone.utc)
        if stamp.tzinfo is None
        else stamp.astimezone(timezone.utc)
    )


def week_start(value: str | datetime) -> str:
    """Return the UTC Monday containing a timestamp, including offset timestamps."""
    stamp = _utc_timestamp(value)
    return (stamp.date() - timedelta(days=stamp.weekday())).isoformat()


def calendar_weeks(first: str, last: str) -> list[str]:
    """Include every week between two Mondays, even when no chats were recorded."""
    start, end = datetime.fromisoformat(first), datetime.fromisoformat(last)
    return [
        (start + timedelta(weeks=i)).date().isoformat()
        for i in range((end - start).days // 7 + 1)
    ]


def compare_windows(
    weeks: Sequence[Mapping[str, Any]],
    categories: Sequence[str],
    window_weeks: int = 4,
    min_window_chats: int = 5,
) -> dict[str, Any]:
    """Compare shares in non-overlapping first/last calendar windows.

    An empty window is missing evidence, not a zero-interest measurement.
    Changes are percentage points of recorded conversations, not percent growth.
    """
    if window_weeks < 1 or min_window_chats < 1:
        raise ValueError("Window size and minimum chat count must be positive")
    enough_time = len(weeks) >= window_weeks * 2
    early, late = weeks[:window_weeks], weeks[-window_weeks:]
    early_total = sum(w["total"] for w in early)
    late_total = sum(w["total"] for w in late)
    sufficient = enough_time and min(early_total, late_total) >= min_window_chats
    shifts = []
    for category in categories:
        early_count = sum(w["counts"].get(category, 0) for w in early)
        late_count = sum(w["counts"].get(category, 0) for w in late)
        early_share = early_count / early_total if early_total else None
        late_share = late_count / late_total if late_total else None
        delta = late_share - early_share if sufficient else None
        active_weeks = sum(w["counts"].get(category, 0) > 0 for w in weeks)
        shifts.append(
            {
                "category": category,
                "early_count": early_count,
                "late_count": late_count,
                "early_share": early_share,
                "late_share": late_share,
                "delta": delta,
                "active_weeks": active_weeks,
                "stable": sufficient
                and early_count >= 2
                and late_count >= 2
                and abs(delta) <= 0.10,
            }
        )
    return {
        "window_weeks": window_weeks,
        "min_window_chats": min_window_chats,
        "sufficient": sufficient,
        "early": {
            "first": early[0]["week"] if early else None,
            "last": early[-1]["week"] if early else None,
            "total": early_total,
        },
        "late": {
            "first": late[0]["week"] if late else None,
            "last": late[-1]["week"] if late else None,
            "total": late_total,
        },
        "shifts": shifts,
    }


def build_temporal_profile(
    conversations: Sequence[Mapping[str, Any]],
    assignments: Mapping[str, str],
    category_order: Sequence[str] | None = None,
    window_weeks: int = 4,
    min_window_chats: int = 5,
) -> dict[str, Any]:
    """Aggregate one category per chat, keeping user timelines and category IDs fixed."""
    if not conversations:
        raise ValueError("At least one conversation is required")
    ids = [c["chat_id"] for c in conversations]
    if len(set(ids)) != len(ids):
        raise ValueError("Conversation IDs must be unique")
    missing = set(ids) - assignments.keys()
    if missing:
        raise ValueError(
            f"Missing category assignments for {len(missing)} conversations"
        )
    present = {assignments[chat_id] for chat_id in ids}
    categories = list(category_order) if category_order is not None else sorted(present)
    if len(set(categories)) != len(categories) or not present.issubset(categories):
        raise ValueError(
            "Category order must contain every assigned category exactly once"
        )
    if any(not c.get("metadata", {}).get("user") for c in conversations):
        raise ValueError("Every conversation needs a metadata.user label")

    dated = [(c, week_start(c["created_at"])) for c in conversations]
    all_weeks = calendar_weeks(min(w for _, w in dated), max(w for _, w in dated))
    users = []
    for label in sorted({c["metadata"]["user"] for c in conversations}):
        mine = [(c, w) for c, w in dated if c["metadata"]["user"] == label]
        first, last = min(w for _, w in mine), max(w for _, w in mine)
        weekly = []
        for week in calendar_weeks(first, last):
            chats = [c for c, w in mine if w == week]
            counts = Counter(assignments[c["chat_id"]] for c in chats)
            weekly.append(
                {
                    "week": week,
                    "total": len(chats),
                    "counts": {category: counts[category] for category in categories},
                    "chat_ids": [c["chat_id"] for c in chats],
                }
            )
        users.append(
            {
                "label": label,
                "total": len(mine),
                "first": min(
                    _utc_timestamp(c["created_at"]) for c, _ in mine
                ).isoformat(),
                "last": max(
                    _utc_timestamp(c["created_at"]) for c, _ in mine
                ).isoformat(),
                "active_weeks": sum(w["total"] > 0 for w in weekly),
                "weeks": weekly,
                "comparison": compare_windows(
                    weekly, categories, window_weeks, min_window_chats
                ),
            }
        )
    return {"categories": categories, "weeks": all_weeks, "users": users}
