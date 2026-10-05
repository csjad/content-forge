# Architecture

ContentForge is a five-stage pipeline with one SQLite state store. Every stage is
a plain module under `contentforge/`; the CLI (`contentforge.cli`) and the
pipeline (`contentforge.pipeline.Pipeline`) are thin orchestrators over them.

```
contentforge/
├── cli.py                 # console entry point (contentforge / python main.py)
├── pipeline.py            # orchestrates the 5 stages for one content unit
├── config.py              # immutable typed config + validation (ConfigError)
├── db.py                  # SQLite state: topics / contents / assets / queue / logs
├── analytics/tracker.py   # dashboard summaries for `status`
├── topics/
│   ├── collector.py       # hot-search collection (baidu/weibo/douyin), degrades
│   └── generator.py       # AI topic scoring into the candidate pool
├── writing/
│   ├── outline.py         # hook + outline + script lines (+ short-script guard)
│   └── adapters.py        # per-platform copy: titles/body/tags/description
├── video/
│   ├── assets.py          # gradient backgrounds + cover rendering (PIL)
│   ├── subtitle.py        # subtitle frames, CJK-aware wrapping
│   ├── tts.py             # edge-tts narration, sentence-boundary timestamps
│   └── compose.py         # ffmpeg per-sentence assembly
├── publish/
│   ├── queue.py           # golden-hour scheduling + due dispatch + retry
│   └── channels/          # registry, factory, RPA utils, 9 platform channels
└── utils/
    ├── paths.py           # single source of truth for all paths (env overridable)
    ├── env.py             # .env loader (no dependency)
    ├── llm.py             # OpenAI-compatible client + JSON fence recovery + retry
    ├── ffmpeg.py          # ffmpeg discovery + resolution fallback
    └── log.py             # console + daily rolling file logs
```

## Data flow

1. **Topics** — `collector` queries hot-search sources (returns nothing on this
   network → automatic degradation, the run continues) and `generator` asks the
   LLM for scored candidates. Candidates below `topics.min_score` or duplicates
   within `topics.dedup_days` are dropped; the rest land in `topics` table.
2. **Writing** — `outline` produces `hook / outline / script_lines / cta`.
   Scripts shorter than the minimum are rejected. `adapters` then rewrites the
   script into 9 platform versions.
3. **Video** — each sentence is voiced with edge-tts; duration comes from
   sentence-boundary timestamps (WordBoundary is not emitted on some backends,
   so the pipeline falls back to SentenceBoundary). PIL renders one subtitle
   frame per sentence plus the cover; ffmpeg loops frames + narration into a
   platform-native vertical video (1080×1920, 30 fps).
4. **Publish** — one queue item per enabled platform, scheduled at
   `platforms.<name>.publish_time` (next occurrence). `process_due` dispatches
   through the channel registered for that platform: official API
   (`api_youtube`, `api_x`) or RPA (Playwright + system Edge) or manual. Failures
   are recorded with the error and retried up to `publish.max_retry`.
5. **Dashboard** — `status` reads the same SQLite store.

## Paths & isolation

`contentforge/utils/paths.py` is the only place that derives paths. Everything
else imports from it. The `FORGE_DATA`, `FORGE_STATE` and `FORGE_DB` environment
variables override the defaults, which is how the test suite isolates itself.

| Path | Default | Purpose |
| --- | --- | --- |
| `DATA_DIR` | `data/` | covers, videos, frames, assets |
| `STATE_DIR` | `state/` | `forge.db`, logs, browser sessions, API tokens |
| `DB_PATH` | `state/forge.db` | SQLite state store |
| `LOGS_DIR` | `state/logs/` | daily rolling logs |

## Configuration

`config.yaml` → typed dataclasses with validation:

- `forge` — timezone, cadence, daily target
- `direction` — the persona; `to_prompt()` builds the LLM framing prompt
- `llm` — OpenAI-compatible endpoint (`base_url`, `api_key`, `model`); secrets
  can come from `.env` (`LLM_API_KEY` etc.)
- `tts` — voice / rate / pitch / engine
- `video` — resolution, fps, default format, subtitle style, BGM
- `platforms.<name>` — enabled / format / channel / publish_time
- `publish` — confirm, max_retry, headless (overridable via `publish --show`)
- `topics` — sources, candidates per run, min score, dedup window

Invalid enum values (`cadence`, `channel`, `default_format`) raise
`ConfigError` at load time.

## Concurrency model

One writer: a single daily run mutates the state. The queue is append-only from
the pipeline's perspective; `process_due` is safe to call repeatedly (attempts
are bumped, failures are retried up to the cap). RPA sessions are per-platform
and reused across runs via saved browser states.
