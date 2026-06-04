from __future__ import annotations

import os

from arq.connections import RedisSettings


async def generate_wiki_job(ctx):
    # The API keeps inline execution as the default MVP path. This worker entrypoint
    # reserves the Redis/Arq surface for long-running jobs once repository IDs are
    # passed through durable storage.
    return {"status": "queued-worker-ready"}


class WorkerSettings:
    functions = [generate_wiki_job]
    redis_settings = RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://redis:6379/0"))
