"""Live metrics dashboard.

Flask serves a JSON API over a simulated metrics stream; Dash is mounted on
the same server at /dash/ and refreshes itself on an interval. The look comes
from a Bootswatch theme (dash-bootstrap-components) with a matching Plotly
figure template (dash-bootstrap-templates).

Run from the repo root:  python -m examples.live_metrics.app
Pick a theme:            EXAMPLES_THEME=FLATLY python -m examples.live_metrics.app
"""
import os

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html
from flask import Flask, jsonify, request
from plotly.subplots import make_subplots

from ..theme import DEFAULT_THEME, graph_card, kpi_card, resolve_theme, style_figure, theme_from_env
from .metrics import MetricsStream, kpis

MAXLEN = 600  # one point per second, so 10 minutes
WINDOWS = [(30, "Last 30 seconds"), (60, "Last 60 seconds"), (300, "Last 5 minutes")]


def kpi_cards(stats: dict) -> list:
    """Two cards: latest requests/s and p95 latency."""
    return [
        kpi_card("Requests/s (latest)", f"{stats['latest_requests']}"),
        kpi_card("p95 latency", f"{stats['p95_latency_ms']:.0f} ms"),
    ]


def make_figure(points: list, template: str = "plotly_white") -> go.Figure:
    """CPU (%) on the left axis, latency (ms) on the right."""
    ts = [p["ts"] for p in points]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=ts, y=[p["cpu"] for p in points], name="CPU (%)"), secondary_y=False)
    fig.add_trace(
        go.Scatter(x=ts, y=[p["latency_ms"] for p in points], name="Latency (ms)"), secondary_y=True
    )
    fig.update_xaxes(title_text="Time (UTC)", tickformat="%H:%M:%S", nticks=5)
    fig.update_yaxes(title_text="CPU (%)", range=[0, 100], secondary_y=False)
    fig.update_yaxes(
        title_text="Latency (ms)", secondary_y=True, showgrid=False,
        tickmode="auto", nticks=6, tickformat=".0f",
    )
    return style_figure(fig, template)


def create_app(seed=None, interval_ms=2000, prefill=60, clock=None, theme=DEFAULT_THEME) -> Flask:
    stylesheet, template = resolve_theme(theme)

    server = Flask(__name__)
    kwargs = {} if clock is None else {"clock": clock}
    stream = MetricsStream(seed=seed, maxlen=MAXLEN, prefill=prefill, **kwargs)
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

    dash_app = Dash(
        __name__,
        server=server,
        routes_pathname_prefix="/dash/",
        external_stylesheets=[stylesheet],
        title="Live metrics",
    )
    dash_app.layout = dbc.Container(
        [
            html.H2("Live metrics", className="mt-3 mb-3"),
            dbc.Row(
                dbc.Col(
                    dbc.Select(
                        id="window",
                        options=[{"label": label, "value": n} for n, label in WINDOWS],
                        value=60,
                    ),
                    xs=12,
                    md=3,
                ),
                className="mb-3",
            ),
            dbc.Row(id="kpis", className="g-3 mb-3"),
            graph_card(dcc.Graph(id="chart", config={"displayModeBar": False})),
            dcc.Interval(id="tick", interval=interval_ms),
        ],
        fluid="lg",
        className="pb-4",
    )

    @dash_app.callback(
        Output("chart", "figure"),
        Output("kpis", "children"),
        Input("tick", "n_intervals"),
        Input("window", "value"),
    )
    def refresh(_n, window):
        stream.advance()
        points = stream.window(int(window))
        return make_figure(points, template), kpi_cards(kpis(points))

    return server


if __name__ == "__main__":
    create_app(theme=theme_from_env()).run(
        debug=True, port=int(os.environ.get("PORT", 5001))
    )
