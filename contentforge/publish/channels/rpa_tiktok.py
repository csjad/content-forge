"""TikTok 发布通道（RPA）：studio.tiktok.com 上传视频 + 标题/标签 + 发布
依赖：先 python main.py login tiktok（需可访问 TikTok 的网络环境）
"""
import os
import time

from ...utils.log import get_logger
from .base import PublishChannel
from .rpa_utils import BrowserSession, find_file_input

log = get_logger("rpa_tiktok")

UPLOAD_URL = "https://www.tiktok.com/upload"


class TiktokChannel(PublishChannel):
    name = "rpa_tiktok"
    platform_key = "tiktok"

    def publish(self, platform, content, assets, scripts, scheduled_at):
        headless = self.cfg.headless_active()
        session = BrowserSession(headless=headless)
        try:
            page = session.start(self.platform_key)
            page.goto(UPLOAD_URL, timeout=60000, wait_until="domcontentloaded")
            time.sleep(5)

            if "login" in page.url.lower():
                return False, None, "未登录TikTok，请先执行: python main.py login tiktok"

            video_path = assets.get("video")
            if not video_path or not os.path.exists(video_path):
                return False, None, "缺少视频文件"
            file_input = find_file_input(page)
            if not file_input:
                return False, None, "未找到上传控件"
            file_input.set_input_files(video_path)
            log.info("视频已提交上传，等待上传完成...")
            time.sleep(20)

            title = (scripts.get("titles") or [""])[0]
            if title:
                try:
                    editor = page.locator("[contenteditable=true]").first
                    editor.wait_for(state="visible", timeout=15000)
                    editor.click()
                    page.keyboard.type(title, delay=20)
                except Exception as e:
                    log.warning(f"标题填写失败: {e}")

            tags = scripts.get("tags") or []
            if tags:
                try:
                    editor = page.locator("[contenteditable=true]").first
                    editor.click()
                    page.keyboard.type(" " + " ".join(tags), delay=20)
                except Exception as e:
                    log.warning(f"标签填写失败: {e}")

            session.screenshot(f"tiktok_before_publish_{content}")

            published = False
            for btn_text in ("Post", "发布"):
                try:
                    btn = page.get_by_role("button", name=btn_text).first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click()
                        published = True
                        break
                except Exception:
                    continue
            if not published:
                return False, None, "未找到 Post 按钮"
            time.sleep(5)
            session.screenshot(f"tiktok_after_publish_{content}")
            return True, None, None
        except Exception as e:
            log.error(f"TikTok发布异常: {e}")
            return False, None, str(e)
        finally:
            session.close()
