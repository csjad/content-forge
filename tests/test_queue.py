"""Publishing queue tests: scheduling, enqueue and fake-channel execution."""
from __future__ import annotations

from contentforge.db import DB, QUEUE_PENDING, QUEUE_SUCCESS
from contentforge.publish.channels.registry import ChannelRegistry
from contentforge.publish.queue import PublishQueue, _scheduled_time


def test_scheduled_time_future_same_day():
    # returns a "YYYY-MM-DD HH:MM:SS" string for the given publish time
    value = _scheduled_time("19:00")
    assert value.split(" ")[0].count("-") == 2  # YYYY-MM-DD
    assert value.split(" ")[1].startswith("19:00")


def test_enqueue_all_platforms(cfg, db: DB):
    from contentforge.publish.channels.factory import build_registry
    registry = build_registry(cfg, db)
    queue = PublishQueue(cfg, db, registry)
    cid = db.add_content(1, "voice_slides", "h", {}, {}, "snap")
    qids = queue.enqueue_for_content(cid, {"douyin": {}})
    assert len(qids) == 3  # douyin / youtube / video_account
    items = db.list_queue()
    assert len(items) == 3
    assert all(i["status"] == QUEUE_PENDING for i in items)


def test_enqueue_deduplicates(cfg, db: DB):
    from contentforge.publish.channels.factory import build_registry
    registry = build_registry(cfg, db)
    queue = PublishQueue(cfg, db, registry)
    cid = db.add_content(1, "voice_slides", "h", {}, {}, "snap")
    queue.enqueue_for_content(cid, {})
    qids = queue.enqueue_for_content(cid, {})
    assert qids == []  # already enqueued


class _FakeChannel:
    name = "rpa_douyin"  # matches PublishQueue._channel_name("douyin")
    result = (True, "https://example.com/p", None)

    def __init__(self, cfg, db):
        pass

    def publish(self, platform, content, assets, scripts, scheduled_at):
        return self.result


def test_process_due_marks_success(cfg, db: DB, monkeypatch):
    registry = ChannelRegistry(cfg, db)
    registry.register(_FakeChannel(cfg, db))
    queue = PublishQueue(cfg, db, registry)
    cid = db.add_content(1, "voice_slides", "h", {}, {}, "snap")
    db.add_asset(cid, "video", "/tmp/v.mp4")
    db.enqueue(cid, "douyin", "rpa", "2020-01-01 00:00:00")  # long past due
    result = queue.process_due()
    assert result["total"] == 1
    assert result["success"] == 1
    item = db.list_queue()[0]
    assert item["status"] == QUEUE_SUCCESS


def test_process_due_force_publishes_all(cfg, db: DB, monkeypatch):
    registry = ChannelRegistry(cfg, db)
    registry.register(_FakeChannel(cfg, db))
    queue = PublishQueue(cfg, db, registry)
    cid = db.add_content(1, "voice_slides", "h", {}, {}, "snap")
    db.add_asset(cid, "video", "/tmp/v.mp4")
    db.enqueue(cid, "douyin", "rpa", "2099-01-01 00:00:00")  # future
    result = queue.process_due(force=True)
    assert result["success"] == 1


def test_process_due_failure_recorded(cfg, db: DB, monkeypatch):
    class _Failing:
        name = "rpa_douyin"

        def __init__(self, cfg, db):
            pass

        def publish(self, *args, **kwargs):
            return False, None, "boom"

    registry = ChannelRegistry(cfg, db)
    registry.register(_Failing(cfg, db))
    queue = PublishQueue(cfg, db, registry)
    cid = db.add_content(1, "voice_slides", "h", {}, {}, "snap")
    db.add_asset(cid, "video", "/tmp/v.mp4")
    db.enqueue(cid, "douyin", "rpa", "2020-01-01 00:00:00")
    result = queue.process_due()
    assert result["failed"] == 1
    item = db.list_queue()[0]
    assert item["status"] == "failed"
    assert "boom" in item["last_error"]
