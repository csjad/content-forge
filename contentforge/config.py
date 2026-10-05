"""Typed configuration for ContentForge.

Config is loaded from ``config.yaml`` and validated into immutable dataclasses,
so every module accesses typed attributes (``cfg.llm.base_url``) instead of
bare dict lookups. Invalid or missing required fields raise ``ConfigError``
with a clear message.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .utils.paths import PROJECT_ROOT

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"

VALID_CADENCES = {"daily", "batch"}
VALID_CHANNELS = {"rpa", "api", "manual", "third_party"}
VALID_VIDEO_FORMATS = {"voice_slides", "ai_scene", "mixed_cut", "text"}


class ConfigError(Exception):
    """Raised when the configuration file is missing, invalid or incomplete."""


def _require(cfg: dict, key: str, section: str) -> Any:
    value = cfg.get(key)
    if value in (None, ""):
        raise ConfigError(f"config.yaml: [{section}] 缺少必填项 '{key}'")
    return value


@dataclass(frozen=True)
class DirectionConfig:
    """The content 'persona': what the factory produces and for whom."""

    niche: str
    audience: str = ""
    language: str = "zh-CN"
    style: str = ""
    must_avoid: str = ""
    content_formats: str = ""
    hooks: str = ""
    custom_instructions: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> DirectionConfig:
        return cls(
            niche=str(_require(d, "niche", "direction")),
            audience=str(d.get("audience", "")),
            language=str(d.get("language", "zh-CN")),
            style=str(d.get("style", "")),
            must_avoid=str(d.get("must_avoid", "")),
            content_formats=str(d.get("content_formats", "")),
            hooks=str(d.get("hooks", "")),
            custom_instructions=str(d.get("custom_instructions", "")),
        )

    def to_prompt(self) -> str:
        """Render the direction as the constraint block injected into LLM prompts."""
        lines = [
            f"Content niche: {self.niche}",
            f"Target audience: {self.audience}",
            f"Language: {self.language}",
            f"Style: {self.style}",
            f"Red lines (must avoid): {self.must_avoid}",
            f"Content formats: {self.content_formats}",
            f"Hook types: {self.hooks}",
        ]
        if self.custom_instructions:
            lines.append(f"Extra instructions: {self.custom_instructions}")
        return "\n".join(line for line in lines if line and not line.endswith(": "))


@dataclass(frozen=True)
class LLMConfig:
    """OpenAI-compatible chat-completions endpoint (DeepSeek, Doubao, Agnes, ...)."""

    base_url: str
    api_key: str = ""
    model: str = ""
    temperature: float = 0.8
    max_tokens: int = 6000
    timeout: float = 120.0
    max_retries: int = 3

    @classmethod
    def from_dict(cls, d: dict) -> LLMConfig:
        base = str(_require(d, "base_url", "llm"))
        return cls(
            base_url=base.rstrip("/"),
            api_key=str(d.get("api_key", "")),
            model=str(d.get("model", "")),
            temperature=float(d.get("temperature", 0.8)),
            max_tokens=int(d.get("max_tokens", 6000)),
            timeout=float(d.get("timeout", 120.0)),
            max_retries=int(d.get("max_retries", 3)),
        )

    def resolve_api_key(self) -> str:
        """API key may come from config or the LLM_API_KEY env var."""
        return self.api_key or os.environ.get("LLM_API_KEY", "")

    def resolve_model(self) -> str:
        return self.model or os.environ.get("LLM_MODEL", "")

    def ready(self) -> bool:
        return bool(self.base_url and self.resolve_api_key() and self.resolve_model())


@dataclass(frozen=True)
class TTSConfig:
    engine: str = "edge"
    voice: str = "zh-CN-XiaoxiaoNeural"
    rate: str = "+8%"
    pitch: str = "+0Hz"

    @classmethod
    def from_dict(cls, d: dict) -> TTSConfig:
        return cls(
            engine=str(d.get("engine", "edge")),
            voice=str(d.get("voice", "zh-CN-XiaoxiaoNeural")),
            rate=str(d.get("rate", "+8%")),
            pitch=str(d.get("pitch", "+0Hz")),
        )


@dataclass(frozen=True)
class ImageSourceConfig:
    engine: str = "local"  # ai | local
    local_dir: str = ""
    ai_prompt_style: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> ImageSourceConfig:
        return cls(
            engine=str(d.get("engine", "local")),
            local_dir=str(d.get("local_dir", "")),
            ai_prompt_style=str(d.get("ai_prompt_style", "")),
        )


@dataclass(frozen=True)
class SubtitleStyle:
    font: str = "msyhbd"
    font_size_ratio: float = 0.052
    font_color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    position: str = "bottom"
    margin_ratio: float = 0.08

    @classmethod
    def from_dict(cls, d: dict) -> SubtitleStyle:
        return cls(
            font=str(d.get("font", "msyhbd")),
            font_size_ratio=float(d.get("font_size_ratio", 0.052)),
            font_color=str(d.get("font_color", "#FFFFFF")),
            stroke_color=str(d.get("stroke_color", "#000000")),
            position=str(d.get("position", "bottom")),
            margin_ratio=float(d.get("margin_ratio", 0.08)),
        )


@dataclass(frozen=True)
class VideoConfig:
    default_format: str = "voice_slides"
    resolution: tuple[int, int] = (1080, 1920)
    fps: int = 30
    bgm: bool = False
    subtitle_style: SubtitleStyle = field(default_factory=SubtitleStyle)

    @classmethod
    def from_dict(cls, d: dict) -> VideoConfig:
        fmt = str(d.get("default_format", "voice_slides"))
        if fmt not in VALID_VIDEO_FORMATS:
            raise ConfigError(f"config.yaml: [video] 不支持的 default_format: {fmt}")
        res = d.get("resolution", [1080, 1920])
        return cls(
            default_format=fmt,
            resolution=(int(res[0]), int(res[1])),
            fps=int(d.get("fps", 30)),
            bgm=bool(d.get("bgm", False)),
            subtitle_style=SubtitleStyle.from_dict(d.get("subtitle_style", {})),
        )


@dataclass(frozen=True)
class PlatformConfig:
    enabled: bool = True
    format: str = "voice_slides"
    channel: str = "rpa"
    publish_time: str = "19:00"

    @classmethod
    def from_dict(cls, d: dict) -> PlatformConfig:
        channel = str(d.get("channel", "rpa"))
        if channel not in VALID_CHANNELS:
            raise ConfigError(f"config.yaml: 不支持的发布通道类型: {channel}")
        return cls(
            enabled=bool(d.get("enabled", True)),
            format=str(d.get("format", "voice_slides")),
            channel=channel,
            publish_time=str(d.get("publish_time", "19:00")),
        )


@dataclass(frozen=True)
class PublishConfig:
    confirm_before_publish: bool = True
    max_retry: int = 2
    headless: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> PublishConfig:
        return cls(
            confirm_before_publish=bool(d.get("confirm_before_publish", True)),
            max_retry=int(d.get("max_retry", 2)),
            headless=bool(d.get("headless", True)),
        )


@dataclass(frozen=True)
class TopicsConfig:
    sources: list[str] = field(default_factory=lambda: ["baidu_hot", "weibo_hot"])
    candidates_per_run: int = 6
    min_score: float = 60.0
    dedup_days: int = 30

    @classmethod
    def from_dict(cls, d: dict) -> TopicsConfig:
        return cls(
            sources=list(d.get("sources", ["baidu_hot", "weibo_hot"])),
            candidates_per_run=int(d.get("candidates_per_run", 6)),
            min_score=float(d.get("min_score", 60.0)),
            dedup_days=int(d.get("dedup_days", 30)),
        )


@dataclass(frozen=True)
class ForgeConfig:
    name: str = "ContentForge"
    timezone: str = "Asia/Shanghai"
    cadence: str = "daily"
    daily_target: int = 1

    @classmethod
    def from_dict(cls, d: dict) -> ForgeConfig:
        cadence = str(d.get("cadence", "daily"))
        if cadence not in VALID_CADENCES:
            raise ConfigError(f"config.yaml: [forge] 不支持的 cadence: {cadence}")
        return cls(
            name=str(d.get("name", "ContentForge")),
            timezone=str(d.get("timezone", "Asia/Shanghai")),
            cadence=cadence,
            daily_target=int(d.get("daily_target", 1)),
        )


class Config:
    """Loaded, validated, typed configuration.

    Example::

        cfg = Config("config.yaml")
        niche = cfg.direction.niche
        model = cfg.llm.model
        douyin = cfg.platforms["douyin"]
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_CONFIG_PATH
        # runtime-only override (never persisted): used by `publish --show`
        self.headless_override: bool | None = None
        self.raw: dict[str, Any] = self._load()
        self.forge: ForgeConfig = ForgeConfig.from_dict(self.raw.get("forge", {}))
        self.direction: DirectionConfig = DirectionConfig.from_dict(
            self.raw.get("direction", {}))
        self.llm: LLMConfig = LLMConfig.from_dict(self.raw.get("llm", {}))
        self.tts: TTSConfig = TTSConfig.from_dict(self.raw.get("tts", {}))
        self.image_source: ImageSourceConfig = ImageSourceConfig.from_dict(
            self.raw.get("image_source", {}))
        self.video: VideoConfig = VideoConfig.from_dict(self.raw.get("video", {}))
        self.publish: PublishConfig = PublishConfig.from_dict(
            self.raw.get("publish", {}))
        self.topics: TopicsConfig = TopicsConfig.from_dict(
            self.raw.get("topics", {}))
        self.platforms: dict[str, PlatformConfig] = {
            name: PlatformConfig.from_dict(p)
            for name, p in (self.raw.get("platforms") or {}).items()
        }
        if not self.platforms:
            raise ConfigError("config.yaml: [platforms] 不能为空")

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            raise ConfigError(f"配置文件不存在: {self.path}")
        with open(self.path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        if not isinstance(cfg, dict):
            raise ConfigError(f"配置文件格式错误（应为 YAML 映射）: {self.path}")
        return cfg

    def reload(self) -> Config:
        """Re-parse the YAML and rebuild all typed sections in place."""
        self.raw = self._load()
        self.forge = ForgeConfig.from_dict(self.raw.get("forge", {}))
        self.direction = DirectionConfig.from_dict(self.raw.get("direction", {}))
        self.llm = LLMConfig.from_dict(self.raw.get("llm", {}))
        self.tts = TTSConfig.from_dict(self.raw.get("tts", {}))
        self.image_source = ImageSourceConfig.from_dict(
            self.raw.get("image_source", {}))
        self.video = VideoConfig.from_dict(self.raw.get("video", {}))
        self.publish = PublishConfig.from_dict(self.raw.get("publish", {}))
        self.topics = TopicsConfig.from_dict(self.raw.get("topics", {}))
        self.platforms = {
            name: PlatformConfig.from_dict(p)
            for name, p in (self.raw.get("platforms") or {}).items()
        }
        return self

    def enabled_platforms(self) -> dict[str, PlatformConfig]:
        """Return only platforms that are switched on."""
        return {name: p for name, p in self.platforms.items() if p.enabled}

    def headless_active(self) -> bool:
        """Effective headless mode (CLI override wins over config.yaml)."""
        if self.headless_override is not None:
            return self.headless_override
        return self.publish.headless
