"""Config loading, validation and typed access tests."""
from __future__ import annotations

from pathlib import Path

import pytest
from contentforge.config import Config, ConfigError


def test_config_loads_typed_sections(cfg: Config):
    assert cfg.direction.niche == "University student growth"
    assert cfg.direction.language == "en-US"
    assert cfg.llm.base_url == "http://127.0.0.1:9/v1"
    assert cfg.video.resolution == (1080, 1920)
    assert cfg.tts.voice == "en-US-AriaNeural"
    assert "douyin" in cfg.platforms
    assert cfg.platforms["douyin"].channel == "rpa"
    assert cfg.platforms["video_account"].channel == "manual"
    assert cfg.publish.max_retry == 2


def test_enabled_platforms_filters_disabled(cfg: Config):
    enabled = cfg.enabled_platforms()
    assert set(enabled.keys()) == {"douyin", "youtube", "video_account"}


def test_direction_to_prompt_contains_niche(cfg: Config):
    prompt = cfg.direction.to_prompt()
    assert "University student growth" in prompt
    assert "Red lines" in prompt
    assert "Clickbait" in prompt.lower() or "clickbait" in prompt.lower()


def test_missing_niche_raises(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("""\
llm:
  base_url: "http://x/v1"
  api_key: "k"
  model: "m"
direction:
  audience: "x"
platforms:
  douyin: {enabled: true}
""", encoding="utf-8")
    with pytest.raises(ConfigError, match="niche"):
        Config(bad)


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(ConfigError, match="配置文件不存在"):
        Config(tmp_path / "nope.yaml")


def test_invalid_channel_raises(tmp_path: Path):
    bad = tmp_path / "bad2.yaml"
    bad.write_text("""\
llm:
  base_url: "http://x/v1"
  api_key: "k"
  model: "m"
direction:
  niche: "x"
platforms:
  douyin: {enabled: true, channel: "magic"}
""", encoding="utf-8")
    with pytest.raises(ConfigError, match="通道类型"):
        Config(bad)


def test_invalid_cadence_raises(tmp_path: Path):
    bad = tmp_path / "bad3.yaml"
    bad.write_text("""\
llm:
  base_url: "http://x/v1"
  api_key: "k"
  model: "m"
forge:
  cadence: "hourly"
direction:
  niche: "x"
platforms:
  douyin: {enabled: true}
""", encoding="utf-8")
    with pytest.raises(ConfigError, match="cadence"):
        Config(bad)


def test_reload_picks_up_changes(tmp_path: Path):
    config = tmp_path / "config.yaml"
    base = """\
llm:
  base_url: "http://x/v1"
  api_key: "k"
  model: "m"
direction:
  niche: "{niche}"
platforms:
  douyin: {enabled: true}
"""
    config.write_text(base.replace("{niche}", "old"), encoding="utf-8")
    c = Config(config)
    assert c.direction.niche == "old"
    config.write_text(base.replace("{niche}", "new direction"), encoding="utf-8")
    c.reload()
    assert c.direction.niche == "new direction"


def test_env_api_key_resolution(monkeypatch):
    from contentforge.config import LLMConfig
    # config key wins when set
    cfg_with_key = LLMConfig(base_url="http://x/v1", api_key="cfg-key", model="m")
    monkeypatch.setenv("LLM_API_KEY", "env-key")
    assert cfg_with_key.resolve_api_key() == "cfg-key"
    # env is the fallback when config is empty
    cfg_empty = LLMConfig(base_url="http://x/v1", api_key="", model="m")
    assert cfg_empty.resolve_api_key() == "env-key"
    assert cfg_empty.ready()
