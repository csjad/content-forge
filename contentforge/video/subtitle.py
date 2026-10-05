"""Subtitle frame rendering: PIL draws each narration line onto a frame.

One frame per narration segment, so frames and audio stay in sync during the
final ffmpeg composition.
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..config import SubtitleStyle
from ..utils.log import get_logger
from ..utils.paths import get_data_dir

log = get_logger("subtitle")

_FONT_CANDIDATES = (
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",       # macOS
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux fallback
)


def find_font() -> str:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    raise FileNotFoundError("No CJK font found (msyh/simhei/PingFang). Install one or set a custom font.")


def render_frame(
    bg_path: str,
    text: str,
    idx: int,
    total: int,
    resolution: tuple[int, int],
    style: SubtitleStyle,
) -> str:
    """Render a single subtitle frame and return the PNG path."""
    w, h = resolution
    bg = Image.open(bg_path).convert("RGB").resize((w, h))
    draw = ImageDraw.Draw(bg)

    font_path = find_font()
    font_size = int(w * style.font_size_ratio)
    font = ImageFont.truetype(font_path, font_size)

    # ---- subtitle block at the bottom (auto wrap, max 2 lines) ----
    max_width = int(w * 0.84)
    margin_bottom = int(h * style.margin_ratio)
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) <= max_width:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    lines = lines[:2]
    line_h = int(font_size * 1.4)
    block_h = line_h * len(lines)
    y = h - margin_bottom - block_h

    for li, line in enumerate(lines):
        lw = draw.textlength(line, font=font)
        x = (w - lw) // 2
        ly = y + li * line_h
        pad = int(font_size * 0.25)
        draw.rounded_rectangle(
            [x - pad, ly - int(font_size * 0.1), x + lw + pad, ly + int(font_size * 1.15)],
            radius=int(font_size * 0.25), fill=(0, 0, 0, 140),
        )
        for dx, dy in ((-2, -2), (2, -2), (-2, 2), (2, 2)):
            draw.text((x + dx, ly + dy), line, font=font, fill=style.stroke_color)
        draw.text((x, ly), line, font=font, fill=style.font_color)

    # ---- top progress bar ----
    bar_w = int(w * 0.5)
    bar_h = max(4, int(h * 0.004))
    bar_x = (w - bar_w) // 2
    bar_y = int(h * 0.06)
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
                           radius=bar_h // 2, outline=(255, 255, 255, 120))
    fill_w = int(bar_w * (idx + 1) / total)
    if fill_w > 0:
        draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h],
                               radius=bar_h // 2, fill="#FF5A5F")

    slide_dir = get_data_dir() / "slides"
    slide_dir.mkdir(parents=True, exist_ok=True)
    out: Path = slide_dir / f"frame_{idx:03d}.png"
    bg.save(out)
    return str(out)
