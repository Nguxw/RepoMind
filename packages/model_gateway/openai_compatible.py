from __future__ import annotations

import json
import os
from typing import Any

import httpx

from packages.model_gateway.base import BaseModelClient, ModelUsage


class OpenAICompatibleClient(BaseModelClient):
    provider = "openai_compatible"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.timeout_seconds = timeout_seconds

    async def generate_text(self, messages: list[dict[str, Any]]) -> str:
        payload = await self._chat_completion(messages)
        return _extract_content(payload)

    async def generate_json(self, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        try:
            payload = await self._chat_completion(
                messages,
                extra={
                    "response_format": {"type": "json_object"},
                },
            )
        except httpx.HTTPStatusError:
            payload = await self._chat_completion(messages)
        content = _extract_content(payload)
        try:
            return json.loads(_strip_json_fences(content))
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
            payload = response.json()
            self.record_usage(_usage_from_payload(payload))
            return payload


def _extract_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, list):
        return "\n".join(str(part.get("text", part)) for part in content)
    return str(content)


def _strip_json_fences(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def _usage_from_payload(payload: dict[str, Any]) -> ModelUsage:
    usage = payload.get("usage") or {}
    return ModelUsage(
        input_tokens=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
    )
