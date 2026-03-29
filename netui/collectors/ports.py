from __future__ import annotations

import asyncio
import logging
from typing import TypedDict

from netui.platforms import platform

logger = logging.getLogger(__name__)


class OpenPortData(TypedDict):
    pid: int | None
    process: str
    proto: str
    local_ip: str
    local_port: int
    remote_ip: str
    remote_port: int
    state: str


def _state_priority(state: str) -> int:
    if state == "LISTEN":
        return 0
    if state == "ESTABLISHED":
        return 1
    return 2


async def get_open_ports(filter_state: str | None = None) -> list[OpenPortData]:
    """Return open-port dict keys: pid, process, proto, local_ip, local_port, remote_ip, remote_port, state."""
    try:
        loop = asyncio.get_running_loop()
        raw_ports = await loop.run_in_executor(None, platform.get_open_ports)

        ports: list[OpenPortData] = []
        for item in raw_ports:
            pid_obj = item.get("pid")
            local_port_obj = item.get("local_port")
            remote_port_obj = item.get("remote_port")
            state_obj = item.get("state")
            ports.append(
                {
                    "pid": int(pid_obj) if isinstance(pid_obj, int) else None,
                    "process": str(item.get("process") or "<unknown>"),
                    "proto": str(item.get("proto") or "TCP"),
                    "local_ip": str(item.get("local_ip") or ""),
                    "local_port": int(local_port_obj) if isinstance(local_port_obj, (int, float)) else 0,
                    "remote_ip": str(item.get("remote_ip") or ""),
                    "remote_port": int(remote_port_obj) if isinstance(remote_port_obj, (int, float)) else 0,
                    "state": str(state_obj) if isinstance(state_obj, str) else "NONE",
                }
            )

        if filter_state is not None:
            target = filter_state.upper()
            ports = [p for p in ports if str(p.get("state", "")).upper() == target]

        return sorted(
            ports,
            key=lambda p: (
                _state_priority(str(p.get("state", ""))),
                int(p.get("local_port", 0)),
            ),
        )
    except Exception:
        logger.exception("Collector get_open_ports failed")
        return []


async def collect(filter_state: str | None = None) -> list[OpenPortData]:
    return await get_open_ports(filter_state=filter_state)
