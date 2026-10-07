# Live metrics dashboard (outline)

Status: **outline only, nothing implemented yet.**

Flask produces simulated metrics; Dash polls it and redraws charts automatically.
Smallest example of Flask and Dash cooperating over a real HTTP boundary.

## Goal
Show a Dash page that refreshes every few seconds from a Flask JSON endpoint.

## Layout
```
examples/live_metrics/
  app.py          # create_app(): Flask routes + Dash mounted at /dash/
  metrics.py      # generator for simulated data (pure functions, seedable)
  test_app.py
```

## Flask side
- `GET /api/metrics?window=60` returns the last N points as
  `[{"ts": ISO8601, "cpu": float, "requests": int, "latency_ms": float}]`
- `GET /api/health` returns `{"status": "ok"}`
- `metrics.py` keeps a bounded in-memory deque and appends a new random-walk
  point per call, seeded for deterministic tests

## Dash side
- `dcc.Interval(interval=2000)` triggers a callback
- Callback calls the metrics function directly (same process) and returns:
  - a line chart (cpu, latency) via `plotly.express`
  - a KPI row (latest requests/s, p95 latency)
- Dropdown for window size (30s / 60s / 5m)

## Tests
- `/api/metrics` returns the requested window length and expected keys
- seeded generator is deterministic
- Dash layout contains the Interval and Graph components

## Build steps
1. `metrics.py` generator plus unit tests
2. Flask API routes
3. Dash layout and interval callback
4. Window-size dropdown, KPI row
5. README run instructions

## Open questions
- Call the generator directly from Dash, or over HTTP to `/api/metrics`? (direct is simpler; HTTP shows a realistic boundary)
- Keep state per process only, or persist to SQLite?
