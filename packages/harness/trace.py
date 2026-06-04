from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from packages.harness.state import ToolCall


def timed_tool(tool: str, input_payload: dict[str, Any], func: Callable[[], Any]) -> tuple[Any, ToolCall]:
    started = time.perf_counter()
    output = func()
    duration_ms = int((time.perf_counter() - started) * 1000)
    return output, ToolCall(tool=tool, input=input_payload, output=_compact(output), duration_ms=duration_ms)


def _compact(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_compact(item) for item in value[:20]]
    if isinstance(value, dict):
        return {key: _compact(item) for key, item in value.items()}
    return value
