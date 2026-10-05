"""Instagram 发布通道（RPA）：网页端仅支持图文/Reels 上传入口不稳定。
当前实现：打开 instagram.com 尝试 Reels 上传；若入口不可用则明确返回需人工。
"""
import os
import time

from ...utils.log import get_logger
from .base import PublishChannel
from .rpa_utils import BrowserSession, find_file_input

log = get_logger("rpa_instagram")

UPLOAD_URL = "https://www.instagram.com/"


class InstagramChannel(PublishChannel):
    name = "rpa_instagram"
    platform_key = "instagram"

    def publish(self, platform, content, assets, scripts, scheduled_at):
        headless = self.cfg.headless_active()
        session = BrowserSession(headless=headless)
        try:
            page = session.start(self.platform_key)
            page.goto(UPLOAD_URL, timeout=60000, wait_until="domcontentloaded")
            time.sleep(5)

            if "login" in page.url.lower() or "accounts" in page.url.lower():
                return False, None, "未登录Instagram，请先执行: python main.py login instagram"

            video_path = assets.get("video")
            if not video_path or not os.path.exists(video_path):
                return False, None, "缺少视频文件"

            # 网页端上传入口：点击"创建"按钮
            try:
                create_btn = page.locator("svg[aria-label='New post']").first
                create_btn.wait_for(state="visible", timeout=10000)
                create_btn.click()
                time.sleep(2)
            except Exception:
                return False, None, "Instagram 网页端上传入口不可用（建议人工发布或走官方API）"

            file_input = find_file_input(page)
            if not file_input:
                return False, None, "未找到上传控件"
            file_input.set_input_files(video_path)
            time.sleep(15)

            caption = scripts.get("caption", "")
            tags = scripts.get("tags") or []
            if caption or tags:
                try:
                    editor = page.locator("[contenteditable=true]").first
                    editor.wait_for(state="visible", timeout=15000)
                    editor.click()
                    page.keyboard.type(caption + ("\n" + " ".join(tags) if tags else ""), delay=15)
                except Exception as e:
                    log.warning(f"正文填写失败: {e}")

            session.screenshot(f"ig_before_publish_{content}")

            published = False
            for btn_text in ("Share", "分享"):
                try:
                    btn = page.get_by_role("button", name=btn_text).first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click()
                        published = True
                        break
                except Exception:
                    continue
            if not published:
                return False, None, "未找到 Share 按钮"
            time.sleep(4)
            session.screenshot(f"ig_after_publish_{content}")
            return True, None, None
        except Exception as e:
            log.error(f"Instagram发布异常: {e}")
            return False, None, str(e)
        finally:
            session.close()
