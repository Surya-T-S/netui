def bytes_to_human(b: float) -> str:
    if b < 0:
        b = 0.0
    units = ["B", "KB", "MB", "GB", "TB"]
    v = float(b)
    i = 0
    while v >= 1024 and i < len(units) - 1:
        v /= 1024
        i += 1
    if i == 0:
        return f"{int(v)} {units[i]}"
    return f"{v:.1f} {units[i]}"


def ms_to_str(ms: float) -> str:
    return f"{ms:.1f} ms"


def ms_to_colored_str(ms: float) -> str:
    if ms < 50:
        color = "green"
    elif ms <= 150:
        color = "yellow"
    else:
        color = "red"
    return f"[{color}]{ms_to_str(ms)}[/{color}]"


def pct_to_colored_str(pct: float) -> str:
    if pct > 5:
        color = "red"
    elif pct >= 1:
        color = "yellow"
    else:
        color = "green"
    return f"[{color}]{pct:.1f}%[/{color}]"


def bits_per_sec_to_human(bps: float) -> str:
    if bps < 0:
        bps = 0.0
    units = ["bps", "Kbps", "Mbps", "Gbps"]
    v = float(bps)
    i = 0
    while v >= 1000 and i < len(units) - 1:
        v /= 1000
        i += 1
    if i == 0:
        return f"{v:.0f} {units[i]}"
    return f"{v:.2f} {units[i]}"
