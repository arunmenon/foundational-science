"""LLM clients for the generator.

OpenAIChatClient — talks to any OpenAI-compatible Chat Completions endpoint (function-calling),
using only the Python stdlib (urllib), so there is no SDK dependency. Configure via env vars:
    OPENAI_BASE_URL  (e.g. https://api.openai.com/v1  or your endpoint)
    OPENAI_API_KEY
    OPENAI_MODEL     (e.g. gpt-4o, gpt-4.1, or your deployed model name)

ReplayClient — a deterministic fixture that replays pre-recorded assistant messages. It is NOT a
model and does not approximate one; it exists only to exercise the generation loop offline in
tests (so we can validate the harness plumbing before the live endpoint is wired).
"""
from __future__ import annotations

import json
import os
import urllib.request


class OpenAIChatClient:
    def __init__(self, base_url=None, api_key=None, model=None, temperature=0.0, timeout=90):
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
        self.temperature = temperature
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set (export it, or pass api_key=).")

    def complete(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None) -> dict:
        """Return the assistant message dict ({content, tool_calls?})."""
        payload = {"model": self.model, "messages": messages, "temperature": self.temperature}
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice
        if parallel_tool_calls is not None:
            # Prefer sequential tool calls for this stepwise env. Endpoints may ignore it, so the
            # generator + lifecycle checker also validate server-side (review F1).
            payload["parallel_tool_calls"] = parallel_tool_calls
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        choices = body.get("choices")
        if not choices:
            raise RuntimeError(f"no choices in completion response: {str(body)[:300]}")
        return choices[0]["message"]


class ReplayClient:
    """Replays scripted assistant-message dicts in order (offline test fixture only)."""

    def __init__(self, scripted_messages):
        self._queue = list(scripted_messages)
        self.model = "replay"

    def complete(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None) -> dict:
        if not self._queue:
            raise RuntimeError("ReplayClient exhausted — script more turns.")
        return self._queue.pop(0)
