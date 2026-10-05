"""Shared pytest fixtures: isolated project dir + typed Config + DB.

Everything points at a per-test temp directory so CI stays hermetic and the
developer's real state/data are never touched.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from contentforge.config import Config
from contentforge.db import DB

TEST_CONFIG = """\
forge:
  timezone: "Asia/Shanghai"
  cadence: "daily"
  daily_target: 1

direction:
  niche: "University student growth"
  audience: "students"
  language: "en-US"
  style: "authentic, practical"
  must_avoid: "clickbait"
  content_formats: "short video"
  hooks: "pain-point question"

llm:
  base_url: "http://127.0.0.1:9/v1"
  api_key: "test"
  model: "mock"

tts:
  engine: "edge"
  voice: "en-US-AriaNeural"
  rate: "+8%"
  pitch: "+0Hz"

image_source:
  engine: "local"
  local_dir: ""

video:
  default_format: "voice_slides"
  resolution: [1080, 1920]
  fps: 30
  bgm: false
  subtitle_style:
    font: "msyhbd"
    font_size_ratio: 0.052
    font_color: "#FFFFFF"
    stroke_color: "#000000"
    position: "bottom"
    margin_ratio: 0.08

platforms:
  douyin: {enabled: true, format: "voice_slides", channel: "rpa", publish_time: "19:00"}
  youtube: {enabled: true, format: "voice_slides", channel: "api", publish_time: "21:00"}
  video_account: {enabled: true, format: "voice_slides", channel: "manual", publish_time: "20:30"}

publish:
  confirm_before_publish: true
  max_retry: 2
  headless: true

topics:
  sources: []
  candidates_per_run: 6
  min_score: 60
  dedup_days: 30
"""


@pytest.fixture()
def tmp_project(tmp_path: Path, monkeypatch) -> Path:
    """A temp project root with config.yaml and isolated data/state dirs."""
    config = tmp_path / "config.yaml"
    config.write_text(TEST_CONFIG, encoding="utf-8")
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"
    monkeypatch.setenv("FORGE_DATA", str(data_dir))
    monkeypatch.setenv("FORGE_STATE", str(state_dir))
    monkeypatch.setenv("FORGE_DB", str(state_dir / "forge.db"))
    return tmp_path


@pytest.fixture()
def cfg(tmp_project: Path) -> Config:
    return Config(tmp_project / "config.yaml")


@pytest.fixture()
def db(tmp_project: Path) -> DB:
    """Explicit path so tests never touch the developer's real state dir."""
    return DB(tmp_project / "state" / "forge.db")
