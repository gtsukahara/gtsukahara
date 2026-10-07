"""Simulated metrics stream: a bounded, seedable random walk."""
import math
import random
import threading
from collections import deque
from datetime import datetime, timedelta, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MetricsStream:
    """Keeps the last ``maxlen`` points; each ``advance()`` adds one more."""

    def __init__(self, seed=None, maxlen=600, prefill=0, clock=_utcnow):
        self._rng = random.Random(seed)
        self._points = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._clock = clock
        self._cpu = 40.0
        now = clock()
        for i in range(prefill):
            self._generate(now - timedelta(seconds=prefill - i))

    def _generate(self, ts: datetime) -> dict:
        self._cpu = min(100.0, max(0.0, self._cpu + self._rng.gauss(0, 5)))
        latency = max(5.0, 80 + self._cpu * 1.5 + self._rng.gauss(0, 10))
        requests = max(0, int(200 + (self._cpu - 40) * 4 + self._rng.gauss(0, 20)))
        point = {
            "ts": ts.isoformat(),
            "cpu": round(self._cpu, 2),
            "requests": requests,
            "latency_ms": round(latency, 2),
        }
        self._points.append(point)
        return point

    def advance(self) -> dict:
        with self._lock:
            return self._generate(self._clock())

    def window(self, n: int) -> list:
        with self._lock:
            return list(self._points)[-n:]


def p95(values) -> float:
    """95th percentile, nearest-rank method."""
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def kpis(points: list) -> dict:
    if not points:
        return {"latest_requests": 0, "p95_latency_ms": 0.0}
    return {
        "latest_requests": points[-1]["requests"],
        "p95_latency_ms": p95(p["latency_ms"] for p in points),
    }
