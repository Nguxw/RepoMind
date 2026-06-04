from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field


class ModelUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class ModelCallResult(BaseModel):
    content: str
    usage: ModelUsage = Field(default_factory=ModelUsage)
    raw: dict[str, Any] = Field(default_factory=dict)


class BaseModelClient:
    provider: str = "base"
    model: str = "unknown"

    async def generate_text(self, messages: list[dict[str, Any]]) -> str:
        raise NotImplementedError

    async def generate_json(self, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def stream(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        yield await self.generate_text(messages)
