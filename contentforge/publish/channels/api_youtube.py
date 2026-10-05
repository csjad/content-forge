"""YouTube publishing channel (official Data API v3, resumable upload).

Auth uses the Google **device flow** so a CLI app can obtain OAuth tokens
without a redirect server: the user opens a URL, enters a code once, and the
token (plus refresh token) is stored under ``state/youtube_token.json`` and
refreshed automatically afterwards.

Setup: enable the YouTube Data API v3 in Google Cloud Console, create an OAuth
2.0 client (Desktop type), then set in ``.env``:

    YOUTUBE_CLIENT_ID=...
    YOUTUBE_CLIENT_SECRET=...
"""
from __future__ import annotations

import json
import os
import time

import requests

from ...utils import env
from ...utils.log import get_logger
from ...utils.paths import get_state_dir
from .base import PublishChannel

log = get_logger("youtube")

_DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
_SCOPE = "https://www.googleapis.com/auth/youtube.upload"


class YoutubeChannel(PublishChannel):
    name = "api_youtube"
    platform_key = "youtube"

    def __init__(self, cfg, db):
        super().__init__(cfg, db)
        self._token_file = get_state_dir() / "youtube_token.json"

    # ---------- credentials ----------
    def _credentials(self) -> tuple[str, str]:
        client_id = env.get("YOUTUBE_CLIENT_ID", "").strip()
        client_secret = env.get("YOUTUBE_CLIENT_SECRET", "").strip()
        return client_id, client_secret

    def _credentials_ready(self) -> bool:
        client_id, client_secret = self._credentials()
        return bool(client_id and client_secret)

    # ---------- OAuth device flow ----------
    def _authorize_device(self, client_id: str, client_secret: str) -> dict:
        """Run the device flow: print the URL, poll until the user approves."""
        r = requests.post(_DEVICE_CODE_URL, data={
            "client_id": client_id,
            "scope": _SCOPE,
        }, timeout=30)
        r.raise_for_status()
        d = r.json()
        log.warning(
            f"Open this URL in your browser and enter code {d['user_code']}:\n"
            f"  {d['verification_url']}\nWaiting for authorization... (never close this window)"
        )
        try:
            import webbrowser
            webbrowser.open(d["verification_url"])
        except Exception:
            pass

        interval = int(d.get("interval", 5))
        for _ in range(int(d.get("expires_in", 1800)) // interval):
            time.sleep(interval)
            r = requests.post(_TOKEN_URL, data={
                "client_id": client_id,
                "client_secret": client_secret,
                "device_code": d["device_code"],
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            }, timeout=30)
            data = r.json()
            if "access_token" in data:
                self._save_token(data)
                log.info("YouTube authorization succeeded.")
                return data
            if data.get("error") in ("authorization_pending", "slow_down"):
                continue
            if data.get("error") == "access_denied":
                raise RuntimeError("YouTube authorization was denied by the user.")
            raise RuntimeError(f"YouTube device flow error: {data.get('error')}")
        raise RuntimeError("YouTube authorization timed out.")

    def _save_token(self, data: dict):
        self._token_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", ""),
            "expires_in": int(data.get("expires_in", 3600)),
            "_issued_at": time.time(),
        }
        self._token_file.write_text(json.dumps(payload), encoding="utf-8")

    def _get_access_token(self, client_id: str, client_secret: str) -> str:
        if not self._token_file.exists():
            self._authorize_device(client_id, client_secret)
        data = json.loads(self._token_file.read_text(encoding="utf-8"))
        if time.time() < float(data.get("_issued_at", 0)) + int(data.get("expires_in", 3600)):
            return data["access_token"]
        # refresh
        r = requests.post(_TOKEN_URL, data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": data["refresh_token"],
            "grant_type": "refresh_token",
        }, timeout=30)
        r.raise_for_status()
        new = r.json()
        new["refresh_token"] = data["refresh_token"]  # keep for next round
        self._save_token(new)
        return new["access_token"]

    # ---------- resumable upload ----------
    def _upload_video(self, token: str, video_path: str, title: str,
                      description: str, tags: list[str]) -> str:
        """Resumable upload; returns the new video ID."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        body = {
            "snippet": {
                "title": title[:100],
                "description": (description or "")[:5000],
                "tags": [str(t) for t in (tags or [])][:500],
                "categoryId": "22",  # People & Blogs (safe default)
            },
            "status": {"privacyStatus": "private"},  # private: safe default
        }
        size = os.path.getsize(video_path)
        headers["X-Upload-Content-Length"] = str(size)

        r = requests.post(
            f"{_UPLOAD_URL}?uploadType=resumable&part=snippet,status",
            headers=headers, json=body, timeout=60,
        )
        r.raise_for_status()
        session_uri = r.headers["Location"]

        with open(video_path, "rb") as f:
            up = requests.put(
                session_uri,
                data=f,
                headers={"Content-Length": str(size)},
                timeout=600,
            )
        if up.status_code in (200, 201):
            return up.json().get("id", "")
        # resume support: if interrupted, session URI may still be usable
        if up.status_code in (308, 503, 500, 408):
            log.warning(f"YouTube upload interrupted ({up.status_code}), retrying once")
            with open(video_path, "rb") as f:
                up = requests.put(session_uri, data=f,
                                  headers={"Content-Length": str(size)},
                                  timeout=600)
            if up.status_code in (200, 201):
                return up.json().get("id", "")
        raise RuntimeError(f"YouTube upload failed: HTTP {up.status_code} {up.text[:300]}")

    # ---------- channel interface ----------
    def publish(self, platform, content, assets, scripts, scheduled_at):
        if not self._credentials_ready():
            return False, None, (
                "YouTube API 未配置：请在 Google Cloud Console 启用 YouTube Data API v3，"
                "创建 OAuth 2.0 凭据（Desktop 类型），填入 .env 的 YOUTUBE_CLIENT_ID / "
                "YOUTUBE_CLIENT_SECRET。"
            )
        video_path = assets.get("video")
        if not video_path or not os.path.exists(video_path):
            return False, None, "缺少视频文件"

        client_id, client_secret = self._credentials()
        try:
            token = self._get_access_token(client_id, client_secret)
            title = (scripts.get("titles_zh") or scripts.get("titles") or [""])[0]
            if scripts.get("titles_en"):
                title = f"{title} | {scripts['titles_en'][0]}" if title else scripts["titles_en"][0]
            video_id = self._upload_video(
                token, video_path, title,
                scripts.get("description", ""),
                scripts.get("tags", []),
            )
            return True, f"https://youtu.be/{video_id}", None
        except Exception as e:
            log.error(f"YouTube publish failed: {e}")
            return False, None, str(e)
