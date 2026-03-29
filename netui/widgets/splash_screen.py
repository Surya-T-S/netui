from __future__ import annotations

import asyncio
import platform as py_platform
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from netui.collectors.dns import resolve_host
from netui.collectors.interfaces import get_interfaces
from netui.collectors.latency import ping_host
from netui.collectors.wifi import get_wifi_info
from netui.platform import platform


class SplashScreen(Screen[dict[str, Any]]):
    DEFAULT_CSS = """
    SplashScreen {
        align: center middle;
        background: #060b12;
    }
    #splash-wrap {
        width: 92;
        border: round #30363d;
        padding: 1 2;
        background: #0d1117;
    }
    #splash-banner {
        color: #58a6ff;
        text-style: bold;
    }
    #splash-log {
        height: 8;
    }
    """

    BANNER = (
        "███╗   ██╗███████╗████████╗██╗   ██╗██╗\n"
        "████╗  ██║██╔════╝╚══██╔══╝██║   ██║██║\n"
        "██╔██╗ ██║█████╗     ██║   ██║   ██║██║\n"
        "██║╚██╗██║██╔══╝     ██║   ██║   ██║██║\n"
        "██║ ╚████║███████╗   ██║   ╚██████╔╝██║\n"
        "╚═╝  ╚═══╝╚══════╝   ╚═╝    ╚═════╝ ╚═╝\n"
        "Network Diagnostics TUI"
    )

    def __init__(self) -> None:
        super().__init__()
        self._lines: list[str] = []
        self._done = False
        self.cache: dict[str, Any] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="splash-wrap"):
            yield Static(self.BANNER + "\n", id="splash-banner")
            yield Static("", id="splash-log")

    def on_mount(self) -> None:
        self.run_worker(self._run_checks(), exclusive=True)

    async def _append(self, line: str) -> None:
        self._lines.append(line)
        self.query_one("#splash-log", Static).update("\n".join(self._lines[-8:]))
        await asyncio.sleep(0.12)

    async def _run_checks(self) -> None:
        plat = "Windows" if py_platform.system().lower().startswith("win") else "Linux"
        await self._append(f"[  OK  ] Detected platform: {plat}")

        interfaces = await get_interfaces()
        self.cache["interfaces"] = interfaces
        await self._append(f"[  OK  ] Found {len(interfaces)} network interfaces")

        dns_servers = platform.get_dns_servers()
        self.cache["dns_servers"] = dns_servers
        await self._append(f"[  OK  ] DNS servers: {', '.join(dns_servers[:3]) if dns_servers else 'none'}")

        ping = await ping_host("8.8.8.8", count=1)
        self.cache["initial_ping"] = ping
        await self._append(f"[  OK  ] Initial ping: {ping.get('avg_ms', 0.0):.1f} ms to 8.8.8.8")

        wifi = await get_wifi_info()
        self.cache["wifi"] = wifi
        if wifi.get("error"):
            await self._append("[ INFO ] Wi-Fi not available")
        else:
            await self._append("[  OK  ] Wi-Fi adapter available")

        _ = await resolve_host("google.com")
        await self._append("[ INFO ] Ready. Press any key to continue...")
        self._done = True
        await asyncio.sleep(0.2)
        self.dismiss(self.cache)

    def on_key(self) -> None:
        self.dismiss(self.cache)
