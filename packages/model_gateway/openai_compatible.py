from __future__ import annotations

import json
import os
from typing import Any

import httpx

from packages.model_gateway.base import BaseModelClient


class OpenAICompatibleClient(BaseModelClient):
    provider = "openai_compatible"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.timeout_seconds = timeout_seconds

    async def generate_text(self, messages: list[dict[str, Any]]) -> str:
        payload = await self._chat_completion(messages)
        return _extract_content(payload)

    async def generate_json(self, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        payload = await self._chat_completion(
            messages,
            extra={
                "response_format": {"type": "json_object"},
            },
        )
        content = _extract_content(payload)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"raw": content}

    async def _chat_completion(self, messages: list[dict[str, Any]], extra: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI-compatible model calls.")

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        body: dict[str, Any] = {"model": self.model, "messages": messages}
        if extra:
            body.update(extra)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
            response.raise_for_status()
            return response.json()


def _extract_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, list):
        return "\n".join(str(part.get("text", part)) for part in content)
    return str(content)
