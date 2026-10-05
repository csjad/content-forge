"""RPA browser helper: Playwright + system browser (Edge/Chrome).

Owns the browser lifecycle, login-state persistence, page helpers and
screenshot evidence. Login state is stored per platform under
``state/browser/<platform>.json`` so automated publishing reuses your session.
"""
from __future__ import annotations

import os
import time

from playwright.sync_api import sync_playwright

from ...utils.log import get_logger
from ...utils.paths import BROWSER_STATE_DIR, get_data_dir

log = get_logger("rpa")

STATE_DIR = BROWSER_STATE_DIR
EVIDENCE_DIR = get_data_dir() / "publish" / "evidence"

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


class BrowserSession:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.pw = None
        self.browser = None
        self.context = None
        self.page = None

    def start(self, platform: str):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        state_file = STATE_DIR / f"{platform}.json"

        self.pw = sync_playwright().start()
        launch_kwargs = {"headless": self.headless}
        if os.path.exists(EDGE_PATH):
            launch_kwargs["channel"] = "msedge"
        else:
            launch_kwargs["channel"] = "chrome"
        self.browser = self.pw.chromium.launch(**launch_kwargs)
        self.context = self.browser.new_context(
            storage_state=str(state_file) if state_file.exists() else None,
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        self.page = self.context.new_page()
        return self.page

    def save_state(self, platform: str):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state_file = STATE_DIR / f"{platform}.json"
        self.context.storage_state(path=str(state_file))
        log.info(f"Login state saved: {state_file}")

    def screenshot(self, name: str) -> str | None:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        path = EVIDENCE_DIR / f"{name}_{int(time.time())}.png"
        try:
            self.page.screenshot(path=str(path), full_page=False)
            return str(path)
        except Exception:
            return None

    def close(self):
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.pw:
                self.pw.stop()
        except Exception:
            pass


def fill_by_placeholder(page, placeholder: str, value: str, timeout: int = 15000):
    """Locate an input/textarea by placeholder text and fill it."""
    locator = page.locator(
        f"input[placeholder*='{placeholder}'], textarea[placeholder*='{placeholder}']").first
    locator.wait_for(state="visible", timeout=timeout)
    locator.click()
    locator.fill(value)
    return locator


def find_file_input(page):
    """Find the hidden file input used for video uploads."""
    selectors = [
        "input[type=file][accept*='video']",
        "input[type=file][accept*='mp4']",
        "input[type=file]",
    ]
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            if loc.count() > 0:
                return loc
        except Exception:
            continue
    return None
