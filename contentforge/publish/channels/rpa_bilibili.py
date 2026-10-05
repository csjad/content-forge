"""B站发布通道（RPA）：投稿中心上传视频 + 标题/简介/标签 + 发布"""
import os
import time

from ...utils.log import get_logger
from .base import PublishChannel
from .rpa_utils import BrowserSession, find_file_input

log = get_logger("rpa_bilibili")

UPLOAD_URL = "https://member.bilibili.com/platform/upload/video/frame"


class BilibiliChannel(PublishChannel):
    name = "rpa_bilibili"
    platform_key = "bilibili"

    def publish(self, platform, content, assets, scripts, scheduled_at):
        headless = self.cfg.headless_active()
        session = BrowserSession(headless=headless)
        try:
            page = session.start(self.platform_key)
            page.goto(UPLOAD_URL, timeout=60000, wait_until="domcontentloaded")
            time.sleep(4)

            if "passport" in page.url.lower() or "login" in page.url.lower():
                return False, None, "未登录B站，请先执行: python main.py login bilibili"

            video_path = assets.get("video")
            if not video_path or not os.path.exists(video_path):
                return False, None, "缺少视频文件"
            file_input = find_file_input(page)
            if not file_input:
                return False, None, "未找到上传控件"
            file_input.set_input_files(video_path)
            log.info("视频已提交上传，等待上传完成...")
            time.sleep(20)  # B站上传/转码较慢

            title = (scripts.get("titles") or [""])[0]
            if title:
                try:
                    t = page.locator("input[placeholder*='标题'], input[placeholder*='标题']").first
                    t.wait_for(state="visible", timeout=10000)
                    t.fill(title)
                except Exception as e:
                    log.warning(f"标题填写失败: {e}")

            body = scripts.get("body", "")
            if body:
                try:
                    desc = page.locator("textarea").first
                    desc.wait_for(state="visible", timeout=10000)
                    desc.fill(body)
                except Exception as e:
                    log.warning(f"简介填写失败: {e}")

            tags = scripts.get("tags") or []
            if tags:
                try:
                    tag_input = page.locator("input[placeholder*='标签']").first
                    tag_input.wait_for(state="visible", timeout=10000)
                    for tag in tags:
                        clean = tag.lstrip("#")
                        tag_input.fill(clean)
                        page.keyboard.press("Enter")
                        time.sleep(0.6)
                except Exception as e:
                    log.warning(f"标签填写失败: {e}")

            session.screenshot(f"bili_before_publish_{content}")

            published = False
            for btn_text in ("立即投稿", "发布"):
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
            session.screenshot(f"bili_after_publish_{content}")
            return True, None, None
        except Exception as e:
            log.error(f"B站发布异常: {e}")
            return False, None, str(e)
        finally:
            session.close()
