"""SQLite state store: topics / contents / assets / publish queue / logs.

Everything persists across restarts so multi-day production and publishing
can be tracked and resumed.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from .utils.log import get_logger
from .utils.paths import get_state_dir

log = get_logger("db")

DB_PATH = Path(os.environ.get("FORGE_DB") or (get_state_dir() / "forge.db"))

# ---------- status constants ----------
TOPIC_CANDIDATE = "candidate"   # waiting to be picked
TOPIC_APPROVED = "approved"     # picked, entering production
TOPIC_REJECTED = "rejected"     # discarded
TOPIC_DONE = "done"             # content produced

CONTENT_DRAFT = "draft"         # script written
CONTENT_READY = "ready"         # assets ready, publishable
CONTENT_FAILED = "failed"

QUEUE_PENDING = "pending"       # queued, not yet due
QUEUE_READY = "ready"           # due, publishable now
QUEUE_PUBLISHING = "publishing"
QUEUE_SUCCESS = "success"
QUEUE_FAILED = "failed"
QUEUE_SKIPPED = "skipped"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class DB:
    def __init__(self, path: str | Path = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self):
        c = self.conn
        c.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            direction_snapshot TEXT,        -- 生成时的方向描述（便于追溯）
            title TEXT NOT NULL,
            summary TEXT,
            angle TEXT,                     -- 切入角度
            score REAL DEFAULT 0,
            reason TEXT,                    -- 评分理由
            source TEXT,                    -- 选题来源：ai / baidu_hot / manual
            status TEXT DEFAULT 'candidate',
            created_at TEXT,
            selected_at TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS contents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER,
            direction_snapshot TEXT,
            format TEXT,                    -- voice_slides / ai_scene / mixed_cut / text
            hook TEXT,                      -- 开头钩子
            outline TEXT,                   -- 结构化大纲（JSON）
            scripts TEXT,                   -- 各平台脚本版本（JSON）
            status TEXT DEFAULT 'draft',
            created_at TEXT,
            produced_at TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER,
            kind TEXT,                      -- video / cover / audio / slide
            platform TEXT DEFAULT 'base',   -- base=通用，或平台名
            path TEXT,
            meta TEXT,                      -- JSON（时长、分辨率等）
            created_at TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS publish_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER,
            platform TEXT,                  -- douyin / xiaohongshu / youtube ...
            status TEXT DEFAULT 'pending',
            channel TEXT,                   -- rpa / api / manual / third_party
            scheduled_at TEXT,              -- 计划发布时间
            published_at TEXT,
            url TEXT,
            attempts INTEGER DEFAULT 0,
            last_error TEXT,
            created_at TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS publish_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            queue_id INTEGER,
            platform TEXT,
            action TEXT,                    -- enqueue / publish / retry / skip / success / fail
            detail TEXT,
            created_at TEXT
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_topics_status ON topics(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_contents_topic ON contents(topic_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON publish_queue(status, scheduled_at)")
        self.conn.commit()

    # ================= 选题 =================
    def add_topic(self, title, summary, angle, score, reason, source, direction_snapshot) -> int:
        cur = self.conn.execute(
            "INSERT INTO topics(direction_snapshot,title,summary,angle,score,reason,source,status,created_at) "
            "VALUES(?,?,?,?,?,?,?,'candidate',?)",
            (direction_snapshot, title, summary, angle, score, reason, source, _now()),
        )
        self.conn.commit()
        return cur.lastrowid

    def topic_exists(self, title: str, window_days: int = 30) -> bool:
        """近 window_days 天内是否出现过相似标题（简单去重）"""
        cur = self.conn.execute(
            "SELECT id FROM topics WHERE title=? AND created_at >= datetime('now', ?)",
            (title, f"-{window_days} days"),
        )
        return cur.fetchone() is not None

    def list_topics(self, status: str | None = None, limit: int = 50):
        if status:
            cur = self.conn.execute(
                "SELECT * FROM topics WHERE status=? ORDER BY score DESC, id DESC LIMIT ?",
                (status, limit),
            )
        else:
            cur = self.conn.execute("SELECT * FROM topics ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]

    def get_topic(self, topic_id: int) -> dict | None:
        cur = self.conn.execute("SELECT * FROM topics WHERE id=?", (topic_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def set_topic_status(self, topic_id: int, status: str):
        self.conn.execute(
            "UPDATE topics SET status=?, selected_at=? WHERE id=?",
            (status, _now() if status == TOPIC_APPROVED else None, topic_id),
        )
        self.conn.commit()

    # ================= 内容 =================
    def add_content(self, topic_id, format, hook, outline, scripts, direction_snapshot) -> int:
        cur = self.conn.execute(
            "INSERT INTO contents(topic_id,direction_snapshot,format,hook,outline,scripts,status,created_at) "
            "VALUES(?,?,?,?,?,?,'draft',?)",
            (topic_id, direction_snapshot, format, hook,
             json.dumps(outline, ensure_ascii=False),
             json.dumps(scripts, ensure_ascii=False), _now()),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_content(self, content_id: int) -> dict | None:
        cur = self.conn.execute("SELECT * FROM contents WHERE id=?", (content_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["outline"] = json.loads(d["outline"]) if d["outline"] else {}
        d["scripts"] = json.loads(d["scripts"]) if d["scripts"] else {}
        return d

    def set_content_status(self, content_id: int, status: str):
        self.conn.execute(
            "UPDATE contents SET status=?, produced_at=? WHERE id=?",
            (status, _now() if status == CONTENT_READY else None, content_id),
        )
        self.conn.commit()

    def update_content_scripts(self, content_id: int, scripts: dict):
        self.conn.execute(
            "UPDATE contents SET scripts=? WHERE id=?",
            (json.dumps(scripts, ensure_ascii=False), content_id),
        )
        self.conn.commit()

    def get_content_by_topic(self, topic_id: int) -> dict | None:
        cur = self.conn.execute("SELECT id FROM contents WHERE topic_id=? ORDER BY id DESC LIMIT 1", (topic_id,))
        row = cur.fetchone()
        return self.get_content(row["id"]) if row else None

    # ================= 素材 =================
    def add_asset(self, content_id, kind, path, platform="base", meta=None) -> int:
        cur = self.conn.execute(
            "INSERT INTO assets(content_id,kind,platform,path,meta,created_at) VALUES(?,?,?,?,?,?)",
            (content_id, kind, platform, path,
             json.dumps(meta or {}, ensure_ascii=False), _now()),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_assets(self, content_id: int, kind: str | None = None):
        if kind:
            cur = self.conn.execute(
                "SELECT * FROM assets WHERE content_id=? AND kind=? ORDER BY id", (content_id, kind))
        else:
            cur = self.conn.execute("SELECT * FROM assets WHERE content_id=? ORDER BY id", (content_id,))
        return [dict(r) for r in cur.fetchall()]

    # ================= 发布队列 =================
    def enqueue(self, content_id, platform, channel, scheduled_at) -> int:
        cur = self.conn.execute(
            "INSERT INTO publish_queue(content_id,platform,status,channel,scheduled_at,created_at) "
            "VALUES(?,?,'pending',?,?,?)",
            (content_id, platform, channel, scheduled_at, _now()),
        )
        self.conn.commit()
        return cur.lastrowid

    def queue_has_platform(self, content_id: int, platform: str) -> bool:
        cur = self.conn.execute(
            "SELECT id FROM publish_queue WHERE content_id=? AND platform=?", (content_id, platform))
        return cur.fetchone() is not None

    def list_queue(self, status: str | None = None, limit: int = 100):
        if status:
            cur = self.conn.execute(
                "SELECT * FROM publish_queue WHERE status=? ORDER BY scheduled_at, id LIMIT ?",
                (status, limit))
        else:
            cur = self.conn.execute(
                "SELECT * FROM publish_queue ORDER BY scheduled_at, id LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]

    def get_queue_item(self, queue_id: int) -> dict | None:
        cur = self.conn.execute("SELECT * FROM publish_queue WHERE id=?", (queue_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def set_queue_status(self, queue_id: int, status: str, url: str | None = None, error: str | None = None):
        fields = [status]
        sql = "UPDATE publish_queue SET status=?"
        if url:
            sql += ", url=?"
            fields.append(url)
        if error:
            sql += ", last_error=?"
            fields.append(error)
        if status == QUEUE_SUCCESS:
            sql += ", published_at=?"
            fields.append(_now())
        sql += " WHERE id=?"
        fields.append(queue_id)
        self.conn.execute(sql, tuple(fields))
        self.conn.commit()

    def bump_attempts(self, queue_id: int):
        self.conn.execute("UPDATE publish_queue SET attempts=attempts+1 WHERE id=?", (queue_id,))
        self.conn.commit()

    # ================= 日志 =================
    def log(self, queue_id, platform, action, detail=""):
        self.conn.execute(
            "INSERT INTO publish_log(queue_id,platform,action,detail,created_at) VALUES(?,?,?,?,?)",
            (queue_id, platform, action, str(detail)[:2000], _now()))
        self.conn.commit()

    def recent_logs(self, limit: int = 50):
        cur = self.conn.execute("SELECT * FROM publish_log ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]

    def close(self):
        self.conn.close()
