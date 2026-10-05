"""Video composition: ffmpeg per-sentence (frame + narration) → concat → mp4.

Optionally mixes a BGM track from ``data/bgm``.
"""
from __future__ import annotations

import os
import re
import subprocess

from ..utils.ffmpeg import ffmpeg_bin, ffprobe_bin
from ..utils.log import get_logger
from ..utils.paths import get_data_dir

log = get_logger("compose")

VIDEO_DIR = get_data_dir() / "videos"
TMP_DIR = get_data_dir() / "publish" / "_tmp"


def _ffmpeg(args: list[str], desc: str):
    proc = subprocess.run([ffmpeg_bin(), *args], capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        log.error(f"ffmpeg {desc} failed: {proc.stderr[-500:]}")
        raise RuntimeError(f"ffmpeg {desc} failed")
    return proc


def _probe_duration(path: str) -> float:
    """Media duration: prefer ffprobe; fall back to parsing ffmpeg -i output."""
    fp = ffprobe_bin()
    if fp:
        try:
            out = subprocess.run(
                [fp, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, timeout=30)
            return float(out.stdout.strip())
        except Exception:
            pass
    try:
        out = subprocess.run([ffmpeg_bin(), "-i", path],
                             capture_output=True, text=True, timeout=30)
        m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out.stderr)
        if m:
            h, mi, s = m.groups()
            return int(h) * 3600 + int(mi) * 60 + float(s)
    except Exception:
        pass
    return 0.0


def compose(segments: list[dict], frames: list[str], resolution: tuple[int, int],
            fps: int = 30, bgm: str | None = None) -> str:
    """Compose segments (each with a frame + narration) into a final mp4."""
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    w, h = resolution
    parts = []

    for i, (seg, frame) in enumerate(zip(segments, frames, strict=False)):
        part = TMP_DIR / f"part_{i:03d}.mp4"
        # per sentence: loop the subtitle frame + the narration clip
        _ffmpeg([
            "-y",
            "-loop", "1", "-i", frame,
            "-i", seg["path"],
            "-t", f"{seg['duration']:.3f}",
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black",
            "-r", str(fps),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", "-shortest",
            "-pix_fmt", "yuv420p", str(part),
        ], f"segment {i+1}")
        parts.append(part)

    concat_list = TMP_DIR / "concat_parts.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for p in parts:
            f.write(f"file '{p.as_posix()}'\n")

    silent = TMP_DIR / "concat_no_bgm.mp4"
    _ffmpeg([
        "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", str(silent),
    ], "concat segments")

    final = VIDEO_DIR / "final.mp4"
    if bgm and os.path.exists(bgm):
        dur = _probe_duration(str(silent))
        _ffmpeg([
            "-y",
            "-i", str(silent),
            "-i", bgm,
            "-filter_complex",
            f"[1:a]atrim=0:{dur},volume=0.12[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", str(final),
        ], "mix BGM")
    else:
        _ffmpeg([
            "-y", "-i", str(silent),
            "-c:v", "copy", "-c:a", "copy", str(final),
        ], "finalize")

    # clean up temp parts
    for p in parts + [concat_list, silent]:
        try:
            p.unlink()
        except OSError:
            pass
    log.info(f"Video composed: {final}")
    return str(final)
