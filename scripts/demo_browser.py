"""演示：弹出真实浏览器窗口，打开指定平台页面并截图存证
用法：python scripts/demo_browser.py douyin
平台：douyin / xiaohongshu / bilibili / weibo / tiktok / instagram / youtube / x
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contentforge.publish.channels.rpa_utils import BrowserSession

PLATFORMS = {
    "douyin": "https://creator.douyin.com/creator-micro/content/upload",
    "xiaohongshu": "https://creator.xiaohongshu.com/publish/publish",
    "bilibili": "https://member.bilibili.com/platform/upload/video/frame",
    "weibo": "https://weibo.com",
    "tiktok": "https://www.tiktok.com/upload",
    "instagram": "https://www.instagram.com/",
    "youtube": "https://studio.youtube.com/",
    "x": "https://x.com/compose/post",
}


def main():
    platform = sys.argv[1] if len(sys.argv) > 1 else "douyin"
    url = PLATFORMS.get(platform)
    if not url:
        print(f"未知平台: {platform}，可用: {', '.join(PLATFORMS)}")
        return
    print(f"弹出真实浏览器，打开 {platform} → {url}")
    session = BrowserSession(headless=False)
    try:
        page = session.start(platform)
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(6)
        print(f"页面标题: {page.title()}")
        print(f"当前URL: {page.url}")
        shot = session.screenshot(f"live_browser_{platform}")
        print(f"截图存证: {shot}")
    finally:
        session.close()
        print("浏览器已关闭")


if __name__ == "__main__":
    main()
