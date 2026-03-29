from __future__ import annotations

import psutil
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView, Rule

from netui.config import MODULE_LABELS
from netui.messages import InterfaceSelected, ModuleSelected


def _list_item_label(item: ListItem) -> str:
    lab = item.query_one(Label)
    return str(lab.content)


class Sidebar(Widget):
    """Interface + module navigation lists."""

    def compose(self) -> ComposeResult:
        iface_names = sorted(psutil.net_if_addrs().keys())
        with Vertical():
            yield Label("INTERFACES")
            yield ListView(
                *[ListItem(Label(n)) for n in iface_names],
                id="iface-list",
                initial_index=0 if iface_names else None,
            )
            yield Rule()
            yield Label("MODULES")
            yield ListView(
                *[ListItem(Label(name)) for name in MODULE_LABELS],
                id="module-list",
                initial_index=0,
            )

    @on(ListView.Selected)
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self._post_nav_event(event.list_view, event.item)

    @on(ListView.Highlighted)
    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is None:
            return
        self._post_nav_event(event.list_view, event.item)

    def _post_nav_event(self, list_view: ListView, item: ListItem) -> None:
        label = _list_item_label(item)
        lid = list_view.id or ""
        if lid == "module-list":
            self.post_message(ModuleSelected(label))
        elif lid == "iface-list":
            self.post_message(InterfaceSelected(label))

    def highlight_interface(self, name: str) -> None:
        if not name:
            return
        lv = self.query_one("#iface-list", ListView)
        for i, child in enumerate(lv.children):
            if isinstance(child, ListItem) and _list_item_label(child) == name:
                lv.index = i
                return
