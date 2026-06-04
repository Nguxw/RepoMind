from __future__ import annotations

import os

from packages.model_gateway.openai_compatible import OpenAICompatibleClient


class DeepSeekClient(OpenAICompatibleClient):
    provider = "deepseek"

    def __init__(self) -> None:
        super().__init__(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        )
