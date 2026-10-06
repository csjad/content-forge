"""Video asset tests: gradient backgrounds and PIL covers.

Frame rendering requires a CJK font on the host; those tests are skipped
when no font is available (e.g. minimal CI images).
"""
from __future__ import annotations

import pytest
from contentforge.config import SubtitleStyle
from contentforge.video import assets, subtitle
from PIL import Image


def _skip_without_cjk_font():
    try:
        assets.find_font()
    except FileNotFoundError:
        pytest.skip("no CJK font on this host")


def test_gradient_background(tmp_project):
    path = assets.get_background("theme", (540, 960))
    img = Image.open(path)
    assert img.size == (540, 960)
    assert img.mode == "RGB"


def test_make_cover_renders_title(tmp_project):
    _skip_without_cjk_font()
    path = assets.make_cover("theme", "Short Title", (540, 960))
    img = Image.open(path)
    assert img.size == (540, 960)


def test_cover_wraps_long_title(tmp_project):
    # long title must render without exceptions and stay within 3 lines
    _skip_without_cjk_font()
    title = "A very long title that should wrap across multiple lines gracefully"
    path = assets.make_cover("theme", title, (540, 960))
    assert Image.open(path).size == (540, 960)


def test_subtitle_frame_rendering(tmp_project):
    try:
        subtitle.find_font()
    except FileNotFoundError:
        pytest.skip("no CJK font on this host")
    bg = assets.get_background("t", (540, 960))
    style = SubtitleStyle(font_size_ratio=0.06)
    path = subtitle.render_frame(bg, "第一行字幕内容", 0, 5, (540, 960), style)
    img = Image.open(path)
    assert img.size == (540, 960)
