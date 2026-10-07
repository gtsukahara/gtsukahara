"""Simulated metrics stream: a bounded, seedable, mean-reverting random walk."""
import math
import random
import threading
from collections import deque
from datetime import datetime, timedelta, timezone

STEP = timedelta(seconds=1)  # one point per second
CPU_MEAN = 45.0
CPU_PULL = 0.1  # fraction of the distance back to the mean, per step


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MetricsStream:
    """Keeps the last ``maxlen`` points, one per second.

    ``advance()`` catches the stream up to the current time, so the series has
    no gaps however rarely it is polled. ``prefill`` points end at "now".
    """

    def __init__(self, seed=None, maxlen=600, prefill=0, clock=_utcnow):
        self._rng = random.Random(seed)
        self._points = deque(maxlen=maxlen)
        self._maxlen = maxlen
        self._lock = threading.Lock()
        self._clock = clock
        self._cpu = 40.0
        now = clock()
        for i in range(prefill):
            self._generate(now - STEP * (prefill - 1 - i))
        self._last_ts = now

    def _generate(self, ts: datetime) -> dict:
        noise = self._rng.gauss(0, 4)
        self._cpu = min(100.0, max(0.0, self._cpu + CPU_PULL * (CPU_MEAN - self._cpu) + noise))
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

    def advance(self) -> list:
        """Add one point per whole second elapsed since the last point; return them."""
        with self._lock:
            elapsed = int((self._clock() - self._last_ts) / STEP)
            new = []
            # a long gap only needs the most recent ``maxlen`` points
            first = max(1, elapsed - self._maxlen + 1)
            for k in range(first, elapsed + 1):
                new.append(self._generate(self._last_ts + STEP * k))
            self._last_ts += STEP * elapsed
            return new

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
