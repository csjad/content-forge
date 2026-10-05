"""X (Twitter) publishing channel — official API v2 with OAuth 1.0a.

Implements:
- OAuth 1.0a request signing (HMAC-SHA1, application user context)
- chunked ``media/upload`` for videos (INIT → APPEND → FINALIZE)
- ``POST /2/tweets`` with the uploaded media attached

Credentials go in ``.env``:

    X_API_KEY=...
    X_API_SECRET=...
    X_ACCESS_TOKEN=...
    X_ACCESS_SECRET=...
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
import urllib.parse

import requests

from ...utils import env
from ...utils.log import get_logger
from .base import PublishChannel

log = get_logger("x")

_MEDIA_URL = "https://upload.twitter.com/1.1/media/upload.json"
_TWEETS_URL = "https://api.twitter.com/2/tweets"
_CHUNK = 5 * 1024 * 1024  # 5 MB per media chunk


class XChannel(PublishChannel):
    name = "api_x"
    platform_key = "x"

    # ---------- credentials ----------
    def _credentials(self) -> dict[str, str]:
        return {
            "api_key": env.get("X_API_KEY", "").strip(),
            "api_secret": env.get("X_API_SECRET", "").strip(),
            "token": env.get("X_ACCESS_TOKEN", "").strip(),
            "token_secret": env.get("X_ACCESS_SECRET", "").strip(),
        }

    def _credentials_ready(self) -> bool:
        return all(self._credentials().values())

    # ---------- OAuth 1.0a signing ----------
    @staticmethod
    def _sign(method: str, url: str, params: dict[str, str],
              creds: dict[str, str]) -> str:
        oauth = {
            "oauth_consumer_key": creds["api_key"],
            "oauth_nonce": base64.b64encode(os.urandom(16)).decode()[:32],
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": creds["token"],
            "oauth_version": "1.0",
        }
        oauth.update(params)
        all_params = dict(oauth)
        # parameters from URL query string also participate in signing
        parsed = urllib.parse.urlparse(url)
        if parsed.query:
            all_params.update(urllib.parse.parse_qsl(parsed.query))
        normalized = "&".join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
            for k, v in sorted(all_params.items())
        )
        base = "&".join([
            method.upper(),
            urllib.parse.quote(parsed.scheme + "://" + parsed.netloc + parsed.path, safe=""),
            urllib.parse.quote(normalized, safe=""),
        ])
        key = f"{creds['api_secret']}&{creds['token_secret']}"
        digest = hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()
        return base64.b64encode(digest).decode()

    def _oauth_header(self, method: str, url: str, params: dict[str, str],
                      creds: dict[str, str]) -> str:
        oauth = {
            "oauth_consumer_key": creds["api_key"],
            "oauth_nonce": base64.b64encode(os.urandom(16)).decode()[:32],
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": creds["token"],
            "oauth_version": "1.0",
        }
        oauth["oauth_signature"] = self._sign(method, url, {**params, **oauth}, creds)
        return "OAuth " + ", ".join(
            f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
            for k, v in sorted(oauth.items())
        )

    # ---------- media upload ----------
    def _upload_media(self, video_path: str, creds: dict[str, str]) -> str:
        total = os.path.getsize(video_path)
        auth = self._oauth_header("POST", _MEDIA_URL,
                                  {"command": "INIT", "media_type": "video/mp4",
                                   "total_bytes": str(total)}, creds)
        r = requests.post(_MEDIA_URL, headers={"Authorization": auth}, data={
            "command": "INIT", "media_type": "video/mp4", "total_bytes": str(total),
        }, timeout=60)
        r.raise_for_status()
        media_id = r.json()["media_id_string"]

        with open(video_path, "rb") as f:
            index = 0
            while True:
                chunk = f.read(_CHUNK)
                if not chunk:
                    break
                auth = self._oauth_header(
                    "POST", _MEDIA_URL,
                    {"command": "APPEND", "media_id": media_id,
                     "segment_index": str(index)}, creds)
                up = requests.post(_MEDIA_URL, headers={"Authorization": auth}, data={
                    "command": "APPEND", "media_id": media_id,
                    "segment_index": str(index),
                }, files={"media": ("chunk", chunk, "application/octet-stream")}, timeout=300)
                up.raise_for_status()
                index += 1

        auth = self._oauth_header("POST", _MEDIA_URL,
                                  {"command": "FINALIZE", "media_id": media_id}, creds)
        r = requests.post(_MEDIA_URL, headers={"Authorization": auth}, data={
            "command": "FINALIZE", "media_id": media_id,
        }, timeout=60)
        r.raise_for_status()
        return media_id

    # ---------- channel interface ----------
    def publish(self, platform, content, assets, scripts, scheduled_at):
        if not self._credentials_ready():
            return False, None, (
                "X API 未配置：请在 developer.twitter.com 创建应用并申请读写权限，"
                "填入 .env 的 X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_SECRET。"
            )
        body = scripts.get("body", "")
        tags = scripts.get("tags") or []
        text = (body + (" " + " ".join(tags) if tags else "")).strip()[:280]
        if not text:
            return False, None, "推文内容为空"

        creds = self._credentials()
        try:
            payload = {"text": text}
            video_path = assets.get("video")
            if video_path and os.path.exists(video_path):
                media_id = self._upload_media(video_path, creds)
                payload["media"] = {"media_ids": [media_id]}
                log.info(f"X media uploaded: {media_id}")
            auth = self._oauth_header("POST", _TWEETS_URL, {}, creds)
            r = requests.post(_TWEETS_URL, headers={
                "Authorization": auth, "Content-Type": "application/json",
            }, json=payload, timeout=60)
            r.raise_for_status()
            tweet_id = r.json().get("data", {}).get("id", "")
            return True, f"https://x.com/i/status/{tweet_id}" if tweet_id else None, None
        except Exception as e:
            log.error(f"X publish failed: {e}")
            return False, None, str(e)
