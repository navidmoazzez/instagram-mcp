from __future__ import annotations

from instagram_mcp.store import Store


async def test_movement_reports_the_delta_between_readings(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    await store.record_media("a", [{"id": "m1", "like_count": 10, "comments_count": 1}])
    await store.record_media("a", [{"id": "m1", "like_count": 42, "comments_count": 5}])

    rows = await store.media_movement("a")
    assert len(rows) == 1
    assert rows[0]["likes_gained"] == 32
    assert rows[0]["comments_gained"] == 4
    store.close()


async def test_a_single_reading_produces_no_movement(tmp_path):
    """One reading is not a trend, and reporting it as one would be a lie."""
    store = Store(tmp_path / "db.sqlite")
    await store.record_media("a", [{"id": "m1", "like_count": 10}])
    assert await store.media_movement("a") == []
    store.close()


async def test_profile_history_is_newest_first(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    await store.record_profile("a", {"followers_count": 1})
    await store.record_profile("a", {"followers_count": 2})
    rows = await store.profile_history("a")
    assert [r["followers"] for r in rows] == [2, 1]
    store.close()


async def test_hashtag_ids_are_remembered_so_the_weekly_quota_is_not_spent_twice(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    assert await store.hashtag_id("aitools") is None
    await store.remember_hashtag("AITools", "17843")
    assert await store.hashtag_id("aitools") == "17843"
    assert await store.hashtags_resolved_since("1970-01-01") == 1
    store.close()
