from __future__ import annotations

import os

from packages.config import load_env_file
from packages.model_gateway.base import BaseModelClient
from packages.model_gateway.claude_adapter import ClaudeClient
from packages.model_gateway.deepseek_adapter import DeepSeekClient
from packages.model_gateway.mock_adapter import MockModelClient
from packages.model_gateway.openai_adapter import OpenAIClient
from packages.model_gateway.openai_compatible import OpenAICompatibleClient


def create_model_client(provider: str | None = None) -> BaseModelClient:
    load_env_file()
    selected = (provider or os.getenv("MODEL_PROVIDER", "mock")).lower()
    if selected in {"mock", "test"}:
        return MockModelClient()
    if selected in {"openai_compatible", "compatible"}:
        return OpenAICompatibleClient()
    if selected == "openai":
        return OpenAIClient()
    if selected == "deepseek":
        return DeepSeekClient()
    if selected in {"claude", "anthropic"}:
        return ClaudeClient()
    raise ValueError(f"Unsupported model provider: {selected}")
