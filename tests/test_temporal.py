from datetime import datetime, timezone

import pytest

from kura.temporal import build_temporal_profile, compare_windows, week_start


def chat(chat_id, created_at, user="User 1"):
    return {"chat_id": chat_id, "created_at": created_at, "metadata": {"user": user}}


def test_utc_monday_boundary_and_year_change():
    assert week_start("2024-01-01T00:30:00+02:00") == "2023-12-25"
    assert week_start("2023-12-31T23:30:00-02:00") == "2024-01-01"
    assert week_start(datetime(2024, 1, 1, tzinfo=timezone.utc)) == "2024-01-01"
    assert week_start("2024-01-01T01:00:00") == "2024-01-01"


def test_zero_filled_weeks_fixed_categories_and_separate_users():
    chats = [
        chat("a", "2024-01-01"),
        chat("b", "2024-01-15"),
        chat("c", "2024-01-15", "User 2"),
    ]
    data = build_temporal_profile(
        chats, {"a": "code", "b": "writing", "c": "code"}, ["code", "writing"]
    )
    assert data["weeks"] == ["2024-01-01", "2024-01-08", "2024-01-15"]
    one, two = data["users"]
    assert one["weeks"][1] == {
        "week": "2024-01-08",
        "total": 0,
        "counts": {"code": 0, "writing": 0},
        "chat_ids": [],
    }
    assert one["total"] == 2 and two["total"] == 1
    assert all(
        sum(w["counts"].values()) == w["total"]
        for u in data["users"]
        for w in u["weeks"]
    )
    assert two["weeks"][0]["counts"] == {"code": 1, "writing": 0}


def test_window_changes_are_normalized_not_raw_volume():
    weeks = [
        {
            "week": f"week{i}",
            "total": total,
            "counts": {"code": code, "writing": total - code},
        }
        for i, (total, code) in enumerate([(10, 5), (0, 0), (20, 10), (20, 10)])
    ]
    result = compare_windows(weeks, ["code", "writing"], window_weeks=2)
    assert result["sufficient"]
    assert result["early"]["total"] == 10 and result["late"]["total"] == 40
    assert result["shifts"][0]["delta"] == 0
    assert result["shifts"][0]["stable"]


def test_sparse_and_overlapping_windows_do_not_produce_drift_claims():
    weeks = [
        {"week": "2024-01-01", "total": 1, "counts": {"code": 1}},
        {"week": "2024-01-08", "total": 0, "counts": {"code": 0}},
    ]
    result = compare_windows(weeks, ["code"], window_weeks=1)
    assert not result["sufficient"]
    assert result["shifts"][0]["late_share"] is None
    assert result["shifts"][0]["delta"] is None
    assert not compare_windows(weeks, ["code"], window_weeks=2)["sufficient"]


def test_invalid_assignments_and_duplicate_ids_fail_explicitly():
    chats = [chat("a", "2024-01-01")]
    with pytest.raises(ValueError, match="Missing category"):
        build_temporal_profile(chats, {})
    with pytest.raises(ValueError, match="unique"):
        build_temporal_profile(chats * 2, {"a": "code"})
    with pytest.raises(ValueError, match="Category order"):
        build_temporal_profile(chats, {"a": "code"}, ["writing"])
    with pytest.raises(ValueError, match="At least one"):
        build_temporal_profile([], {})
