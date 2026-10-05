"""ContentForge — AI content factory.

Turn a content direction into finished, platform-ready videos:
topic discovery → script writing → video production → multi-platform publishing.

```
topic discovery ──▶ script writing ──▶ video production ──▶ publishing queue
      │                   │                   │                   │
      ▼                   ▼                   ▼                   ▼
  topics table        contents table      assets table      publish_queue
                          SQLite state store (state/forge.db)
```
"""

__version__ = "0.2.0"
