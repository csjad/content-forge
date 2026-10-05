"""Image assets: background images and covers.

Resolution order for backgrounds:
1. ``ai``    — OpenAI-compatible images API (optional; configured in image_source.engine)
2. ``local`` — random image from a local stock library
3. gradient — deterministic procedural gradient (always available fallback)

Covers are always composited with PIL (AI image generators are unreliable at
rendering CJK text, so title text is drawn locally).
"""
from __future__ import annotations

import glob
import os
import random

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import ImageSourceConfig
from ..utils import env
from ..utils.log import get_logger
from ..utils.paths import get_data_dir

log = get_logger("assets")

GRADIENT_CACHE: dict = {}

_FONT_CANDIDATES = (
    "C:/Windows/Fonts/msyhbd.ttc",      # Windows 微软雅黑粗
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",  # macOS
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",  # Linux
)


def find_font() -> str:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        "No CJK font found. Install one (msyh / simhei / PingFang / Noto Sans CJK)."
    )


def _gradient_bg(size: tuple[int, int], seed: int = 0) -> Image.Image:
    """Procedural gradient background with a subtle noise texture."""
    key = (size, seed % 7)
    if key in GRADIENT_CACHE:
        return GRADIENT_CACHE[key].copy()
    w, h = size
    palettes = [
        ((30, 40, 90), (90, 60, 140)),   # deep blue-purple
        ((20, 60, 80), (40, 140, 160)),  # teal
        ((60, 30, 80), (140, 70, 120)),  # magenta-purple
        ((40, 70, 40), (110, 150, 90)),  # forest
        ((70, 40, 30), (160, 100, 60)),  # bronze
        ((30, 30, 50), (80, 90, 140)),   # slate blue
        ((50, 50, 50), (120, 110, 130)),  # neutral grey
    ]
    c1, c2 = palettes[seed % len(palettes)]
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        t = y / h
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    noise = Image.new("RGB", size, (0, 0, 0))
    np = noise.load()
    for _ in range(size[0] * size[1] // 400):
        nx, ny = random.randint(0, w - 1), random.randint(0, h - 1)
        np[nx, ny] = (random.randint(-18, 18),) * 3
    img = Image.blend(img, noise, 0.06)
    img = img.filter(ImageFilter.GaussianBlur(0.4))
    GRADIENT_CACHE[key] = img
    return img.copy()


def _random_local_image(local_dir: str) -> str | None:
    exts = ("*.jpg", "*.jpeg", "*.png", "*.webp")
    files: list[str] = []
    for ext in exts:
        files.extend(glob.glob(os.path.join(local_dir, "**", ext), recursive=True))
    return random.choice(files) if files else None


def _ai_image(prompt: str, size: str = "1024x1792") -> str | None:
    """Optional OpenAI-compatible images API. Returns a local path or None."""
    base = env.get("LLM_BASE_URL", "").rstrip("/")
    key = env.get("LLM_API_KEY", "")
    model = env.get("IMG_MODEL", "")
    if not (base and key and model):
        return None
    try:
        resp = requests.post(
            f"{base}/images/generations",
            json={"model": model, "prompt": prompt, "size": size, "n": 1},
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=120,
        )
        resp.raise_for_status()
        url = resp.json()["data"][0].get("url") or resp.json()["data"][0].get("b64_json")
        if not url:
            return None
        if url.startswith("http"):
            img_resp = requests.get(url, timeout=60)
            img_resp.raise_for_status()
            content = img_resp.content
        else:
            import base64
            content = base64.b64decode(url)
        out = get_data_dir() / "covers" / "_ai_tmp.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(content)
        return str(out)
    except Exception as e:
        log.warning(f"AI image generation failed, falling back: {e}")
        return None


def get_background(theme: str, size: tuple[int, int] = (1080, 1920),
                   source: ImageSourceConfig | None = None) -> str:
    """Resolve a background image path: ai → local stock → procedural gradient."""
    out = get_data_dir() / "slides" / "bg.png"
    out.parent.mkdir(parents=True, exist_ok=True)

    chosen: Image.Image | None = None
    if source:
        if source.engine == "ai":
            ai_path = _ai_image(f"{theme}, {source.ai_prompt_style}")
            if ai_path:
                return ai_path
        if source.engine == "local" and source.local_dir:
            local = _random_local_image(source.local_dir)
            if local:
                return local
    chosen = _gradient_bg(size, random.randint(0, 6))
    chosen.save(out)
    return str(out)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) <= max_width:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    # merge a trailing orphan character into the previous line
    if len(lines) > 1 and len(lines[-1]) <= 1:
        last = lines.pop()
        lines[-1] += last
    return lines


def make_cover(theme: str, title: str, size: tuple[int, int] = (1080, 1920),
               source: ImageSourceConfig | None = None) -> str:
    """Cover: background + large centered title (PIL-composited, auto-wrap)."""
    bg_path = get_background(theme, size, source)
    bg = Image.open(bg_path).convert("RGB").resize(size)
    overlay = Image.new("RGBA", size, (0, 0, 0, 90))
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(bg)
    font_path = find_font()
    w, h = size

    max_lines = 3
    font_size = int(w * 0.085)
    while font_size > 40:
        font = ImageFont.truetype(font_path, font_size)
        lines = _wrap_text(draw, title, font, int(w * 0.82))
        if len(lines) <= max_lines:
            break
        font_size -= 8
    font = ImageFont.truetype(font_path, font_size)

    lines = _wrap_text(draw, title, font, int(w * 0.82))[:max_lines]
    line_h = int(font_size * 1.35)
    total_h = line_h * len(lines)
    y = int(h * 0.62) - total_h // 2
    for line in lines:
        tw = draw.textlength(line, font=font)
        x = (w - tw) // 2
        for dx, dy in ((-3, 3), (3, -3), (-3, -3), (3, 3)):
            draw.text((x + dx, y + dy), line, font=font, fill="#000000")
        draw.text((x, y), line, font=font, fill="#FFFFFF")
        y += line_h

    small = ImageFont.truetype(font_path, int(w * 0.035))
    brand = "ContentForge · Daily"
    bw = draw.textlength(brand, font=small)
    draw.text(((w - bw) // 2, int(h * 0.88)), brand, font=small, fill=(255, 255, 255, 200))

    out = get_data_dir() / "covers" / "cover.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.convert("RGB").save(out, quality=92)
    return str(out)
