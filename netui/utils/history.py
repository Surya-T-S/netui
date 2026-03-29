from collections import deque


class RollingHistory:
    def __init__(self, maxlen: int = 120) -> None:
        self._data: deque[float] = deque(maxlen=maxlen)

    def push(self, value: float) -> None:
        self._data.append(value)

    def get_all(self) -> list[float]:
        return list(self._data)

    def get_last_n(self, n: int) -> list[float]:
        return list(self._data)[-n:]

    def average(self) -> float:
        if not self._data:
            return 0.0
        return sum(self._data) / len(self._data)

    def min(self) -> float:
        if not self._data:
            return 0.0
        return min(self._data)

    def max(self) -> float:
        if not self._data:
            return 0.0
        return max(self._data)
