from __future__ import annotations

import logging
import os
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import TypedDict

import httpx

from netui import config
from netui.collectors.latency import ping_host

logger = logging.getLogger(__name__)


class SpeedTestResult(TypedDict, total=False):
    download_mbps: float
    upload_mbps: float
    latency_ms: float
    timestamp: str
    error: str


async def run_speed_test(
    progress_callback: Callable[[str, int, float], Awaitable[None]] | None = None,
) -> SpeedTestResult:
    """Return speed-test dict keys: download_mbps, upload_mbps, latency_ms, timestamp, optional error."""
    default_result: SpeedTestResult = {
        "download_mbps": 0.0,
        "upload_mbps": 0.0,
        "latency_ms": 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        ping = await ping_host("8.8.8.8", count=1)
        latency_ms = float(ping.get("avg_ms", 0.0))

        download_mbps = 0.0
        async with httpx.AsyncClient(timeout=30) as client:
            start = time.monotonic()
            total_bytes = 0
            async with client.stream("GET", config.SPEED_TEST_URL_DOWN) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    total_bytes += len(chunk)
                    elapsed = time.monotonic() - start
                    if progress_callback:
                        await progress_callback("download", total_bytes, elapsed)
            elapsed = max(time.monotonic() - start, 1e-9)
            download_mbps = (total_bytes * 8.0) / (elapsed * 1_000_000)

        data = os.urandom(5_000_000)
        start_up = time.monotonic()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(config.SPEED_TEST_URL_UP, content=data)
            response.raise_for_status()
        elapsed_up = max(time.monotonic() - start_up, 1e-9)
        upload_mbps = (len(data) * 8.0) / (elapsed_up * 1_000_000)

        return {
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
            "latency_ms": latency_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.exception("Speed test failed")
        return {
            **default_result,
            "error": str(exc),
            "download_mbps": 0.0,
            "upload_mbps": 0.0,
        }


async def collect() -> SpeedTestResult:
    return await run_speed_test()
