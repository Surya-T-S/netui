from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import sys
from typing import TypedDict

from icmplib import async_ping, ping  # type: ignore[import-untyped]

from netui import config

logger = logging.getLogger(__name__)


class PingResult(TypedDict):
    host: str
    avg_ms: float
    min_ms: float
    max_ms: float
    jitter_ms: float
    packet_loss_pct: float
    is_alive: bool
    fallback_mode: bool


icmp_fallback_mode = False
_icmp_probed = False


def _default_ping(host: str) -> PingResult:
    return {
        "host": host,
        "avg_ms": 0.0,
        "min_ms": 0.0,
        "max_ms": 0.0,
        "jitter_ms": 0.0,
        "packet_loss_pct": 100.0,
        "is_alive": False,
        "fallback_mode": True,
    }


def _ensure_icmp_mode() -> None:
    global icmp_fallback_mode, _icmp_probed
    if _icmp_probed:
        return
    _icmp_probed = True

    if config.limited_mode or sys.platform == "win32":
        icmp_fallback_mode = config.limited_mode
        return

    try:
        ping("127.0.0.1", count=1, timeout=1)
        icmp_fallback_mode = False
    except PermissionError:
        icmp_fallback_mode = True
    except OSError:
        icmp_fallback_mode = True
    except Exception:
        icmp_fallback_mode = False


def _parse_ping_avg_ms(output: str) -> float:
    unix_match = re.search(
        r"(?:round-trip|rtt)\s+min/avg/max(?:/mdev)?\s*=\s*[0-9.]+/([0-9.]+)/[0-9.]+",
        output,
    )
    if unix_match:
        return float(unix_match.group(1))

    win_match = re.search(
        r"Average\s*=\s*(\d+)ms",
        output,
        flags=re.IGNORECASE,
    )
    if win_match:
        return float(win_match.group(1))

    return 0.0


def _run_ping_subprocess(host: str, count: int) -> subprocess.CompletedProcess[str]:
    if sys.platform == "win32":
        cmd = ["ping", "-n", str(count), "-w", "2000", host]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
            timeout=5,
            check=False,
        )

    cmd = ["ping", "-c", str(count), "-W", "2", host]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )


async def _subprocess_ping(host: str, count: int) -> PingResult:
    result = _default_ping(host)
    try:
        loop = asyncio.get_running_loop()
        proc = await loop.run_in_executor(None, _run_ping_subprocess, host, count)
        text = (proc.stdout or "") + "\n" + (proc.stderr or "")
        avg = _parse_ping_avg_ms(text)
        result["avg_ms"] = avg
        result["is_alive"] = proc.returncode == 0
        result["packet_loss_pct"] = 0.0 if proc.returncode == 0 else 100.0
        result["fallback_mode"] = True
    except subprocess.TimeoutExpired:
        logger.warning("Subprocess ping timed out for %s", host)
        result["fallback_mode"] = True
    except Exception:
        logger.exception("Subprocess ping failed for %s", host)
        result["fallback_mode"] = True
    return result


async def ping_host(host: str, count: int = 10) -> PingResult:
    """Return ping result keys: host, avg_ms, min_ms, max_ms, jitter_ms, packet_loss_pct, is_alive."""
    global icmp_fallback_mode
    _ensure_icmp_mode()
    if icmp_fallback_mode:
        return await _subprocess_ping(host, count)

    try:
        response = await async_ping(host, count=count, interval=0.2, timeout=2)  # type: ignore[arg-type]
        min_ms = float(getattr(response, "min_rtt", 0.0) or 0.0)
        max_ms = float(getattr(response, "max_rtt", 0.0) or 0.0)
        avg_ms = float(getattr(response, "avg_rtt", 0.0) or 0.0)
        return {
            "host": host,
            "avg_ms": avg_ms,
            "min_ms": min_ms,
            "max_ms": max_ms,
            "jitter_ms": max(0.0, max_ms - min_ms),
            "packet_loss_pct": float(getattr(response, "packet_loss", 0.0) or 0.0),
            "is_alive": bool(getattr(response, "is_alive", False)),
            "fallback_mode": False,
        }
    except (PermissionError, OSError):
        icmp_fallback_mode = True
        logger.info("Permission denied for raw ping, falling back to subprocess ping")
        return await _subprocess_ping(host, count)
    except Exception as exc:
        if "permission" in str(exc).lower():
            icmp_fallback_mode = True
            return await _subprocess_ping(host, count)
        logger.exception("Ping failed for host %s", host)
        return _default_ping(host)


async def ping_all_hosts(hosts: list[str] | None = None) -> list[PingResult]:
    """Run ping_host concurrently and return successful result dicts only."""
    target_hosts = hosts or config.DEFAULT_PING_HOSTS
    gathered = await asyncio.gather(
        *[ping_host(host) for host in target_hosts],
        return_exceptions=True,
    )

    results: list[PingResult] = []
    for item in gathered:
        if isinstance(item, BaseException):
            logger.exception("ping_all_hosts worker failed", exc_info=item)
            continue
        results.append(item)
    return results


async def collect() -> list[PingResult]:
    return await ping_all_hosts()
