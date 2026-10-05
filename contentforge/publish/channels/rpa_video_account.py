"""视频号发布通道：微信视频号无网页端公开上传入口（仅微信App内），
默认走 manual（人工确认）——系统产出发布包（视频+文案+封面）并给出操作指引。
"""

from ...utils.log import get_logger
from .base import PublishChannel

log = get_logger("video_account")


class VideoAccountChannel(PublishChannel):
    name = "manual_video_account"
    platform_key = "video_account"

    def publish(self, platform, content, assets, scripts, scheduled_at):
        video_path = assets.get("video")
        title = (scripts.get("titles") or [""])[0]
        body = scripts.get("body", "")
        log.warning(
            f"视频号需人工发布: 请将以下内容通过微信【视频号助手】发布\n"
            f"  视频文件: {video_path}\n  标题: {title}\n  简介: {body}"
        )
        return False, None, "视频号无公开API/网页入口，需人工发布（发布包已就绪）"
