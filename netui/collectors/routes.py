from __future__ import annotations

import asyncio
import logging
from typing import TypedDict

from netui.platforms import platform

logger = logging.getLogger(__name__)


class RouteData(TypedDict, total=False):
    interface: str
    destination: str
    gateway: str
    metric: int
    mask: str
    flags: int


async def get_routes() -> list[dict[str, object]]:
    """Return route dicts from platform backend."""
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, platform.get_routes)
    except Exception:
        logger.exception("Collector get_routes failed")
        return []


async def collect() -> list[dict[str, object]]:
    return await get_routes()
