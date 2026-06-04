from __future__ import annotations

import os
from typing import Any, Awaitable, Callable
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskHandle(BaseModel):
    task_id: str = Field(default_factory=lambda: uuid4().hex)
    status: str = "completed"
    result: Any = None


class InlineTaskQueue:
    mode = "inline"

    async def enqueue(self, name: str, func: Callable[[], Awaitable[Any]]) -> TaskHandle:
        result = await func()
        return TaskHandle(status="completed", result=result)


class ArqTaskQueue:
    mode = "arq"

    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")

    async def enqueue(self, name: str, func: Callable[[], Awaitable[Any]]) -> TaskHandle:
        try:
            from arq import create_pool
            from arq.connections import RedisSettings
        except ImportError as exc:
            raise RuntimeError("arq is not installed. Install repomind[queue] or use REPOMIND_QUEUE_MODE=inline.") from exc

        settings = _redis_settings(self.redis_url)
        redis = await create_pool(settings)
        job = await redis.enqueue_job(name)
        return TaskHandle(task_id=job.job_id, status="queued")


def create_task_queue():
    mode = os.getenv("REPOMIND_QUEUE_MODE", "inline").lower()
    if mode == "arq":
        return ArqTaskQueue()
    return InlineTaskQueue()


def _redis_settings(redis_url: str):
    from urllib.parse import urlparse
    from arq.connections import RedisSettings

    parsed = urlparse(redis_url)
    return RedisSettings(host=parsed.hostname or "localhost", port=parsed.port or 6379, database=int((parsed.path or "/0").lstrip("/") or 0))
