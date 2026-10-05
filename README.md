# ContentForge

**One-click content factory: topic discovery → script writing → video production → multi-platform publishing → dashboard.**

ContentForge is a self-hosted pipeline that turns a single command into a finished,
platform-adapted content unit — hot-topic research, AI-scored topic selection,
platform-specific copy (9 platforms), edge-TTS narration, PIL subtitle frames,
ffmpeg composition, and a scheduled publish queue that dispatches through official
APIs or browser automation.

> It is built for quality, not toys: every stage is configurable, every artifact
> is verifiable, and the state of everything lives in one SQLite database.

---

## Features

| Stage | What it does |
| --- | --- |
| **Topics** | Hot-search collection (Baidu / Weibo / Douyin) with graceful degradation; AI scores candidates into a SQLite pool; dedup by title within a configurable window |
| **Writing** | Pain-point hook + structured outline + multi-line script; then a per-platform adapter produces titles, bodies, tags and descriptions for all 9 platforms |
| **Video** | Per-sentence narration via edge-tts (timestamps from sentence boundaries); PIL-rendered subtitle frames + gradient cover; ffmpeg assembles a platform-native vertical video (1080×1920) with optional BGM |
| **Publishing** | Items enter a queue scheduled at each platform's golden hour; a worker dispatches due items through official APIs (YouTube, X) or Playwright-driven Edge (Douyin, Xiaohongshu, Bilibili, Weibo, TikTok, Instagram), with manual fallback for WeChat Channels |
| **Dashboard** | `status` shows today's candidates, approved topics, produced contents and queue health |

## Pipeline at a glance

```
  config.yaml + .env (direction / LLM / platforms)
        │
        ▼
┌─────────────┐   ┌──────────────┐   ┌─────────────┐   ┌─────────────────┐
│ topic engine │→ │ writing shop │→ │ video plant │→ │ publish queue   │
│ collector +  │   │ outline +    │   │ tts + frame │   │ scheduler +     │
│ AI scoring   │   │ 9 adapters   │   │ + compose   │   │ API / RPA /    │
└──────┬──────┘   └──────┬───────┘   └──────┬──────┘   │ manual channels │
       │                 │                  │          └────────┬────────┘
       ▼                 ▼                  ▼                   ▼
   topics table      contents table      assets table     publish_queue
                      SQLite state (state/forge.db)  +  data/ outputs
```

## Quick start

### 1. Install

Requires **Python 3.11+** and **ffmpeg** on PATH (ContentForge locates it
automatically; set `FFMPEG_PATH`/`FFPROBE_PATH` if needed).

```bash
git clone https://github.com/<your-org>/contentforge.git
cd contentforge
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure

Edit `config.yaml`:

- `direction` — your content persona. This is the heart of the system; you can
  switch it any time (e.g. `niche: University student growth`, `language: zh-CN`,
  `must_avoid: clickbait`).
- `llm` — an OpenAI-compatible endpoint (DeepSeek, Doubao, Agnes, …):
  ```yaml
  llm:
    base_url: "https://api.deepseek.com/v1"
    api_key: "sk-..."
    model: "deepseek-chat"
  ```
  Secrets may also go into `.env` (`LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`,
  plus `IMG_MODEL` for image generation).

### 3. Produce

```bash
contentforge run --auto      # topic → script → video → queue, fully automatic
contentforge status          # today's dashboard
contentforge publish         # dispatch due queue items
contentforge publish --force # dispatch everything pending, right now
```

That is the whole loop. A Windows scheduled task script is provided in
`scripts/install_scheduler.ps1` for fully unattended daily runs.

## Platform channel matrix

| Platform | Channel | Auth | Notes |
| --- | --- | --- | --- |
| YouTube | `api_youtube` | OAuth 2.0 device flow | resumable upload, default `private`, token stored & auto-refreshed |
| X / Twitter | `api_x` | OAuth 1.0a (app-level) | HMAC-SHA1 signed, chunked media upload, `POST /2/tweets` |
| Douyin | `rpa_douyin` | session (login once) | Playwright + system Edge, headless by default, `--show` for visible |
| Xiaohongshu | `rpa_xiaohongshu` | session | — |
| Bilibili | `rpa_bilibili` | session | — |
| Weibo | `rpa_weibo` | session | — |
| TikTok | `rpa_tiktok` | session | — |
| Instagram | `rpa_instagram` | session | — |
| WeChat Channels | `manual_video_account` | — | opens with everything prepared; you confirm the final post |

Detailed per-platform setup lives in [`docs/platform-channels.md`](docs/platform-channels.md).

## CLI reference

| Command | Description |
| --- | --- |
| `init` | create directories and the SQLite state database |
| `config` | print the effective configuration |
| `direction` | print the current content persona prompt |
| `run` | interactive: pick a candidate, then produce |
| `run --auto` | auto-pick the highest-scored candidate |
| `run --topic N` | produce from candidate topic `N` |
| `topics [--status]` | list candidate / approved / rejected topics |
| `pick N` | approve topic `N` and produce it |
| `publish [--force] [--show]` | dispatch due items; force all; show browser |
| `login PLATFORM` | one-time interactive login to save a session |
| `status` | today's dashboard |
| `logs` | recent run logs |

`python main.py ...` works identically; the console script `contentforge` is
installed with the package.

## Configuration model

`config.yaml` is parsed into **immutable typed dataclasses** (`ForgeConfig`,
`DirectionConfig`, `LLMConfig`, `TTSConfig`, `VideoConfig`, `PlatformConfig`,
`PublishConfig`, `TopicsConfig`, …) with validation — invalid cadence, channel or
format values raise `ConfigError` at startup instead of failing mid-run. The file
is hot-reloaded on every run; `direction.niche` is your persona and can change
any time. See [`docs/architecture.md`](docs/architecture.md) for the module map.

## Compliance & boundaries

ContentForge is honest automation. It **never** solves CAPTCHAs, evades
anti-bot detection, spoofs fingerprints or circumvents scraping restrictions —
contributions adding such techniques are rejected. Publishing failures are loud
and safe (drafts/screenshots), never silently "successful". Always follow each
platform's terms of service and rate limits. Details:
[`docs/compliance.md`](docs/compliance.md).

## Development

```bash
ruff check contentforge tests scripts   # lint gate
pytest -m "not rpa and not network and not integration" -v   # hermetic test suite
python scripts/selftest.py              # full end-to-end run with a mock LLM
```

- Tests run against a temporary SQLite DB (`FORGE_DATA`/`FORGE_STATE`/`FORGE_DB`
  override the real paths), so they never touch your state.
- Network / RPA / integration tests are marked and skipped in CI.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) before sending a PR.

## License

MIT — see [`LICENSE`](LICENSE). You are responsible for how you use the
publishing channels; the project is provided as-is.
