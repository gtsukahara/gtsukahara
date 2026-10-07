"""Dash page: completion trend, open tasks by priority, KPIs, add-task form."""
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, State, dcc, html

from ..theme import COLORWAY, graph_card, kpi_card, style_figure
from . import service, stats


def kpi_cards(k: dict) -> list:
    return [
        kpi_card("Open", str(k["open"])),
        kpi_card("Completed this week", str(k["completed_this_week"])),
        kpi_card("Avg time to complete", f"{k['avg_hours_to_complete']} h"),
    ]


def _priority(value) -> int:
    """dbc.Select may send the value as a string; fall back to the default for anything invalid."""
    return int(value) if str(value) in ("1", "2", "3") else 2


def per_day_figure(per_day):
    # px fixes marker colours when it builds the figure, so pass the palette here
    fig = px.bar(
        per_day, x="day", y="completed", title="Completed per day (last 14 days)",
        color_discrete_sequence=COLORWAY,
    )
    if per_day["completed"].max() <= 6:
        fig.update_yaxes(dtick=1)  # whole tasks only
    return fig


def priority_figure(open_by_priority):
    counts = {p: n for p, n in open_by_priority.items() if n}  # skip empty slices (their labels overlap)
    fig = px.pie(
        names=[f"Priority {p}" for p in counts],
        values=list(counts.values()),
        title="Open tasks by priority",
        color_discrete_sequence=COLORWAY,
    )
    if not counts:
        fig.add_annotation(text="No open tasks", showarrow=False, font={"size": 16})
    return fig


def register_dashboard(server, stylesheet, template):
    factory = server.extensions["task_sessions"]
    dash_app = Dash(
        __name__,
        server=server,
        routes_pathname_prefix="/dash/",
        external_stylesheets=[stylesheet],
        title="Task tracker",
    )
    dash_app.layout = dbc.Container(
        [
            html.H2("Task tracker", className="mt-3 mb-3"),
            dbc.Card(
                dbc.CardBody(
                    dbc.Row(
                        [
                            dbc.Col(dbc.Input(id="title", type="text", placeholder="New task", maxLength=200), md=6),
                            dbc.Col(
                                dbc.Select(
                                    id="priority",
                                    options=[{"label": f"Priority {p}", "value": p} for p in (1, 2, 3)],
                                    value=2,
                                ),
                                md=3,
                            ),
                            dbc.Col(dbc.Button("Add task", id="add", n_clicks=0, color="primary", className="w-100"), md=3),
                        ],
                        className="g-2",
                    )
                ),
                className="mb-3",
            ),
            dbc.Row(id="kpis", className="g-3 mb-3"),
            dbc.Row(
                [
                    dbc.Col(graph_card(dcc.Graph(id="per-day", config={"displayModeBar": False})), md=8),
                    dbc.Col(graph_card(dcc.Graph(id="by-priority", config={"displayModeBar": False})), md=4),
                ],
                className="g-3",
            ),
        ],
        fluid="lg",
        className="pb-4",
    )

    @dash_app.callback(
        Output("per-day", "figure"),
        Output("by-priority", "figure"),
        Output("kpis", "children"),
        Output("title", "value"),
        Input("add", "n_clicks"),
        State("title", "value"),
        State("priority", "value"),
    )
    def refresh(n_clicks, title, priority):
        with factory() as s:
            if n_clicks and title and title.strip():
                service.create_task(s, title.strip()[:service.MAX_TITLE], _priority(priority))
            per_day = pd.DataFrame(stats.completed_per_day(s), columns=["day", "completed"])
            prio = stats.open_by_priority(s)
            k = stats.kpis(s)
        return (
            style_figure(per_day_figure(per_day), template),
            style_figure(priority_figure(prio), template),
            kpi_cards(k),
            "",
        )

    return dash_app
