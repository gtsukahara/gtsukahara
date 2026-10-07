"""Live metrics dashboard.

Flask serves a JSON API over a simulated metrics stream; Dash is mounted on
the same server at /dash/ and refreshes itself on an interval.

Run from the repo root:  python -m examples.live_metrics.app
"""
import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html
from flask import Flask, jsonify, request
from plotly.subplots import make_subplots

from .metrics import MetricsStream, kpis

MAXLEN = 600  # one point per second, so 10 minutes
WINDOWS = [(30, "Last 30 seconds"), (60, "Last 60 seconds"), (300, "Last 5 minutes")]

FONT = {"fontFamily": "system-ui, -apple-system, Segoe UI, Roboto, sans-serif"}
CARD = {
    "border": "1px solid #d9dee5",
    "borderRadius": "8px",
    "padding": "10px 16px",
    "minWidth": "150px",
}


def kpi_cards(stats: dict) -> list:
    """Two small cards: latest requests/s and p95 latency."""
    def card(label, value):
        return html.Div(
            [
                html.Div(label, style={"fontSize": "12px", "color": "#5b6573"}),
                html.Div(value, style={"fontSize": "24px", "fontWeight": "600"}),
            ],
            style=CARD,
        )

    return [
        card("Requests/s (latest)", f"{stats['latest_requests']}"),
        card("p95 latency", f"{stats['p95_latency_ms']:.0f} ms"),
    ]


def make_figure(points: list) -> go.Figure:
    """CPU (%) on the left axis, latency (ms) on the right."""
    ts = [p["ts"] for p in points]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=ts, y=[p["cpu"] for p in points], name="CPU (%)"), secondary_y=False)
    fig.add_trace(
        go.Scatter(x=ts, y=[p["latency_ms"] for p in points], name="Latency (ms)"), secondary_y=True
    )
    fig.update_xaxes(title_text="Time (UTC)")
    fig.update_yaxes(title_text="CPU (%)", range=[0, 100], secondary_y=False)
    fig.update_yaxes(title_text="Latency (ms)", secondary_y=True, showgrid=False)
    fig.update_layout(
        template="plotly_white",
        legend={"orientation": "h", "y": 1.12, "x": 0},
        margin={"l": 60, "r": 60, "t": 40, "b": 50},
    )
    return fig


def create_app(seed=None, interval_ms=2000, prefill=60, clock=None) -> Flask:
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

    dash_app = Dash(__name__, server=server, routes_pathname_prefix="/dash/")
    dash_app.layout = html.Div(
        [
            html.H2("Live metrics", style={"marginTop": 0}),
            dcc.Dropdown(
                id="window",
                options=[{"label": label, "value": n} for n, label in WINDOWS],
                value=60,
                clearable=False,
                style={"width": "220px", "marginBottom": "16px"},
            ),
            html.Div(id="kpis", style={"display": "flex", "gap": "12px", "marginBottom": "8px"}),
            dcc.Graph(id="chart"),
            dcc.Interval(id="tick", interval=interval_ms),
        ],
        style={"maxWidth": "1100px", "margin": "0 auto", "padding": "24px", **FONT},
    )

    @dash_app.callback(
        Output("chart", "figure"),
        Output("kpis", "children"),
        Input("tick", "n_intervals"),
        Input("window", "value"),
    )
    def refresh(_n, window):
        stream.advance()
        points = stream.window(window)
        return make_figure(points), kpi_cards(kpis(points))

    return server


if __name__ == "__main__":
    create_app().run(debug=True, port=5001)
