"""OpenAI-compatible LLM client.

Speaks the ``/chat/completions`` protocol against any OpenAI-compatible
endpoint (DeepSeek, OpenAI, Doubao, Agnes, vLLM, ...). Provides:

- ``chat``      — plain completion text
- ``chat_json`` — JSON completion with fence-stripping and recovery parsing

Usage::

    llm = LLMClient(cfg.llm)          # pass the typed LLMConfig
    text = llm.chat([{"role": "user", "content": "..."}])
    data = llm.chat_json([...])
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

import requests

from ..config import LLMConfig
from .log import get_logger

log = get_logger("llm")


class LLMError(Exception):
    """Raised when the LLM call fails after retries or returns unparsable JSON."""


class LLMClient:
    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg

    @property
    def base_url(self) -> str:
        return self.cfg.base_url

    def ready(self) -> bool:
        return self.cfg.ready()

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        if not self.ready():
            raise LLMError(
                "LLM is not configured: set base_url / api_key / model in config.yaml "
                "under [llm], or export LLM_API_KEY / LLM_MODEL."
            )
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.cfg.resolve_model(),
            "messages": messages,
            "temperature": self.cfg.temperature if temperature is None else temperature,
            "max_tokens": self.cfg.max_tokens if max_tokens is None else max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.cfg.resolve_api_key()}",
            "Content-Type": "application/json",
        }
        last_detail = ""
        for attempt in range(1, self.cfg.max_retries + 1):
            try:
                resp = requests.post(url, json=payload, headers=headers,
                                     timeout=self.cfg.timeout)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            except requests.RequestException as e:
                try:
                    last_detail = resp.json().get("error", {}).get("message", str(e))
                except Exception:
                    last_detail = str(e)
                log.warning(f"LLM call failed (attempt {attempt}/{self.cfg.max_retries}): "
                            f"{last_detail}")
                if attempt < self.cfg.max_retries:
                    time.sleep(2 * attempt)
        raise LLMError(f"LLM call failed after {self.cfg.max_retries} attempts: {last_detail}")

    def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Request a JSON object; strips markdown fences and recovers partial JSON."""
        messages = [*messages]
        messages.append({
            "role": "system",
            "content": "Output only a valid JSON object. No extra text, no markdown fences.",
        })
        text = self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        text = _strip_fences(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError as err:
            start, end = text.find("{"), text.rfind("}")
            if 0 <= start < end:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            log.error(f"LLM returned invalid JSON (first 200 chars): {text[:200]}")
            raise LLMError("LLM did not return a valid JSON object") from err


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()
