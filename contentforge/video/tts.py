"""Narration synthesis with edge-tts (free Microsoft voices).

Each script line is synthesized separately and its duration is measured from
the streamed word/sentence boundary timestamps (no ffprobe dependency), then
all segments are concatenated into a single voice track.

Output: ``data/audio/seg_XX_*.mp3`` ... + ``data/audio/voice.mp3``
"""
from __future__ import annotations

import asyncio
import subprocess
import uuid

import edge_tts

from ..config import TTSConfig
from ..utils.ffmpeg import ffmpeg_bin
from ..utils.log import get_logger
from ..utils.paths import get_data_dir

log = get_logger("tts")

TAIL_PAD = 0.25  # seconds of silence appended to each sentence


async def _synth_segment(text: str, voice: str, rate: str, pitch: str,
                         out_path: str) -> float:
    """Synthesize one sentence; return its duration in seconds."""
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    last_end = 0.0
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            kind = chunk["type"]
            if kind == "audio":
                f.write(chunk["data"])
            elif kind in ("WordBoundary", "SentenceBoundary"):
                # offset/duration are in 100ns units
                last_end = (chunk["offset"] + chunk["duration"]) / 1e7
    return last_end + TAIL_PAD


def synth_sentences(lines: list[str], cfg: TTSConfig) -> list[dict]:
    """Synthesize each line; return [{"index", "text", "path", "duration"}]."""
    audio_dir = get_data_dir() / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    if cfg.engine != "edge":
        log.error(f"Unsupported TTS engine: {cfg.engine} (only 'edge' is implemented)")
        return []

    segments = []
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        out = audio_dir / f"seg_{i:02d}_{uuid.uuid4().hex[:6]}.mp3"
        try:
            dur = asyncio.run(_synth_segment(
                line, voice=cfg.voice, rate=cfg.rate, pitch=cfg.pitch, out_path=str(out)))
            if dur <= 0.3:
                log.warning(f"Sentence {i} duration anomaly, skipping: {line}")
                continue
            segments.append({"index": i, "text": line, "path": str(out), "duration": dur})
            log.info(f"Sentence {i} narrated ({dur:.1f}s): {line[:24]}...")
        except Exception as e:
            log.error(f"Sentence {i} synthesis failed: {e}")

    if not segments:
        return []
    # concat into a single voice track
    voice_path = audio_dir / "voice.mp3"
    concat_list = audio_dir / "concat.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(f"file '{seg['path'].replace(chr(92), '/')}'\n")
    subprocess.run(
        [ffmpeg_bin(), "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", str(voice_path)],
        capture_output=True, timeout=120,
    )
    total = sum(s["duration"] for s in segments)
    log.info(f"Voice track composed: {total:.1f}s -> {voice_path}")
    return segments
