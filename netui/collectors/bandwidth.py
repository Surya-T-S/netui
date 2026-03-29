from __future__ import annotations

import logging
import time
from typing import Any
from typing import TypedDict

import psutil

from netui.utils.history import RollingHistory

logger = logging.getLogger(__name__)


class InterfaceBandwidth(TypedDict):
    rx_bps: float
    tx_bps: float
    rx_history: list[float]
    tx_history: list[float]
    total_rx: int
    total_tx: int


class BandwidthMonitor:
    def __init__(self) -> None:
        self._history: dict[str, dict[str, RollingHistory]] = {}
        self._last_counters: dict[str, Any] = {}
        self._last_time: float | None = None

    async def poll(self) -> dict[str, InterfaceBandwidth]:
        """Return per-interface bandwidth keys: rx_bps, tx_bps, rx_history, tx_history, total_rx, total_tx."""
        try:
            current = psutil.net_io_counters(pernic=True)
            current_time = time.monotonic()
            result: dict[str, InterfaceBandwidth] = {}

            for iface, counters in current.items():
                if iface not in self._history:
                    self._history[iface] = {
                        "rx": RollingHistory(120),
                        "tx": RollingHistory(120),
                    }

                if self._last_counters and iface in self._last_counters and self._last_time:
                    dt = max(current_time - self._last_time, 1e-9)
                    rx_bps = (
                        counters.bytes_recv - self._last_counters[iface].bytes_recv
                    ) / dt
                    tx_bps = (
                        counters.bytes_sent - self._last_counters[iface].bytes_sent
                    ) / dt
                    self._history[iface]["rx"].push(rx_bps)
                    self._history[iface]["tx"].push(tx_bps)
                    result[iface] = {
                        "rx_bps": rx_bps,
                        "tx_bps": tx_bps,
                        "rx_history": self._history[iface]["rx"].get_last_n(60),
                        "tx_history": self._history[iface]["tx"].get_last_n(60),
                        "total_rx": counters.bytes_recv,
                        "total_tx": counters.bytes_sent,
                    }

            self._last_counters = current
            self._last_time = current_time
            return result
        except Exception:
            logger.exception("Bandwidth poll failed")
            return {}


_monitor = BandwidthMonitor()


async def collect() -> dict[str, InterfaceBandwidth]:
    return await _monitor.poll()
