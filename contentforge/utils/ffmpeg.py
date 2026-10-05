"""ffmpeg/ffprobe 路径定位：环境变量 → PATH → WorkBuddy 内置 → 常见安装路径
兼容本机（ffmpeg 在 .workbuddy/binaries 且无 ffprobe 的环境）
"""
import os
import shutil

_KNOWN_FFMPEG = [
    r"C:\Users\diege\.workbuddy\binaries\ffmpeg\ffmpeg.exe",
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    r"C:\Tools\ffmpeg\bin\ffmpeg.exe",
    r"E:\ffmpeg\bin\ffmpeg.exe",
]
_KNOWN_FFPROBE = [
    r"C:\Users\diege\.workbuddy\binaries\ffmpeg\ffprobe.exe",
    r"C:\ffmpeg\bin\ffprobe.exe",
    r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
    r"C:\Tools\ffmpeg\bin\ffprobe.exe",
    r"E:\ffmpeg\bin\ffprobe.exe",
]

_cache = {}


def ffmpeg_bin() -> str:
    if "ffmpeg" in _cache:
        return _cache["ffmpeg"]
    p = os.environ.get("FFMPEG_PATH", "").strip().strip('"')
    if p and os.path.exists(p):
        _cache["ffmpeg"] = p
        return p
    p = shutil.which("ffmpeg")
    if p:
        _cache["ffmpeg"] = p
        return p
    for p in _KNOWN_FFMPEG:
        if os.path.exists(p):
            _cache["ffmpeg"] = p
            return p
    raise FileNotFoundError(
        "未找到 ffmpeg。请安装 ffmpeg 并加入 PATH，或设置环境变量 FFMPEG_PATH 指向 ffmpeg.exe"
    )


def ffprobe_bin() -> str | None:
    if "ffprobe" in _cache:
        return _cache["ffprobe"] or None
    p = os.environ.get("FFPROBE_PATH", "").strip().strip('"')
    if p and os.path.exists(p):
        _cache["ffprobe"] = p
        return p
    p = shutil.which("ffprobe")
    if p:
        _cache["ffprobe"] = p
        return p
    for p in _KNOWN_FFPROBE:
        if os.path.exists(p):
            _cache["ffprobe"] = p
            return p
    _cache["ffprobe"] = None
    return None
