"""Minimal Flask + Dash demo.

Flask serves a landing page and a JSON API; Dash is mounted on the same
Flask server under /dash/ and renders an interactive chart from the same data.

Run:  python app.py   ->  http://127.0.0.1:5000/
"""
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dcc, html
from flask import Flask, jsonify

SALES = pd.DataFrame(
    {
        "month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"] * 2,
        "region": ["North"] * 6 + ["South"] * 6,
        "revenue": [120, 135, 160, 150, 170, 190, 90, 100, 95, 120, 130, 145],
    }
)


def create_app() -> Flask:
    server = Flask(__name__)

    @server.get("/")
    def index():
        return (
            "<h1>Flask + Dash demo</h1>"
            '<ul><li><a href="/api/sales">/api/sales</a> (Flask JSON API)</li>'
            '<li><a href="/dash/">/dash/</a> (Dash dashboard)</li></ul>'
        )

    @server.get("/api/sales")
    def sales():
        return jsonify(SALES.to_dict(orient="records"))

    dash_app = Dash(__name__, server=server, routes_pathname_prefix="/dash/")
    dash_app.layout = html.Div(
        [
            html.H2("Revenue by month"),
            dcc.Dropdown(
                id="region",
                options=["All", *sorted(SALES["region"].unique())],
                value="All",
                clearable=False,
            ),
            dcc.Graph(id="chart"),
        ]
    )

    @dash_app.callback(Output("chart", "figure"), Input("region", "value"))
    def update_chart(region):
        df = SALES if region == "All" else SALES[SALES["region"] == region]
        return px.bar(df, x="month", y="revenue", color="region", barmode="group")

    return server


if __name__ == "__main__":
    create_app().run(debug=True)
