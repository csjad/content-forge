"""微博发布通道（RPA）：微博发布器上传视频。微博视频上传链路较长，
当前实现：打开发布页 → 上传视频 → 填正文/话题 → 尝试发布；失败则留截图供人工接管。
"""
import os
import time

from ...utils.log import get_logger
from .base import PublishChannel
from .rpa_utils import BrowserSession, find_file_input

log = get_logger("rpa_weibo")

UPLOAD_URL = "https://weibo.com"
COMPOSE_URL = "https://weibo.com/compose"


class WeiboChannel(PublishChannel):
    name = "rpa_weibo"
    platform_key = "weibo"

    def publish(self, platform, content, assets, scripts, scheduled_at):
        headless = self.cfg.headless_active()
        session = BrowserSession(headless=headless)
        try:
            page = session.start(self.platform_key)
            page.goto(UPLOAD_URL, timeout=60000, wait_until="domcontentloaded")
            time.sleep(4)

            if "passport" in page.url.lower() or "login" in page.url.lower():
                return False, None, "未登录微博，请先执行: python main.py login weibo"

            video_path = assets.get("video")
            if not video_path or not os.path.exists(video_path):
                return False, None, "缺少视频文件"
            file_input = find_file_input(page)
            if not file_input:
                log.warning("微博首页无上传控件，尝试打开发布器...")
                page.goto(COMPOSE_URL, timeout=30000)
                time.sleep(3)
                file_input = find_file_input(page)
                if not file_input:
                    return False, None, "微博上传入口定位失败（建议人工发布或走第三方工具）"
            file_input.set_input_files(video_path)
            time.sleep(15)

            body = scripts.get("body", "")
            tags = scripts.get("tags") or []
            try:
                editor = page.locator("[contenteditable=true]").first
                editor.wait_for(state="visible", timeout=10000)
                editor.click()
                page.keyboard.type(body + (" " + " ".join(tags) if tags else ""), delay=15)
            except Exception as e:
                log.warning(f"正文填写失败: {e}")

            session.screenshot(f"weibo_before_publish_{content}")

            published = False
            for btn_text in ("发布", "发送"):
                try:
                    btn = page.get_by_role("button", name=btn_text).first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click()
                        published = True
                        break
                except Exception:
                    continue
            if not published:
                return False, None, "微博发布按钮定位失败，已截图留证（建议人工接管）"
            time.sleep(4)
            session.screenshot(f"weibo_after_publish_{content}")
            return True, None, None
        except Exception as e:
            log.error(f"微博发布异常: {e}")
            return False, None, str(e)
        finally:
            session.close()
