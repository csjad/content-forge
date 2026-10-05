#!/usr/bin/env python
"""Thin wrapper so the project also runs as `python main.py ...`.

The real CLI lives in ``contentforge.cli`` (also exposed as the ``contentforge``
console script after ``pip install -e .``).
"""
from __future__ import annotations

import sys

from contentforge.cli import main

if __name__ == "__main__":
    sys.exit(main())
