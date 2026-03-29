_BLOCKS = "▁▂▃▄▅▆▇█"


def smooth_values(values: list[float], alpha: float = 0.35) -> list[float]:
    if not values:
        return []
    a = max(0.05, min(0.95, alpha))
    out: list[float] = [values[0]]
    for v in values[1:]:
        out.append((a * v) + ((1.0 - a) * out[-1]))
    return out


def render_sparkline(values: list[float], width: int = 40) -> str:
    if width <= 0:
        return ""
    if not values:
        return _BLOCKS[0] * width
    mn = min(values)
    mx = max(values)
    if mn == mx:
        idx = len(_BLOCKS) // 2
        ch = _BLOCKS[idx]
        return ch * width
    span = len(_BLOCKS) - 1
    # sample or pad values to `width` columns
    n = len(values)
    if n >= width:
        step = n / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = list(values) + [values[-1]] * (width - n)
    out: list[str] = []
    for v in sampled[:width]:
        t = (v - mn) / (mx - mn)
        i = int(round(t * span))
        i = max(0, min(span, i))
        out.append(_BLOCKS[i])
    return "".join(out)
