# Compliance

ContentForge automates content **production** on your own machines and accounts.
This document states what the project does, what it deliberately does not do,
and what you are responsible for.

## What we never implement

The project has a hard technical boundary — any contribution crossing it is
rejected, and the same rules apply to runtime behavior:

- **No CAPTCHA solving.** We never automate or proxy human-verification steps.
  If a platform requires verification, the run fails loudly and waits for a
  human.
- **No anti-detection / fingerprint spoofing.** No user-agent rotation,
  canvas/WebGL spoofing, TLS mimicry, or headless-browser evasion. The browser
  is the real system Edge with a real saved session from a real login.
- **No scraping circumvention.** Hot-topic collection is best-effort with
  graceful degradation; when a source returns nothing (rate-limited, blocked),
  the pipeline continues without the feed rather than fighting the block.
- **No rate-limit bypass.** Publishing is scheduled, human-paced, and per-account
  friendly.

## Publishing honesty

- Every publish outcome is written to the SQLite queue: `success` (with the
  canonical URL), `failed` (with the error text), `publishing` (in-flight).
- A failure is never converted into a silent success. RPA channels that cannot
  find the upload form fail the item and keep drafts/screenshots where possible.
- YouTube uploads default to `private` so nothing leaks publicly by accident.

## Your responsibility

- You run this on your own accounts. Follow each platform's terms of service,
  community guidelines, and rate limits — and your local law.
- Credentials: `.env`, `state/browser/`, and `state/youtube_token.json` contain
  secrets. They are git-ignored; never commit or share them.
- The generated content is your responsibility: the LLM can hallucinate, and
  hot-topic feeds can be wrong. Review before you publish anything factual,
  financial, or medical.
- WeChat Channels is intentionally manual-only — the final confirm remains a
  human action.

## AI-generated content disclosure

Many platforms require or recommend disclosing AI-generated or synthetic media.
Configure your titles/descriptions accordingly (`direction.must_avoid` is a good
place to encode this), and follow platform policies (e.g. YouTube's synthetic
media disclosure, TikTok's AI labels).
