"""Topic generator and script writer tests with a stubbed LLM."""
from __future__ import annotations

from contentforge.db import DB, TOPIC_CANDIDATE
from contentforge.topics.generator import TopicGenerator
from contentforge.writing.adapters import PlatformAdapter
from contentforge.writing.outline import ScriptWriter

TOPICS = [
    {"title": "Topic one", "summary": "s", "angle": "a", "score": 92, "reason": "r"},
    {"title": "Topic two", "summary": "s", "angle": "a", "score": 55, "reason": "low"},
]
SCRIPT = {
    "hook": "Hook line",
    "outline": ["point 1", "point 2"],
    "script_lines": ["Line one", "Line two", "Line three", "Line four"],
    "cta": "Follow me",
    "duration_est": 60,
}
ADAPTER = {
    "douyin": {"titles": ["T1", "T2", "T3"], "body": "b", "tags": ["#a", "#b"]},
    "youtube": {"titles_zh": ["YT1"], "titles_en": ["YT E"], "description": "d",
                "tags": ["tag"]},
}


def test_generate_filters_low_scores_and_writes_db(cfg, db: DB, monkeypatch):
    def fake_chat_json(*args, **kwargs):
        return TOPICS

    monkeypatch.setattr("contentforge.utils.llm.LLMClient.chat_json", fake_chat_json)
    gen = TopicGenerator(cfg, db)
    saved = gen.produce_candidates([])
    # score 55 < min_score 60 should be filtered out
    assert len(saved) == 1
    assert saved[0]["title"] == "Topic one"
    topics = db.list_topics(status=TOPIC_CANDIDATE)
    assert len(topics) == 1


def test_generate_dedup(cfg, db: DB, monkeypatch):
    db.add_topic("Topic one", "", "", 90, "", "ai", "snap")
    monkeypatch.setattr("contentforge.utils.llm.LLMClient.chat_json",
                        lambda *args, **kw: TOPICS)
    saved = TopicGenerator(cfg, db).produce_candidates([])
    assert saved == []  # already exists within dedup window


def test_script_writer_returns_structured_script(cfg, db: DB, monkeypatch):
    monkeypatch.setattr("contentforge.utils.llm.LLMClient.chat_json",
                        lambda *args, **kw: SCRIPT)
    topic = {"id": 1, "title": "T", "summary": "", "angle": ""}
    script = ScriptWriter(cfg, db).write(topic)
    assert script is not None
    assert len(script["script_lines"]) >= 3
    assert script["hook"] == "Hook line"


def test_script_writer_rejects_too_short(cfg, db: DB, monkeypatch):
    monkeypatch.setattr("contentforge.utils.llm.LLMClient.chat_json",
                        lambda *args, **kw: {"script_lines": ["only"]})
    topic = {"id": 1, "title": "T", "summary": "", "angle": ""}
    assert ScriptWriter(cfg, db).write(topic) is None


def test_platform_adapter_normalizes(cfg, monkeypatch):
    monkeypatch.setattr("contentforge.utils.llm.LLMClient.chat_json",
                        lambda *args, **kw: ADAPTER)
    result = PlatformAdapter(cfg).adapt(["l1", "l2"], ["o1"])
    assert result["douyin"]["titles"] == ["T1", "T2", "T3"]
    assert result["douyin"]["tags"] == ["#a", "#b"]
    assert result["youtube"]["tags"] == ["tag"]
