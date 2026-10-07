# Flask + Dash demo (start here)

The simplest of the three examples: one 60-line file showing Flask and Dash sharing one server.
Read this one first, then move on to `live_metrics` (auto-refresh) and `task_tracker` (database and forms).

- `/` - Flask route returning an HTML landing page (styled with the same Bootstrap theme as the dashboard)
- `/api/sales` - Flask JSON API backed by a pandas DataFrame
- `/dash/` - Dash dashboard (region dropdown + grouped Plotly bar chart) mounted on the same Flask app

## Layout
```
app.py                  # create_app(): Flask routes + Dash mounted at /dash/
test_flask_dash_demo.py
```

## Run
From the repo root, in a venv with `requirements.txt` installed:

```bash
python -m examples.flask_dash_demo.app
```

Then open http://127.0.0.1:5003/ . Port 5003 is used because macOS's AirPlay Receiver occupies port 5000.
The look comes from the shared theme in `examples/theme.py`; try `EXAMPLES_THEME=FLATLY` for a light version.

## Test
```bash
pytest examples/flask_dash_demo
```
