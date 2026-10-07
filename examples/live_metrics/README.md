# Live metrics dashboard

Flask serves a JSON API over a simulated metrics stream; Dash is mounted on the
same server at `/dash/` and refreshes itself every 2 seconds.

- `GET /api/metrics?window=60` returns the last N points (one per second)
  (`ts`, `cpu`, `requests`, `latency_ms`) after catching the stream up to the current time
- `GET /api/health` returns `{"status": "ok"}`
- `/dash/` shows CPU (%) and latency (ms) on separate axes, two KPI cards (requests/s, p95 latency)
  and a window dropdown (30 seconds, 60 seconds, 5 minutes); the layout is responsive down to phone width

## Layout
```
metrics.py          # seedable mean-reverting generator, p95 and KPI helpers
app.py              # create_app(): Flask routes + Dash mounted at /dash/
test_live_metrics.py
```

## Run
From the repo root, in a venv with `requirements.txt` installed:

```bash
python -m examples.live_metrics.app
```

Then open http://127.0.0.1:5001/dash/ .

### Themes
The look comes from a Bootswatch theme via `dash-bootstrap-components`, with a matching Plotly figure template
from `dash-bootstrap-templates`. The default is `CYBORG` (dark, with the best line contrast of the ones tried).
Pick another with an environment variable (any of the 25 names in `THEMES` in `app.py`):

```bash
LIVE_METRICS_THEME=FLATLY python -m examples.live_metrics.app     # light
PORT=5010 python -m examples.live_metrics.app                       # change the port
```

`DARKLY` is also dark but its default CPU line is low contrast on the dark background. In code:
`create_app(theme="FLATLY")`.

## Test
```bash
pytest examples/live_metrics
```

## Design notes
- Dash calls the stream directly (same process) rather than over HTTP. That
  keeps the demo small; the HTTP API exists for other clients.
- The stream has one point per second and catches up to the current time whenever it is read, so there are no
  gaps even if nobody was polling (a gap longer than 10 minutes only keeps the newest 600 points). This avoids a
  background thread and lets tests control time with an injected clock.
- CPU is a mean-reverting random walk (pulled toward 45%), so it stays in a realistic band instead of pinning at 100%.
- State is in memory per process (bounded to 600 points). Persisting to SQLite
  would be a natural next step.
