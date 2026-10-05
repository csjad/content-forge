"""发布编排：入队（按平台定时）+ 到期执行（多通道分发 + 重试）
"""
from datetime import datetime, timedelta

from ..db import QUEUE_FAILED, QUEUE_PENDING, QUEUE_PUBLISHING, QUEUE_SUCCESS
from ..utils.log import get_logger

log = get_logger("queue")


def _scheduled_time(publish_time: str) -> str:
    """今天 publish_time，若已过则明天同时刻"""
    now = datetime.now()
    try:
        hh, mm = publish_time.split(":")
        target = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    except Exception:
        target = now.replace(hour=19, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target.strftime("%Y-%m-%d %H:%M:%S")


class PublishQueue:
    def __init__(self, cfg, db, registry):
        self.cfg = cfg
        self.db = db
        self.registry = registry

    def enqueue_for_content(self, content_id: int, scripts: dict) -> list[int]:
        """把内容入队到所有开启的平台"""
        ids = []
        for platform, pcfg in self.cfg.enabled_platforms().items():
            if self.db.queue_has_platform(content_id, platform):
                log.info(f"内容 #{content_id} 已入队过 {platform}，跳过")
                continue
            scheduled = _scheduled_time(pcfg.publish_time)
            channel = pcfg.channel
            qid = self.db.enqueue(content_id, platform, channel, scheduled)
            self.db.log(qid, platform, "enqueue", f"计划发布: {scheduled}")
            ids.append(qid)
            log.info(f"入队 [{platform}] 计划 {scheduled} (queue_id={qid})")
        return ids

    def process_due(self, force: bool = False) -> dict:
        """执行到期发布。force=True 忽略发布时间直接执行全部 pending"""
        result = {"total": 0, "success": 0, "failed": 0, "skipped": 0, "details": []}
        due_items = []
        if force:
            due_items = self.db.list_queue(status=QUEUE_PENDING)
        else:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for item in self.db.list_queue():
                if item["status"] in (QUEUE_PENDING, QUEUE_FAILED) and item["scheduled_at"] <= now:
                    due_items.append(item)
        # 失败项重试检查
        for item in due_items:
            if item["status"] == QUEUE_FAILED and item["attempts"] >= self.cfg.publish.max_retry:
                continue

        result["total"] = len(due_items)
        for item in due_items:
            self.db.bump_attempts(item["id"])
            self.db.set_queue_status(item["id"], QUEUE_PUBLISHING)
            outcome = self._publish_item(item)
            if outcome["ok"]:
                self.db.set_queue_status(item["id"], QUEUE_SUCCESS, url=outcome["url"])
                self.db.log(item["id"], item["platform"], "success", outcome["url"] or "")
                result["success"] += 1
                result["details"].append({"platform": item["platform"], "status": "success"})
            else:
                err = outcome["error"] or "未知错误"
                self.db.log(item["id"], item["platform"], "fail", err)
                self.db.set_queue_status(item["id"], QUEUE_FAILED, error=err)
                result["failed"] += 1
                result["details"].append({"platform": item["platform"], "status": "failed", "error": err})
        return result

    def _publish_item(self, item: dict) -> dict:
        platform = item["platform"]
        content = self.db.get_content(item["content_id"])
        if not content:
            return {"ok": False, "error": f"内容不存在: {item['content_id']}"}
        scripts = (content.get("scripts") or {}).get(platform, {})
        # 素材：取 base 的 video / cover
        assets = {}
        for a in self.db.list_assets(item["content_id"]):
            if a["kind"] in ("video", "cover") and a["platform"] == "base":
                assets[a["kind"]] = a["path"]
        if not assets.get("video"):
            return {"ok": False, "error": "内容尚未产出视频素材"}

        channel = self.registry.get(self._channel_name(platform))
        if channel is None:
            return {"ok": False, "error": f"平台 {platform} 无可用发布通道"}
        try:
            ok, url, err = channel.publish(
                platform=platform,
                content=content,
                assets=assets,
                scripts=scripts,
                scheduled_at=item["scheduled_at"],
            )
            return {"ok": ok, "url": url, "error": err}
        except Exception as e:
            log.error(f"通道执行异常 [{platform}]: {e}")
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _channel_name(platform: str) -> str:
        """platform_key → channel.name 映射（与 factory 注册名一致）"""
        mapping = {
            "douyin": "rpa_douyin",
            "xiaohongshu": "rpa_xiaohongshu",
            "bilibili": "rpa_bilibili",
            "video_account": "manual_video_account",
            "weibo": "rpa_weibo",
            "youtube": "api_youtube",
            "tiktok": "rpa_tiktok",
            "x": "api_x",
            "instagram": "rpa_instagram",
        }
        return mapping.get(platform, platform)
