# Contributing to ContentForge

Thanks for considering a contribution! A few ground rules to keep the project
healthy:

## Project scope

ContentForge automates *content production* (topic discovery, script writing,
video rendering) and provides *opt-in publishing* channels for third-party
platforms. We keep the following boundaries:

- **No CAPTCHA solving, no anti-detection, no fingerprint spoofing, no
  scraping circumvention.** PRs that add such techniques will be rejected.
- Publishing channels must be honest about platform terms: failures should be
  loud and safe (save drafts, screenshots), never silently "successful".
- The project targets Python 3.11+, runs on Windows and macOS/Linux, and must
  not introduce hard platform-specific dependencies.

## Development setup

```bash
git clone https://github.com/<you>/contentforge.git
cd contentforge
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -e ".[dev]"
playwright install chromium                      # optional, only for RPA dev
```

## Before submitting

1. Run `ruff check contentforge tests scripts`.
2. Run `pytest -m "not rpa and not network"` — all green.
3. Add tests for new logic under `tests/`; keep network/RPA tests marked with
   `@pytest.mark.network` / `@pytest.mark.rpa` so CI stays hermetic.
4. Update `README.md` and `docs/` if the change is user-facing.

## Commit style

- Conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`.
- Keep changes focused; one logical change per PR.

## Questions

Open an issue with the `question` label. No need to ask permission before
opening a PR.
