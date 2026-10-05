"""数据看板：生产/发布统计（status 命令用）"""
from datetime import datetime

from ..db import DB


class Tracker:
    def __init__(self, db: DB):
        self.db = db

    def summary(self) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        # 候选池
        candidates = self.db.list_topics(status="candidate", limit=100)
        approved_today = 0
        for t in self.db.list_topics(limit=500):
            selected_at = t.get("selected_at") or ""
            if str(selected_at).startswith(today):
                approved_today += 1

        queue = self.db.list_queue(limit=500)
        q = {"pending": 0, "success": 0, "failed": 0, "publishing": 0}
        for item in queue:
            st = item["status"]
            q[st] = q.get(st, 0) + 1

        # 今日内容
        today_contents = []
        for c in self.db.conn.execute(
            "SELECT id, topic_id, status, created_at FROM contents ORDER BY id DESC LIMIT 50"
        ).fetchall():
            row = dict(c)
            if row["created_at"].startswith(today):
                today_contents.append(row)

        return {
            "date": today,
            "top_candidates": candidates[:6],
            "candidate_count": len(candidates),
            "approved_today": approved_today,
            "today_contents": today_contents,
            "queue": q,
            "queue_items": queue[:20],
        }
