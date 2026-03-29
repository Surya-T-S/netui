from __future__ import annotations


def ratio_bar(value: float, maximum: float, width: int = 12) -> str:
    if width <= 0:
        return ""
    if maximum <= 0:
        filled = 0
    else:
        frac = max(0.0, min(1.0, value / maximum))
        filled = int(round(frac * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)
