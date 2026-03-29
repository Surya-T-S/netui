from __future__ import annotations

import asyncio
import logging
from typing import TypedDict

from netui.platforms import platform

logger = logging.getLogger(__name__)


class WifiInfo(TypedDict):
    ssid: str | None
    bssid: str | None
    frequency_mhz: int | None
    channel: int | None
    signal_dbm: float | None
    quality_pct: int | None
    tx_bitrate_mbps: float | None
    interface: str | None
    error: str | None


async def get_wifi_info() -> WifiInfo:
    """Return Wi-Fi info keys: ssid, bssid, frequency_mhz, channel, signal_dbm, quality_pct, tx_bitrate_mbps, interface, error."""
    try:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, platform.get_wifi_info)
        ssid_obj = data.get("ssid")
        bssid_obj = data.get("bssid")
        freq_obj = data.get("frequency_mhz")
        channel_obj = data.get("channel")
        signal_obj = data.get("signal_dbm")
        quality_obj = data.get("quality_pct")
        tx_obj = data.get("tx_bitrate_mbps")
        iface_obj = data.get("interface")
        error_obj = data.get("error")

        return {
            "ssid": ssid_obj if isinstance(ssid_obj, str) else None,
            "bssid": bssid_obj if isinstance(bssid_obj, str) else None,
            "frequency_mhz": int(freq_obj) if isinstance(freq_obj, (int, float)) else None,
            "channel": int(channel_obj) if isinstance(channel_obj, (int, float)) else None,
            "signal_dbm": float(signal_obj) if isinstance(signal_obj, (int, float)) else None,
            "quality_pct": int(quality_obj) if isinstance(quality_obj, (int, float)) else None,
            "tx_bitrate_mbps": float(tx_obj) if isinstance(tx_obj, (int, float)) else None,
            "interface": iface_obj if isinstance(iface_obj, str) else None,
            "error": error_obj if isinstance(error_obj, str) else None,
        }
    except Exception as exc:
        logger.exception("Collector get_wifi_info failed")
        return {
            "ssid": None,
            "bssid": None,
            "frequency_mhz": None,
            "channel": None,
            "signal_dbm": None,
            "quality_pct": None,
            "tx_bitrate_mbps": None,
            "interface": None,
            "error": str(exc),
        }


async def collect() -> WifiInfo:
    return await get_wifi_info()
