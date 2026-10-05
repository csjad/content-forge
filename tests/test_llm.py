"""LLM client tests using a stubbed HTTP transport (no network)."""
from __future__ import annotations

import pytest
import requests
from contentforge.config import LLMConfig
from contentforge.utils.llm import LLMClient, LLMError


class _FakeResponse:
    def __init__(self, status: int, payload: dict):
        self.status_code = status
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self):
        return self._payload


def _make_client(monkeypatch, responses: list[dict], status: int = 200) -> LLMClient:
    cfg = LLMConfig(base_url="http://example.test/v1", api_key="k", model="m")
    client = LLMClient(cfg)
    calls: list = []

    def fake_post(url, **kwargs):
        calls.append(url)
        return _FakeResponse(status, responses[min(len(calls) - 1, len(responses) - 1)])

    monkeypatch.setattr("requests.post", fake_post)
    client._calls = calls  # type: ignore[attr-defined]
    return client


def test_chat_returns_content(monkeypatch):
    client = _make_client(monkeypatch, [{
        "choices": [{"message": {"role": "assistant", "content": "  hello  "}}]
    }])
    assert client.chat([{"role": "user", "content": "hi"}]) == "hello"


def test_chat_json_strips_fences(monkeypatch):
    client = _make_client(monkeypatch, [{
        "choices": [{"message": {"role": "assistant",
                                 "content": '```json\n{"a": 1}\n```'}}]
    }])
    assert client.chat_json([{"role": "user", "content": "json please"}]) == {"a": 1}


def test_chat_json_recovers_substring(monkeypatch):
    client = _make_client(monkeypatch, [{
        "choices": [{"message": {"role": "assistant",
                                 "content": 'Sure, here it is: {"b": [1, 2]} done'}}]
    }])
    assert client.chat_json([{"role": "user", "content": "j"}]) == {"b": [1, 2]}


def test_chat_retries_then_raises(monkeypatch):
    client = _make_client(monkeypatch, [{}, {}, {}], status=500)
    with pytest.raises(LLMError, match="after 3 attempts"):
        client.chat([{"role": "user", "content": "x"}])


def test_chat_recovers_after_transient_failure(monkeypatch):
    client = _make_client(monkeypatch, [
        {},
        {"choices": [{"message": {"role": "assistant", "content": "recovered"}}]},
    ], status=500)
    # first response 500, second response 200 — fake_post always uses the
    # same status, so emulate a transient failure differently:
    calls: list = []

    def fake_post(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            return _FakeResponse(500, {})
        return _FakeResponse(200, {
            "choices": [{"message": {"role": "assistant", "content": "recovered"}}]
        })

    monkeypatch.setattr("requests.post", fake_post)
    assert client.chat([{"role": "user", "content": "x"}]) == "recovered"


def test_unconfigured_raises():
    cfg = LLMConfig(base_url="", api_key="", model="")
    with pytest.raises(LLMError, match="not configured"):
        LLMClient(cfg).chat([{"role": "user", "content": "x"}])
