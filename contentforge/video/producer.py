"""Video production orchestration: script → background/cover → TTS → frames → mp4.

Currently supports the ``voice_slides`` format (slideshow with subtitles and
AI narration). Extensible to ``ai_scene`` / ``mixed_cut`` behind the same API.
"""
from __future__ import annotations

from ..db import DB
from ..utils.log import get_logger
from ..utils.paths import get_data_dir
from . import assets, compose, subtitle, tts

log = get_logger("producer")


class VideoProducer:
    def __init__(self, cfg, db: DB):
        self.cfg = cfg
        self.db = db

    def produce(self, content_id: int, title: str, script_lines: list[str]) -> dict:
        """Produce video + cover, record assets, return paths and duration."""
        vcfg = self.cfg.video
        resolution = vcfg.resolution
        fps = vcfg.fps
        fmt = vcfg.default_format

        # 1. background + cover
        bg_path = assets.get_background(title, resolution, self.cfg.image_source)
        cover_path = assets.make_cover(title, title, resolution, self.cfg.image_source)
        self.db.add_asset(content_id, "cover", cover_path, "base",
                          {"resolution": list(resolution)})

        # 2. narration (sentence by sentence)
        segments = tts.synth_sentences(script_lines, self.cfg.tts)
        if not segments:
            raise RuntimeError("配音生成失败（TTS 不可用）")
        for seg in segments:
            self.db.add_asset(content_id, "audio", seg["path"], "base",
                              {"index": seg["index"], "duration": seg["duration"]})

        # 3. subtitle frames (one per narration segment)
        frames = []
        total = len(segments)
        style = vcfg.subtitle_style
        for i, seg in enumerate(segments):
            frame = subtitle.render_frame(bg_path, seg["text"], i, total, resolution, style)
            frames.append(frame)
            self.db.add_asset(content_id, "slide", frame, "base", {"index": i})

        # 4. compose
        bgm_path = None
        if vcfg.bgm:
            bgm_dir = get_data_dir() / "bgm"
            if bgm_dir.is_dir():
                for f in sorted(bgm_dir.iterdir()):
                    if f.suffix.lower() in (".mp3", ".m4a", ".wav"):
                        bgm_path = str(f)
                        break
        video_path = compose.compose(segments, frames, resolution, fps=fps, bgm=bgm_path)
        total_dur = sum(s["duration"] for s in segments)

        self.db.add_asset(content_id, "video", video_path, "base",
                          {"resolution": list(resolution), "duration": round(total_dur, 1),
                           "format": fmt})
        log.info(f"内容 #{content_id} 生产完成: 时长 {total_dur:.1f}s")
        return {"video_path": video_path, "cover_path": cover_path,
                "duration": total_dur, "format": fmt}
