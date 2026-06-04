import pytest

from packages.tasks import InlineTaskQueue


@pytest.mark.asyncio
async def test_inline_task_queue_executes_coroutine():
    queue = InlineTaskQueue()

    handle = await queue.enqueue("demo", lambda: _ok())

    assert handle.status == "completed"
    assert handle.result == {"ok": True}


async def _ok():
    return {"ok": True}
