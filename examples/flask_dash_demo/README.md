# Flask + Dash demo

A tiny app showing Flask and Dash sharing one server.

- `/` - Flask route (HTML)
- `/api/sales` - Flask JSON API backed by a pandas DataFrame
- `/dash/` - Dash dashboard (region dropdown + Plotly bar chart) mounted on the same Flask app

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # from the repo root
python examples/flask_dash_demo/app.py
```

Then open http://127.0.0.1:5000/ .

## Test

```bash
pytest examples/flask_dash_demo
```
