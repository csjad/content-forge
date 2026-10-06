# Changelog

All notable changes to ContentForge are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-10-06

Initial open-source release.

### Added

- Full pipeline: hot-topic collection (Baidu/Weibo/Douyin, graceful
  degradation) → AI topic scoring → per-platform copy for 9 platforms →
  edge-tts narration → PIL subtitle frames + cover → ffmpeg video composition →
  scheduled publish queue.
- Publishing channels:
  - Official APIs: YouTube (OAuth 2.0 device flow, resumable upload, private by
    default, token auto-refresh) and X (OAuth 1.0a HMAC-SHA1 signing, chunked
    media upload, `POST /2/tweets`).
  - RPA (Playwright + system Edge, headless by default, `--show` to watch):
    Douyin, Xiaohongshu, Bilibili, Weibo, TikTok, Instagram.
  - Manual fallback for WeChat Channels.
- Typed, immutable configuration with validation (`ConfigError` on invalid
  cadence / channel / format).
- Single source of truth for paths (`contentforge/utils/paths.py`,
  `FORGE_DATA` / `FORGE_STATE` / `FORGE_DB` overrides).
- SQLite state store: topics / contents / assets / publish queue / logs.
- CLI (`contentforge` console script): `run`, `topics`, `pick`, `publish`,
  `login`, `status`, `config`, `direction`, `logs`.
- Hermetic pytest suite (37 tests) with isolated temp DB, ruff lint gate, and
  GitHub Actions CI matrix (ubuntu + windows × Python 3.11/3.12).
- End-to-end selftest (`scripts/selftest.py`) with a mock LLM.
- Documentation: English README, architecture, platform-channel matrix,
  compliance boundaries, contributing guide.
- MIT license and automated-publishing disclaimer (no CAPTCHA solving, no
  anti-detection, no scraping circumvention).
