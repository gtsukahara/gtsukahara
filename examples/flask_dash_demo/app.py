"""Minimal Flask + Dash demo.

Flask serves a landing page and a JSON API; Dash is mounted on the same
Flask server under /dash/ and renders an interactive chart from the same data.
Both pages use the shared theme (see examples/theme.py).

Run from the repo root:  python -m examples.flask_dash_demo.app  ->  http://127.0.0.1:5003/
"""
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dcc, html
from flask import Flask, jsonify

from ..theme import COLORWAY, DEFAULT_THEME, resolve_theme, style_figure, theme_from_env

SALES = pd.DataFrame(
    {
        "month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"] * 2,
        "region": ["North"] * 6 + ["South"] * 6,
        "revenue": [120, 135, 160, 150, 170, 190, 90, 100, 95, 120, 130, 145],
    }
)

LANDING = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flask + Dash demo</title><link rel="stylesheet" href="{stylesheet}"></head>
<body><div class="container py-4" style="max-width: 720px">
<h1 class="mb-3">Flask + Dash demo</h1>
<p class="text-muted">One Flask server: a plain route, a JSON API, and a Dash dashboard.</p>
<div class="list-group">
<a class="list-group-item list-group-item-action" href="/api/sales"><b>/api/sales</b> &ndash; Flask JSON API</a>
<a class="list-group-item list-group-item-action" href="/dash/"><b>/dash/</b> &ndash; Dash dashboard</a>
</div></div></body></html>"""


def create_app(theme=DEFAULT_THEME) -> Flask:
    stylesheet, template = resolve_theme(theme)
    server = Flask(__name__)

    @server.get("/")
    def index():
        return LANDING.format(stylesheet=stylesheet)

    @server.get("/api/sales")
    def sales():
        return jsonify(SALES.to_dict(orient="records"))

    dash_app = Dash(
        __name__,
        server=server,
        routes_pathname_prefix="/dash/",
        external_stylesheets=[stylesheet],
        title="Flask + Dash demo",
    )
    dash_app.layout = dbc.Container(
        [
            html.H2("Revenue by month", className="mt-3 mb-3"),
            dbc.Row(
                dbc.Col(
                    dbc.Select(
                        id="region",
                        options=[{"label": r, "value": r} for r in ["All", *sorted(SALES["region"].unique())]],
                        value="All",
                    ),
                    xs=12,
                    md=3,
                ),
                className="mb-3",
            ),
            dbc.Card(dbc.CardBody(dcc.Graph(id="chart", config={"displayModeBar": False}))),
        ],
        fluid="lg",
        className="pb-4",
    )

    @dash_app.callback(Output("chart", "figure"), Input("region", "value"))
    def update_chart(region):
        df = SALES if region == "All" else SALES[SALES["region"] == region]
        fig = px.bar(
            df, x="month", y="revenue", color="region", barmode="group",
            color_discrete_sequence=COLORWAY,
        )
        return style_figure(fig, template)

    return server


if __name__ == "__main__":
    create_app(theme=theme_from_env()).run(debug=True, port=5003)
