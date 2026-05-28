"""Простейший in-memory sliding-window rate-limiter.

Для MVP/single-worker деплоя — норма. Для multi-worker prod (uvicorn --workers >1
или несколько подов) нужен общий стор (Redis). Пока используется для защиты
/auth/login от brute-force перебора паролей.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock


class SlidingWindowRateLimiter:
    """Считает N событий за последние window_seconds для каждого ключа.

    Потокобезопасен (Lock), но не межпроцессно. Не персистентен — после
    рестарта счётчик сбрасывается, что приемлемо: атакующий и так теряет
    state соединения при рестарте.
    """

    def __init__(self, *, max_events: int, window_seconds: float) -> None:
        if max_events <= 0:
            raise ValueError("max_events must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._max_events = max_events
        self._window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check_and_record(self, key: str, *, now: float | None = None) -> bool:
        """True если событие можно принять; False если лимит превышен."""
        current = now if now is not None else time.monotonic()
        threshold = current - self._window_seconds
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] < threshold:
                bucket.popleft()
            if len(bucket) >= self._max_events:
                return False
            bucket.append(current)
            return True

    def retry_after(self, key: str, *, now: float | None = None) -> float:
        """Сколько секунд осталось до следующего разрешённого события."""
        current = now if now is not None else time.monotonic()
        with self._lock:
            bucket = self._buckets[key]
            if not bucket or len(bucket) < self._max_events:
                return 0.0
            oldest = bucket[0]
            return max(0.0, oldest + self._window_seconds - current)


# 10 неуспешных попыток за 5 минут на ключ — этого хватает для обычного
# пользователя, который ошибся пару раз, и режет brute-force.
login_rate_limiter = SlidingWindowRateLimiter(max_events=10, window_seconds=300)
