from __future__ import annotations

import asyncio
import logging
import traceback
from collections.abc import Callable, Coroutine
from typing import Any


logger = logging.getLogger(__name__)


class TaskScheduler:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    async def _repeating_wrapper(
        self,
        name: str,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
        interval: float,
    ) -> None:
        while True:
            try:
                await coro_fn()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Task '%s' failed", name)
                with open("netui.log", "a", encoding="utf-8") as f:
                    f.write(f"Task '{name}' failed: {exc}\n")
                    f.write(traceback.format_exc())
                    f.write("\n")
            await asyncio.sleep(interval)

    def add_task(
        self,
        name: str,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
        interval_secs: float,
    ) -> None:
        if name in self._tasks:
            self._tasks[name].cancel()
        self._tasks[name] = asyncio.create_task(
            self._repeating_wrapper(name, coro_fn, interval_secs)
        )

    def run_once(
        self,
        name: str,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
        callback: Callable[[Any], None] | None = None,
    ) -> None:
        async def _wrapper() -> None:
            result = await coro_fn()
            if callback:
                callback(result)

        self._tasks[name] = asyncio.create_task(_wrapper())

    def cancel_all(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
