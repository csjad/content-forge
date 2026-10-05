# Platform channels

ContentForge publishes through three channel types. The channel for a platform
is set in `config.yaml` under `platforms.<name>.channel`.

| Channel type | How it works | Platforms |
| --- | --- | --- |
| `api` | Official API, OAuth-signed requests from your machine | YouTube, X |
| `rpa` | Playwright drives the system Edge browser, reusing a saved session from a one-time interactive login | Douyin, Xiaohongshu, Bilibili, Weibo, TikTok, Instagram |
| `manual` | Everything is prepared (title/copy/video/cover), the user confirms the final post | WeChat Channels |

## Official API channels

### YouTube (`api_youtube`)

1. Enable **YouTube Data API v3** in Google Cloud Console and create an
   **OAuth 2.0 Client ID** (Desktop application).
2. Put `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET` into `.env`.
3. On first publish the channel runs the **device flow**: it prints a
   verification URL + code, opens the browser for you, and stores the token in
   `state/youtube_token.json` (refresh token persisted, auto-refreshed).
4. Videos upload via **resumable upload** and default to `privacyStatus=private`
   so nothing goes public by accident. Title = `titles_zh | titles_en` when both
   exist; category defaults to People & Blogs.

### X / Twitter (`api_x`)

1. Create an app at developer.twitter.com with **Read and Write** permission
   (Elevated access is required for video upload).
2. Put `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET` into
   `.env`.
3. The channel signs every request with **OAuth 1.0a HMAC-SHA1** and uploads the
   video in 5 MB chunks (INIT → APPEND → FINALIZE) before posting `POST /2/tweets`.

## RPA channels (browser automation)

Each RPA platform needs **one manual login**:

```bash
contentforge login douyin        # opens a real browser; log in, press Enter
contentforge login xiaohongshu   # …same for the others
```

The session (cookies + local storage) is saved under `state/browser/<platform>/`
and reused for every scheduled publish. Publishing runs **headless by default**;
use `contentforge publish --show` to watch the browser do the work.

### Selectors & fragility

RPA selectors live inside each channel module
(`contentforge/publish/channels/rpa_*.py`) and target the platforms' creator
dashboards. Platform DOMs change without notice — when a selector breaks, the
publish fails loudly with the error and the queue records the failure (never a
fake success). Keep selectors minimal and prefer stable attributes
(`aria-label`, stable CSS classes) over generated class names.

### Session storage

| Platform | State dir |
| --- | --- |
| douyin | `state/browser/douyin/` |
| xiaohongshu | `state/browser/xiaohongshu/` |
| bilibili | `state/browser/bilibili/` |
| weibo | `state/browser/weibo/` |
| tiktok | `state/browser/tiktok/` |
| instagram | `state/browser/instagram/` |

These are git-ignored; keep them private — they contain your login.

## Manual channel (WeChat Channels)

`manual_video_account` prepares the copy and locates the local video file, opens
the WeChat Channels publisher and prints exactly what to paste. The human press
is the last mile — this is the only platform where we deliberately do not fully
automate, to stay clearly within the platform's rules.

## Safety rules (all channels)

- **Never** solve CAPTCHAs, spoof fingerprints, rotate user agents, or bypass
  rate limits. Pull requests adding such techniques are rejected (see
  `CONTRIBUTING.md`).
- Failures must be loud: the queue records `failed` with the error text.
- Respect each platform's terms and per-account limits. Spread publishing over
  the scheduled golden hours — do not blast.
