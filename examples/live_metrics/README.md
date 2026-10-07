# Live metrics dashboard

Flask serves a JSON API over a simulated metrics stream; Dash is mounted on the
same server at `/dash/` and refreshes itself every 2 seconds.

- `GET /api/metrics?window=60` returns the last N points
  (`ts`, `cpu`, `requests`, `latency_ms`) and adds one new point per call
- `GET /api/health` returns `{"status": "ok"}`
- `/dash/` shows a line chart (cpu, latency), a KPI row (requests/s, p95 latency)
  and a window-size dropdown

## Layout
```
metrics.py          # seedable random-walk generator, p95 and KPI helpers
app.py              # create_app(): Flask routes + Dash mounted at /dash/
test_live_metrics.py
```

## Run
From the repo root, in a venv with `requirements.txt` installed:

```bash
python -m examples.live_metrics.app
```

Then open http://127.0.0.1:5001/dash/ .

## Test
```bash
pytest examples/live_metrics
```

## Design notes
- Dash calls the stream directly (same process) rather than over HTTP. That
  keeps the demo small; the HTTP API exists for other clients.
- State is in memory per process (bounded to 600 points). Persisting to SQLite
  would be a natural next step.
