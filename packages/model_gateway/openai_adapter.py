from __future__ import annotations

import os

from packages.model_gateway.openai_compatible import OpenAICompatibleClient


class OpenAIClient(OpenAICompatibleClient):
    provider = "openai"

    def __init__(self) -> None:
        super().__init__(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        )
