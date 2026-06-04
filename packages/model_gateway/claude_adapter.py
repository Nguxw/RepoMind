from __future__ import annotations

import os
from typing import Any

import httpx

from packages.model_gateway.base import BaseModelClient


class ClaudeClient(BaseModelClient):
    provider = "claude"

    def __init__(self) -> None:
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        self.base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")

    async def generate_text(self, messages: list[dict[str, Any]]) -> str:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for Claude model calls.")
        system = "\n".join(str(message.get("content", "")) for message in messages if message.get("role") == "system")
        user_messages = [
            {"role": message.get("role", "user"), "content": str(message.get("content", ""))}
            for message in messages
            if message.get("role") != "system"
        ]
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {"model": self.model, "max_tokens": 2048, "system": system, "messages": user_messages}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{self.base_url}/v1/messages", headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        return "\n".join(part.get("text", "") for part in payload.get("content", []) if part.get("type") == "text")

    async def generate_json(self, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        text = await self.generate_text([
            *messages,
            {"role": "user", "content": "Return only valid JSON."},
        ])
        import json

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}
