from __future__ import annotations

import asyncio
import logging
import re
import socket
import sys
from collections.abc import AsyncGenerator
from typing import TypedDict

logger = logging.getLogger(__name__)

try:
    import icmplib  # type: ignore[import-untyped]

    _icmp_traceroute = getattr(icmplib, "async_traceroute", None)
except Exception:  # pragma: no cover
    _icmp_traceroute = None


class TraceHop(TypedDict):
    hop_num: int
    ip: str
    hostname: str
    latency_ms: float
    is_timeout: bool


def parse_tracert_windows_line(line: str) -> TraceHop | None:
    timeout_re = re.compile(r"^\s*(\d+)\s+\*\s+\*\s+\*\s+Request timed out\.?")
    win_hop_re = re.compile(
        r"^\s*(\d+)\s+(?:<)?(\d+|\*)\s*ms.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|\*)"
    )
    timeout_match = timeout_re.match(line.strip())
    if timeout_match:
        hop_num = int(timeout_match.group(1))
        return {
            "hop_num": hop_num,
            "ip": "*",
            "hostname": "*",
            "latency_ms": 0.0,
            "is_timeout": True,
        }

    m = win_hop_re.match(line.strip())
    if not m:
        return None
    hop_num = int(m.group(1))
    latency_token = m.group(2)
    ip = m.group(3)
    is_timeout = ip == "*" or latency_token == "*"
    latency_ms = 0.0
    if not is_timeout:
        try:
            latency_ms = float(latency_token)
        except ValueError:
            latency_ms = 0.0
    return {
        "hop_num": hop_num,
        "ip": ip,
        "hostname": ip,
        "latency_ms": latency_ms,
        "is_timeout": is_timeout,
    }


def parse_traceroute_linux_line(line: str) -> TraceHop | None:
    hop_re = re.compile(r"^\s*(\d+)\s+(.*)$")
    ip_re = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})")
    ms_re = re.compile(r"(<\d+|\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)
    match = hop_re.match(line.strip())
    if not match:
        return None
    hop_num = int(match.group(1))
    rest = match.group(2)
    ip_match = ip_re.search(rest)
    ip = ip_match.group(1) if ip_match else "*"
    is_timeout = ip == "*" or "*" in rest
    latency_ms = 0.0
    latency_match = ms_re.search(rest)
    if latency_match and not is_timeout:
        token = latency_match.group(1).replace("<", "")
        try:
            latency_ms = float(token)
        except ValueError:
            latency_ms = 0.0
    return {
        "hop_num": hop_num,
        "ip": ip,
        "hostname": ip,
        "latency_ms": latency_ms,
        "is_timeout": is_timeout,
    }


async def _resolve_hostname(ip: str) -> str:
    if ip == "*":
        return "*"
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, socket.getfqdn, ip),
            timeout=1.5,
        )
    except Exception:
        return ip


async def _trace_subprocess(host: str, max_hops: int) -> AsyncGenerator[TraceHop, None]:
    if sys.platform == "win32":
        cmd = ["tracert", "-d", "-w", "1000", "-h", str(max_hops), host]
    else:
        cmd = ["traceroute", "-n", "-m", str(max_hops), "-w", "1", host]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    assert proc.stdout is not None
    hop_re = re.compile(r"^\s*(\d+)\s+(.*)$")

    while True:
        line_bytes = await proc.stdout.readline()
        if not line_bytes:
            break
        line = line_bytes.decode(errors="ignore").strip()

        if sys.platform == "win32":
            parsed = parse_tracert_windows_line(line)
            if parsed is not None:
                hostname = await _resolve_hostname(parsed["ip"])
                parsed["hostname"] = hostname
                yield parsed
                continue

        match = hop_re.match(line)
        if not match:
            continue
        parsed = parse_traceroute_linux_line(line)
        if parsed is None:
            continue
        parsed["hostname"] = await _resolve_hostname(parsed["ip"])
        yield parsed

    await proc.wait()


async def trace_route(host: str, max_hops: int = 30) -> AsyncGenerator[TraceHop, None]:
    """Yield hop dicts with keys: hop_num, ip, hostname, latency_ms, is_timeout."""
    use_subprocess = sys.platform == "win32" or not callable(_icmp_traceroute)
    if not use_subprocess:
        try:
            assert _icmp_traceroute is not None
            hops = await _icmp_traceroute(host, max_hops=max_hops, count=1, timeout=1)
            for hop in hops:
                hop_distance = int(getattr(hop, "distance", 0) or 0)
                hop_address = getattr(hop, "address", None)
                hop_avg_rtt = float(getattr(hop, "avg_rtt", 0.0) or 0.0)

                ip = str(hop_address) if hop_address else "*"
                is_timeout = ip == "*"
                latency_ms = 0.0 if is_timeout else hop_avg_rtt
                hostname = await _resolve_hostname(ip)
                yield {
                    "hop_num": hop_distance,
                    "ip": ip,
                    "hostname": hostname,
                    "latency_ms": latency_ms,
                    "is_timeout": is_timeout,
                }
            return
        except PermissionError:
            logger.info("Permission denied for icmplib traceroute, falling back")
        except Exception:
            logger.exception("icmplib traceroute failed, falling back")

    try:
        async for hop in _trace_subprocess(host, max_hops):
            yield hop
    except FileNotFoundError:
        logger.exception("Traceroute command not available")
    except Exception:
        logger.exception("Traceroute subprocess fallback failed")


async def collect(host: str = "8.8.8.8", max_hops: int = 30) -> list[TraceHop]:
    hops: list[TraceHop] = []
    async for hop in trace_route(host, max_hops=max_hops):
        hops.append(hop)
    return hops
