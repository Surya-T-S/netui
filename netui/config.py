from pathlib import Path

APP_NAME = "NetUI"

DEFAULT_PING_HOSTS = ["8.8.8.8", "1.1.1.1", "8.8.4.4"]

DEFAULT_DNS_TEST_HOSTS = ["google.com", "cloudflare.com", "github.com", "amazon.com"]

PING_INTERVAL_SECS = 5
BANDWIDTH_POLL_SECS = 1
PORT_REFRESH_SECS = 10
WIFI_REFRESH_SECS = 5

SPEED_TEST_URL_DOWN = "https://speed.cloudflare.com/__down?bytes=10000000"
SPEED_TEST_URL_UP = "https://speed.cloudflare.com/__up"

# Sidebar / routing labels (must match MODULE_PANEL_MAP keys in app).
MODULE_LABELS: list[str] = [
    "Latency",
    "Speed Test",
    "DNS",
    "Traceroute",
    "Interfaces",
    "Bandwidth",
    "Open Ports",
    "Wi-Fi",
    "Routes",
]

KEYBINDINGS: dict[str, str] = {
    "q": "quit",
    "ctrl+c": "quit",
    "r": "refresh",
    "question_mark": "help",
    "slash": "filter",
    "s": "speed_test",
    "t": "traceroute",
    "i": "cycle_interface",
    "escape": "cancel",
    "tab": "cycle_sidebar",
    "c": "cycle_theme",
    "ctrl+l": "reset_panel",
}

THEMES: dict[str, dict[str, str]] = {
    "matrix": {
        "accent": "#33ff66",
        "highlight_bg": "#0f2d17",
        "border": "#1f3f2a",
        "dim": "#6ea37c",
        "header_bg": "#050905",
        "body_bg": "#020402",
        "value": "#b7f7c5",
        "error": "#f85149",
        "warning": "#ffcc33",
        "info": "#6ce6ff",
    },
    "amber": {
        "accent": "#ffbf3f",
        "highlight_bg": "#2e2000",
        "border": "#584010",
        "dim": "#b38f52",
        "header_bg": "#0b0700",
        "body_bg": "#040300",
        "value": "#ffe3b3",
        "error": "#ff6b57",
        "warning": "#ffd166",
        "info": "#ffe08a",
    },
    "mono": {
        "accent": "#d8d8d8",
        "highlight_bg": "#1a1a1a",
        "border": "#2a2a2a",
        "dim": "#8f8f8f",
        "header_bg": "#080808",
        "body_bg": "#030303",
        "value": "#f0f0f0",
        "error": "#f85149",
        "warning": "#d4af37",
        "info": "#b8b8b8",
    },
}

THEME_ORDER = ["matrix", "amber", "mono"]
current_theme_index = 0

limited_mode = False

LOG_DIR = Path.home() / ".netui"
LOG_PATH = LOG_DIR / "netui.log"

PUBLIC_IP_URL = "https://api.ipify.org"
