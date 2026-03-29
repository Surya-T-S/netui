from __future__ import annotations

import asyncio
import logging
from typing import TypedDict

import psutil

from netui.platforms import platform

logger = logging.getLogger(__name__)


class InterfaceData(TypedDict):
    name: str
    ipv4: str | None
    ipv6: str | None
    mac: str | None
    mtu: int
    speed_mbps: int
    is_up: bool
    type: str
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int
    dropin: int
    dropout: int


async def get_interfaces() -> list[InterfaceData]:
    """Return interface dict keys: name, ipv4, ipv6, mac, mtu, speed_mbps, is_up, type, bytes_sent, bytes_recv, packets_sent, packets_recv, errin, errout, dropin, dropout."""
    try:
        loop = asyncio.get_running_loop()
        base_interfaces = await loop.run_in_executor(None, platform.get_interfaces)
        pernic = psutil.net_io_counters(pernic=True)

        result: list[InterfaceData] = []
        for iface in base_interfaces:
            name_obj = iface.get("name")
            name = str(name_obj) if isinstance(name_obj, str) else ""
            counters = pernic.get(name)
            ipv4_obj = iface.get("ipv4")
            ipv6_obj = iface.get("ipv6")
            mac_obj = iface.get("mac")
            mtu_obj = iface.get("mtu")
            speed_obj = iface.get("speed_mbps")
            is_up_obj = iface.get("is_up")
            type_obj = iface.get("type")
            result.append(
                {
                    "name": name,
                    "ipv4": ipv4_obj if isinstance(ipv4_obj, str) else None,
                    "ipv6": ipv6_obj if isinstance(ipv6_obj, str) else None,
                    "mac": mac_obj if isinstance(mac_obj, str) else None,
                    "mtu": int(mtu_obj) if isinstance(mtu_obj, (int, float)) else 0,
                    "speed_mbps": int(speed_obj) if isinstance(speed_obj, (int, float)) else 0,
                    "is_up": bool(is_up_obj) if isinstance(is_up_obj, bool) else False,
                    "type": str(type_obj) if isinstance(type_obj, str) else "unknown",
                    "bytes_sent": int(counters.bytes_sent if counters else 0),
                    "bytes_recv": int(counters.bytes_recv if counters else 0),
                    "packets_sent": int(counters.packets_sent if counters else 0),
                    "packets_recv": int(counters.packets_recv if counters else 0),
                    "errin": int(counters.errin if counters else 0),
                    "errout": int(counters.errout if counters else 0),
                    "dropin": int(counters.dropin if counters else 0),
                    "dropout": int(counters.dropout if counters else 0),
                }
            )
        return result
    except Exception:
        logger.exception("Collector get_interfaces failed")
        return []


async def collect() -> list[InterfaceData]:
    return await get_interfaces()
