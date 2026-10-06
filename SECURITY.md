# Security Policy

ContentForge is honest automation: it never bypasses platform defenses, and we
take security reports seriously.

## Scope

We accept reports about:

- Code-level vulnerabilities (arbitrary code execution, injection, secrets
  leakage, unsafe deserialization, etc.) in `contentforge/`, `scripts/`, or
  `tests/`.
- Accidentally committed secrets (tokens, keys, session files) in the
  repository history.
- Dependency vulnerabilities in `pyproject.toml`.

Out of scope: automating around platform anti-bot systems is **by design
rejected** (see `CONTRIBUTING.md` and `docs/compliance.md`), so such reports are
not considered vulnerabilities of this project.

## Reporting a vulnerability

**Do not open a public issue.** Report privately:

- Open a GitHub Security Advisory at
  https://github.com/csjad/content-forge/security/advisories/new, or
- Email the maintainers (link available on the repository page).

Please include: affected version(s), a minimal reproduction, and your suggested
fix if you have one. We aim to acknowledge reports within 3 business days.

## Supported versions

| Version | Supported |
| --- | --- |
| latest release | ✅ |
| older releases | ❌ (upgrade) |

## Disclosure

We will coordinate a fix and a public disclosure. Security fixes are released as
patch releases with a changelog note.

## Secrets hygiene

- `state/` (SQLite DB, logs, browser sessions, API tokens) and `.env` are
  git-ignored. Never commit them.
- If you believe a secret was committed, rotate it immediately and report it
  above so history can be purged.
