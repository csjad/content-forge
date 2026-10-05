"""小红书发布通道（RPA）：创作者中心上传视频 + 标题/正文/话题 + 发布"""
import os
import time

from ...utils.log import get_logger
from .base import PublishChannel
from .rpa_utils import BrowserSession, fill_by_placeholder, find_file_input

log = get_logger("rpa_xhs")

UPLOAD_URL = "https://creator.xiaohongshu.com/publish/publish"


class XiaohongshuChannel(PublishChannel):
    name = "rpa_xiaohongshu"
    platform_key = "xiaohongshu"

    def publish(self, platform, content, assets, scripts, scheduled_at):
        headless = self.cfg.headless_active()
        session = BrowserSession(headless=headless)
        try:
            page = session.start(self.platform_key)
            page.goto(UPLOAD_URL, timeout=60000, wait_until="domcontentloaded")
            time.sleep(4)

            if "login" in page.url.lower() or "passport" in page.url.lower():
                return False, None, "未登录小红书，请先执行: python main.py login xiaohongshu"

            video_path = assets.get("video")
            if not video_path or not os.path.exists(video_path):
                return False, None, "缺少视频文件"
            file_input = find_file_input(page)
            if not file_input:
                return False, None, "未找到上传控件"
            file_input.set_input_files(video_path)
            log.info("视频已提交上传，等待上传完成...")
            time.sleep(15)

            title = (scripts.get("titles") or [""])[0]
            if title:
                fill_by_placeholder(page, "填写标题", title)

            body = scripts.get("body", "")
            tags = scripts.get("tags") or []
            if body or tags:
                try:
                    editor = page.locator("[contenteditable=true]").first
                    editor.wait_for(state="visible", timeout=10000)
                    editor.click()
                    page.keyboard.type(body, delay=10)
                    if tags:
                        page.keyboard.type(" " + " ".join(tags), delay=20)
                except Exception as e:
                    log.warning(f"正文/话题填写失败: {e}")

            session.screenshot(f"xhs_before_publish_{content}")

            published = False
            for btn_text in ("发布",):
                try:
                    btn = page.get_by_role("button", name=btn_text).first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click()
                        published = True
                        break
                except Exception:
                    continue
            if not published:
                return False, None, "未找到发布按钮"
            time.sleep(4)
            session.screenshot(f"xhs_after_publish_{content}")
            return True, None, None
        except Exception as e:
            log.error(f"小红书发布异常: {e}")
            return False, None, str(e)
        finally:
            session.close()
