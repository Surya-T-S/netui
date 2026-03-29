from __future__ import annotations

from typing import cast

from typing import ClassVar
from typing import Any

import psutil
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import ListView

from netui import config
from netui.config import KEYBINDINGS, MODULE_LABELS
from netui.messages import InterfaceSelected, ModuleSelected
from netui.utils.toast import show_toast
from netui.utils.async_runner import TaskScheduler
from netui.widgets.bandwidth_panel import BandwidthPanel
from netui.widgets.content_area import ContentArea
from netui.widgets.dns_panel import DnsPanel
from netui.widgets.header import Header
from netui.widgets.help_screen import HelpScreen
from netui.widgets.interfaces_panel import InterfacesPanel
from netui.widgets.latency_panel import LatencyPanel
from netui.widgets.panel_base import PanelBase
from netui.widgets.ports_panel import PortsPanel
from netui.widgets.route_panel import RoutePanel
from netui.widgets.sidebar import Sidebar
from netui.widgets.speed_panel import SpeedPanel
from netui.widgets.splash_screen import SplashScreen
from netui.widgets.status_bar import StatusBar
from netui.widgets.traceroute_panel import TraceroutePanel
from netui.widgets.wifi_panel import WifiPanel
from netui.collectors import latency as latency_collector


def _app_bindings() -> list[BindingType]:
    bindings: list[Binding] = []
    for key, action in KEYBINDINGS.items():
        bindings.append(Binding(key, action, "", show=False))
    return cast(list[BindingType], bindings)


_MODULE_CLASSES: tuple[type[PanelBase], ...] = (
    LatencyPanel,
    SpeedPanel,
    DnsPanel,
    TraceroutePanel,
    InterfacesPanel,
    BandwidthPanel,
    PortsPanel,
    WifiPanel,
    RoutePanel,
)

MODULE_PANEL_MAP: dict[str, type[PanelBase]] = dict(
    zip(MODULE_LABELS, _MODULE_CLASSES, strict=True)
)


class NetUIApp(App[None]):
    TITLE = "NetUI"
    CSS_PATH = "netui.tcss"

    BINDINGS = _app_bindings()

    _netui_theme_index: ClassVar[int] = 0
    _startup_cache: ClassVar[dict[str, Any]] = {}

    active_module = reactive("Latency", init=False)
    active_interface = reactive("", init=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._task_scheduler = TaskScheduler()
        self._panel_cache: dict[str, PanelBase] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-row"):
            yield Sidebar()
            yield ContentArea()
        yield StatusBar()

    def get_theme_variable_defaults(self) -> dict[str, str]:
        theme_name = config.THEME_ORDER[config.current_theme_index % len(config.THEME_ORDER)]
        t = config.THEMES[theme_name]
        return {
            "netui-accent": t["accent"],
            "netui-highlight-bg": t["highlight_bg"],
            "netui-border": t["border"],
            "netui-dim": t["dim"],
            "netui-header-bg": t["header_bg"],
            "netui-body-bg": t["body_bg"],
            "netui-value": t["value"],
            "netui-error": t["error"],
            "netui-warning": t["warning"],
            "netui-info": t["info"],
        }

    def on_mount(self) -> None:
        self.push_screen(SplashScreen(), self._after_splash)

    def _after_splash(self, cache: dict[str, Any] | None) -> None:
        NetUIApp._startup_cache = cache or {}
        self._init_active_interface()
        sidebar = self.query_one(Sidebar)
        sidebar.highlight_interface(self.active_interface)
        sidebar.query_one("#module-list", ListView).focus()
        self.swap_active_module(self.active_module)
        if config.limited_mode:
            show_toast(
                self,
                "Running without admin rights — using fallback ping",
                level="info",
                duration=4,
            )
        if getattr(latency_collector, "icmp_fallback_mode", False) and not config.limited_mode:
            show_toast(
                self,
                "Using subprocess ping (try: sudo setcap cap_net_raw+ep /usr/bin/python3)",
                level="info",
                duration=5,
            )

    def on_unmount(self) -> None:
        self._task_scheduler.cancel_all()
        panel = self._active_panel()
        if panel:
            panel.cancel_operation()

    def _init_active_interface(self) -> None:
        stats = psutil.net_if_stats()
        for name, st in stats.items():
            if st.isup:
                self.active_interface = name
                return
        addrs = psutil.net_if_addrs()
        if addrs:
            self.active_interface = next(iter(sorted(addrs.keys())), "")
        else:
            self.active_interface = ""

    def watch_active_module(self, old_module: str, module_name: str) -> None:
        if module_name not in MODULE_PANEL_MAP:
            return
        self.swap_active_module(module_name)

    @work(thread=False, exclusive=True)
    async def swap_active_module(self, module_name: str) -> None:
        cls = MODULE_PANEL_MAP[module_name]
        content = self.query_one(ContentArea)
        sidebar = self.query_one(Sidebar)
        iface = sidebar.query_one("#iface-list", ListView)
        mod = sidebar.query_one("#module-list", ListView)
        keep_iface_focus = iface.has_focus
        keep_mod_focus = mod.has_focus
        cached = self._panel_cache.get(module_name)
        if cached is None:
            cached = cls()
            self._panel_cache[module_name] = cached
            await content.mount(cached)

        for child in list(content.children):
            if isinstance(child, PanelBase):
                child.display = child is cached
            elif getattr(child, "id", "") == "content-placeholder":
                await child.remove()

        if not cached.display:
            cached.display = True

        if keep_iface_focus:
            iface.focus()
        elif keep_mod_focus:
            mod.focus()

    @on(ModuleSelected)
    def on_module_selected(self, event: ModuleSelected) -> None:
        if event.module_name in MODULE_PANEL_MAP:
            self.active_module = event.module_name

    @on(InterfaceSelected)
    def on_interface_selected(self, event: InterfaceSelected) -> None:
        self.active_interface = event.interface_name

    async def action_quit(self) -> None:
        self.exit()

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_refresh(self) -> None:
        panel = self._active_panel()
        if panel:
            panel.refresh_data()

    def action_cycle_sidebar(self) -> None:
        sidebar = self.query_one(Sidebar)
        iface = sidebar.query_one("#iface-list", ListView)
        mod = sidebar.query_one("#module-list", ListView)
        if not iface.has_focus and not mod.has_focus:
            iface.focus()
            return
        if iface.has_focus:
            mod.focus()
        else:
            iface.focus()

    def action_cycle_theme(self) -> None:
        config.current_theme_index = (config.current_theme_index + 1) % len(config.THEME_ORDER)
        theme_name = config.THEME_ORDER[config.current_theme_index]
        theme = config.THEMES[theme_name]
        self.theme_variables.update(
            {
                "netui-accent": theme["accent"],
                "netui-highlight-bg": theme["highlight_bg"],
                "netui-border": theme["border"],
                "netui-dim": theme["dim"],
                "netui-header-bg": theme["header_bg"],
                "netui-body-bg": theme["body_bg"],
                "netui-value": theme["value"],
                "netui-error": theme["error"],
                "netui-warning": theme["warning"],
                "netui-info": theme["info"],
            }
        )
        self.refresh_css(animate=False)
        self.query_one(StatusBar).redraw()
        pretty = {
            "matrix": "Matrix Green",
            "amber": "Amber",
            "mono": "Monochrome",
        }.get(theme_name, theme_name.title())
        show_toast(self, f"Theme: {pretty}", level="info", duration=2)

    def action_reset_panel(self) -> None:
        panel = self._active_panel()
        if panel:
            panel.reset()

    def action_filter(self) -> None:
        panel = self._active_panel()
        if panel:
            panel.open_filter()

    def action_speed_test(self) -> None:
        panel = self._active_panel()
        if isinstance(panel, SpeedPanel):
            panel.start_test()

    def action_traceroute(self) -> None:
        panel = self._active_panel()
        if isinstance(panel, TraceroutePanel):
            panel.start_trace()

    def action_cycle_interface(self) -> None:
        panel = self._active_panel()
        if isinstance(panel, BandwidthPanel):
            panel.cycle_interface()

    def action_cancel(self) -> None:
        if self.screen_stack and len(self.screen_stack) > 1:
            self.pop_screen()
            return
        panel = self._active_panel()
        if panel:
            panel.cancel_operation()

    def _active_panel(self) -> PanelBase | None:
        content = self.query_one(ContentArea)
        for child in content.children:
            if isinstance(child, PanelBase):
                return child
        return None
