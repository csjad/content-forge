"""抖音发布通道（RPA）：创作者中心上传视频 + 标题/话题 + 发布
依赖：先运行 python main.py login douyin 完成一次登录
"""
import os
import time

from ...utils.log import get_logger
from .base import PublishChannel
from .rpa_utils import BrowserSession, fill_by_placeholder, find_file_input

log = get_logger("rpa_douyin")

UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"


class DouyinChannel(PublishChannel):
    name = "rpa_douyin"
    platform_key = "douyin"

    def publish(self, platform, content, assets, scripts, scheduled_at):
        headless = self.cfg.headless_active()
        session = BrowserSession(headless=headless)
        try:
            page = session.start(self.platform_key)
            page.goto(UPLOAD_URL, timeout=60000, wait_until="domcontentloaded")
            time.sleep(3)

            # 登录检查
            if "login" in page.url.lower() or "passport" in page.url.lower():
                err = "未登录抖音，请先执行: python main.py login douyin"
                log.error(err)
                return False, None, err

            video_path = assets.get("video")
            if not video_path or not os.path.exists(video_path):
                return False, None, "缺少视频文件"
            file_input = find_file_input(page)
            if not file_input:
                return False, None, "未找到上传控件（页面结构可能变化）"
            file_input.set_input_files(video_path)
            log.info("视频已提交上传，等待上传完成...")
            time.sleep(15)  # 等上传；后续用进度提示优化

            title = (scripts.get("titles") or [""])[0]
            if title:
                fill_by_placeholder(page, "填写作品描述", title)

            # 话题标签
            tags = scripts.get("tags") or []
            if tags:
                tag_text = " ".join(tags)
                try:
                    desc = page.locator("textarea, [contenteditable=true]").first
                    desc.click()
                    page.keyboard.type(" " + tag_text, delay=30)
                except Exception as e:
                    log.warning(f"话题填写失败（不影响主体发布）: {e}")

            evidence = session.screenshot(f"douyin_before_publish_{content}")
            log.info(f"发布前截图: {evidence}")

            # 发布（找不到发布按钮则保存草稿兜底）
            published = False
            for btn_text in ("发布", "发布作品"):
                try:
                    btn = page.get_by_role("button", name=btn_text).first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click()
                        published = True
                        log.info(f"已点击发布按钮: {btn_text}")
                        break
                except Exception:
                    continue
            if not published:
                for btn_text in ("存草稿", "草稿"):
                    try:
                        btn = page.get_by_role("button", name=btn_text).first
                        if btn.count() > 0 and btn.is_visible():
                            btn.click()
                            log.warning("未找到发布按钮，已保存草稿（人工确认后手动发布）")
                            return False, None, "已保存草稿，需人工确认发布"
                    except Exception:
                        continue
                return False, None, "未找到发布按钮"

            time.sleep(5)
            session.screenshot(f"douyin_after_publish_{content}")
            return True, None, None
        except Exception as e:
            log.error(f"抖音发布异常: {e}")
            return False, None, str(e)
        finally:
            session.close()
