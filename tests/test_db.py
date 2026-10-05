"""SQLite state store tests: CRUD and status transitions."""
from __future__ import annotations

from contentforge.db import (
    CONTENT_DRAFT,
    DB,
    QUEUE_PENDING,
    TOPIC_APPROVED,
    TOPIC_CANDIDATE,
    TOPIC_DONE,
)


def test_topic_lifecycle(db: DB):
    tid = db.add_topic(
        title="Why students feel anxious",
        summary="summary",
        angle="energy management",
        score=92,
        reason="pain point",
        source="ai",
        direction_snapshot="niche: x",
    )
    assert tid > 0
    topic = db.get_topic(tid)
    assert topic["status"] == TOPIC_CANDIDATE
    assert topic["score"] == 92

    db.set_topic_status(tid, TOPIC_APPROVED)
    assert db.get_topic(tid)["status"] == TOPIC_APPROVED
    db.set_topic_status(tid, TOPIC_DONE)
    assert db.get_topic(tid)["status"] == TOPIC_DONE


def test_topic_dedup(db: DB):
    db.add_topic("Same title", "", "", 80, "", "ai", "snap")
    assert db.topic_exists("Same title")
    assert not db.topic_exists("Different title")


def test_content_and_scripts_roundtrip(db: DB):
    tid = db.add_topic("T", "", "", 90, "", "ai", "snap")
    cid = db.add_content(
        topic_id=tid,
        format="voice_slides",
        hook="hook",
        outline={"script_lines": ["a", "b"]},
        scripts={"douyin": {"titles": ["x"]}},
        direction_snapshot="snap",
    )
    content = db.get_content(cid)
    assert content["outline"]["script_lines"] == ["a", "b"]
    assert content["scripts"]["douyin"]["titles"] == ["x"]
    assert content["status"] == CONTENT_DRAFT
    db.set_content_status(cid, "ready")
    assert db.get_content(cid)["status"] == "ready"


def test_assets(db: DB):
    cid = db.add_content(1, "voice_slides", "h", {}, {}, "s")
    db.add_asset(cid, "video", "/tmp/v.mp4", "base", {"duration": 10})
    db.add_asset(cid, "cover", "/tmp/c.png")
    assets = db.list_assets(cid)
    assert len(assets) == 2
    videos = db.list_assets(cid, kind="video")
    assert len(videos) == 1
    assert videos[0]["path"] == "/tmp/v.mp4"


def test_queue_lifecycle(db: DB):
    cid = db.add_content(1, "voice_slides", "h", {}, {}, "s")
    qid = db.enqueue(cid, "douyin", "rpa", "2026-10-07 19:00:00")
    item = db.get_queue_item(qid)
    assert item["platform"] == "douyin"
    assert item["status"] == QUEUE_PENDING
    assert db.queue_has_platform(cid, "douyin")
    assert not db.queue_has_platform(cid, "youtube")

    db.set_queue_status(qid, "success", url="https://example.com/v")
    done = db.get_queue_item(qid)
    assert done["status"] == "success"
    assert done["url"] == "https://example.com/v"
    assert done["published_at"]


def test_logs(db: DB):
    db.log(1, "douyin", "enqueue", "plan 19:00")
    rows = db.recent_logs()
    assert len(rows) >= 1
    assert rows[0]["action"] == "enqueue"


def test_list_topics_by_status(db: DB):
    db.add_topic("A", "", "", 80, "", "ai", "s")
    db.add_topic("B", "", "", 70, "", "ai", "s")
    cands = db.list_topics(status=TOPIC_CANDIDATE)
    assert len(cands) == 2
    assert cands[0]["score"] >= cands[1]["score"]  # sorted by score desc
