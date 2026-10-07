"""Live metrics dashboard.

Flask serves a JSON API over a simulated metrics stream; Dash is mounted on
the same server at /dash/ and refreshes itself on an interval.

Run from the repo root:  python -m examples.live_metrics.app
"""
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, ctx, dcc, html
from flask import Flask, jsonify, request

from .metrics import MetricsStream, kpis

MAXLEN = 600
WINDOWS = [30, 60, 300]


def create_app(seed=None, interval_ms=2000, prefill=60) -> Flask:
    server = Flask(__name__)
    stream = MetricsStream(seed=seed, maxlen=MAXLEN, prefill=prefill)
    server.extensions["metrics_stream"] = stream

    @server.get("/api/health")
    def health():
        return jsonify(status="ok")

    @server.get("/api/metrics")
    def metrics():
        window = request.args.get("window", default=60, type=int)
        if not 1 <= window <= MAXLEN:
            return jsonify(error=f"window must be between 1 and {MAXLEN}"), 400
        stream.advance()
        return jsonify(stream.window(window))

    dash_app = Dash(__name__, server=server, routes_pathname_prefix="/dash/")
    dash_app.layout = html.Div(
        [
            html.H2("Live metrics"),
            dcc.Dropdown(
                id="window",
                options=[{"label": f"Last {n} points", "value": n} for n in WINDOWS],
                value=60,
                clearable=False,
            ),
            html.Div(id="kpis"),
            dcc.Graph(id="chart"),
            dcc.Interval(id="tick", interval=interval_ms),
        ]
    )

    @dash_app.callback(
        Output("chart", "figure"),
        Output("kpis", "children"),
        Input("tick", "n_intervals"),
        Input("window", "value"),
    )
    def refresh(_n, window):
        if ctx.triggered_id == "tick":
            stream.advance()
        points = stream.window(window)
        df = pd.DataFrame(points)
        df["ts"] = pd.to_datetime(df["ts"])
        fig = px.line(df, x="ts", y=["cpu", "latency_ms"])
        stats = kpis(points)
        summary = (
            f"Requests/s: {stats['latest_requests']}  |  "
            f"p95 latency: {stats['p95_latency_ms']:.0f} ms"
        )
        return fig, summary

    return server


if __name__ == "__main__":
    create_app().run(debug=True, port=5001)
