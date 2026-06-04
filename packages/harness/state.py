from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from packages.wiki_engine.models import Citation


class ToolCall(BaseModel):
    tool: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    duration_ms: int = 0


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class AgentRun(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid4().hex)
    task: str
    repo_id: str
    status: str = "completed"
    model: str = "mock-repomind"
    steps: list[ToolCall] = Field(default_factory=list)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    output: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AskAnswer(BaseModel):
    question: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    run_id: str
