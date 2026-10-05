#!/usr/bin/env python
"""ContentForge CLI.

Entry point::

    contentforge run --auto
    python main.py status

Commands
--------
init        create directories / database
config      print configuration summary
direction   print the current content direction (persona)
run         produce one full content unit (topics -> script -> video -> queue)
run --auto  auto-pick the highest-scored topic
run --topic N  produce from candidate topic N
topics      list the candidate topic pool
pick N      approve topic N and produce it
publish     run the due publish queue
publish --force   run every pending item immediately
publish --show    open real browser windows during publishing (visible)
login PLAT  one-time login to a platform (saves session state)
status      today's dashboard
logs        recent run logs
"""
from __future__ import annotations

import argparse
import sys

from contentforge.analytics.tracker import Tracker
from contentforge.config import Config
from contentforge.db import DB
from contentforge.pipeline import Pipeline
from contentforge.publish.channels.factory import build_registry
from contentforge.publish.channels.rpa_utils import BrowserSession
from contentforge.publish.queue import PublishQueue
from contentforge.utils.log import get_logger

log = get_logger("cli")

LOGIN_PLATFORMS = {
    "douyin": ("https://creator.douyin.com/creator-micro/content/upload", "抖音"),
    "xiaohongshu": ("https://creator.xiaohongshu.com/publish/publish", "小红书"),
    "bilibili": ("https://member.bilibili.com/platform/upload/video/frame", "B站"),
    "weibo": ("https://weibo.com", "微博"),
    "tiktok": ("https://www.tiktok.com/upload", "TikTok"),
    "instagram": ("https://www.instagram.com/", "Instagram"),
}


def cmd_init():
    db = DB()
    log.info(f"database initialized: {db.path}")
    log.info("layout: data/ = assets & outputs, state/ = status & sessions")
    log.info("next: edit config.yaml (LLM section) then `contentforge run`")


def cmd_config():
    cfg = Config()
    print("=" * 50)
    print("niche:   ", cfg.direction.niche)
    llm_ready = cfg.llm.ready()
    print("LLM:     ", f"{cfg.llm.base_url} / {cfg.llm.model}",
          "" if llm_ready else "（未配置!）")
    print("video:   ", cfg.video.default_format, cfg.video.resolution)
    print("platforms:", ", ".join(cfg.enabled_platforms().keys()))
    print("cadence: ", cfg.forge.cadence, f"daily_target={cfg.forge.daily_target}")
    print("confirm: ", cfg.publish.confirm_before_publish)
    print("=" * 50)
    print("config.yaml is hot-reloaded on each run; switch direction any time.")


def cmd_direction():
    cfg = Config()
    print(cfg.direction.to_prompt())


def _pick_interactive(pipeline: Pipeline) -> int:
    candidates = pipeline.db.list_topics(status="candidate", limit=10)
    if not candidates:
        print("candidate pool empty, generating...")
        pipeline.generate_topics()
        candidates = pipeline.db.list_topics(status="candidate", limit=10)
    print("\n===== candidate pool (score desc) =====")
    for i, t in enumerate(candidates, 1):
        print(f"[{i}] #{t['id']} score {t['score']:.0f} | {t['title']}")
        if t.get("angle"):
            print(f"    angle: {t['angle']}")
    print("=======================================")
    while True:
        try:
            raw = input("pick a number (Enter = highest score / q = quit): ").strip()
            if raw.lower() in ("q", "quit"):
                raise SystemExit("aborted")
            if not raw:
                return max(candidates, key=lambda x: x["score"])["id"]
            idx = int(raw)
            if 1 <= idx <= len(candidates):
                return candidates[idx - 1]["id"]
            print("index out of range")
        except ValueError:
            print("enter a number")


def cmd_run(args):
    pipeline = Pipeline()
    if args.topic:
        result = pipeline.run(topic_id=args.topic)
    elif args.auto:
        result = pipeline.run(auto_pick=True)
    else:
        topic_id = _pick_interactive(pipeline)
        result = pipeline.run(topic_id=topic_id)

    if result.get("need_pick"):
        print(result["message"])
        return

    topic = result["topic"]
    content = result["content"]
    video = result["video"]
    print("\n" + "=" * 56)
    print("content produced")
    print(f"topic:  {topic['title']}")
    print(f"content: #{content['id']} | platform versions: {len(content['scripts'])}")
    print(f"video:  {video['video_path']} ({video['duration']:.0f}s)")
    print(f"cover:  {video['cover_path']}")
    print(f"queue:  {result['platform_count']} platforms")
    for qid in result["queue_ids"]:
        item = pipeline.db.get_queue_item(qid)
        print(f"  - [{item['platform']}] scheduled {item['scheduled_at']}")
    print("=" * 56)
    print("run `contentforge publish` for due items, `contentforge publish --force` for all")


def cmd_topics(args):
    db = DB()
    topics = db.list_topics(status=args.status, limit=50)
    if not topics:
        print("(empty)")
        return
    for t in topics:
        print(f"#{t['id']} [{t['status']}] score {t['score']:.0f} | {t['title']}")
        if t.get("angle"):
            print(f"    angle: {t['angle']}")
        if t.get("reason"):
            print(f"    reason: {t['reason']}")


def cmd_pick(args):
    pipeline = Pipeline()
    try:
        pipeline.pick_topic(args.topic_id)
        print("topic approved, producing...")
        cmd_run_args = argparse.Namespace(topic=args.topic_id, auto=False)
        cmd_run(cmd_run_args)
    except ValueError as e:
        print(f"error: {e}")


def cmd_publish(args):
    cfg = Config()
    if getattr(args, "show", False):
        cfg.headless_override = False  # visible browser windows
    db = DB()
    registry = build_registry(cfg, db)
    queue = PublishQueue(cfg, db, registry)
    result = queue.process_due(force=args.force)
    print(f"publish done: total {result['total']} | ok {result['success']} | failed {result['failed']}")
    for d in result["details"]:
        if d["status"] == "success":
            print(f"  [OK] {d['platform']}")
        else:
            print(f"  [FAIL] {d['platform']}: {d.get('error', '')[:100]}")


def cmd_login(args):
    platform = args.platform
    if platform not in LOGIN_PLATFORMS:
        print(f"supported platforms: {', '.join(LOGIN_PLATFORMS)}")
        return
    url, name = LOGIN_PLATFORMS[platform]
    print(f"opening {name} in a real browser; log in manually (session is saved and reused)")
    session = BrowserSession(headless=False)
    try:
        page = session.start(platform)
        page.goto(url, timeout=90000)
        input("press Enter here after you finish logging in... ")
        session.save_state(platform)
        print(f"session saved for {name}")
    finally:
        session.close()


def cmd_status(args):
    cfg = Config()
    db = DB()
    tracker = Tracker(db)
    s = tracker.summary()
    print(f"===== content forge dashboard · {s['date']} =====")
    print(f"candidates: {s['candidate_count']} | used today: {s['approved_today']}")
    print(f"today contents: {len(s['today_contents'])}")
    for c in s["today_contents"]:
        print(f"  #{c['id']} [{c['status']}] topic={c['topic_id']}")
    print(f"queue: pending={s['queue'].get('pending', 0)} "
          f"success={s['queue'].get('success', 0)} failed={s['queue'].get('failed', 0)}")
    for item in s["queue_items"][:10]:
        print(f"  [{item['platform']}] {item['status']} @ {item['scheduled_at']} "
              f"attempts={item['attempts']} {('| ' + item['url']) if item.get('url') else ''}")
    print("direction:", cfg.direction.niche)


def cmd_logs(args):
    db = DB()
    for row in db.recent_logs(30):
        print(f"{row['created_at']} [{row['platform']}] {row['action']}: {row['detail'][:80]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="ContentForge — one-click content factory")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("init")
    sub.add_parser("config")
    sub.add_parser("direction")

    p_run = sub.add_parser("run")
    p_run.add_argument("--auto", action="store_true", help="auto-pick the highest score")
    p_run.add_argument("--topic", type=int, help="produce from candidate topic id")

    p_topics = sub.add_parser("topics")
    p_topics.add_argument("--status", default="candidate", help="candidate/approved/rejected")

    p_pick = sub.add_parser("pick")
    p_pick.add_argument("topic_id", type=int)

    p_pub = sub.add_parser("publish")
    p_pub.add_argument("--force", action="store_true", help="publish every pending item now")
    p_pub.add_argument("--show", action="store_true", help="visible browser windows")

    p_login = sub.add_parser("login")
    p_login.add_argument("platform", help="douyin/xiaohongshu/bilibili/weibo/tiktok/instagram")

    sub.add_parser("status")
    sub.add_parser("logs")

    args = parser.parse_args()
    handlers = {
        "init": lambda: cmd_init(),
        "config": lambda: cmd_config(),
        "direction": lambda: cmd_direction(),
        "run": lambda: cmd_run(args),
        "topics": lambda: cmd_topics(args),
        "pick": lambda: cmd_pick(args),
        "publish": lambda: cmd_publish(args),
        "login": lambda: cmd_login(args),
        "status": lambda: cmd_status(args),
        "logs": lambda: cmd_logs(args),
    }
    handler = handlers.get(args.cmd)
    if not handler:
        parser.print_help()
        return 0
    try:
        handler()
    except SystemExit as e:
        print(str(e) or "")
        return 0
    except Exception as e:
        log.error(f"command failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
