"""Dash page: completion trend, open tasks by priority, KPIs, add-task form."""
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, State, dcc, html

from . import stats
from .models import Task


def register_dashboard(server):
    factory = server.extensions["task_sessions"]
    dash_app = Dash(__name__, server=server, routes_pathname_prefix="/dash/")
    dash_app.layout = html.Div(
        [
            html.H2("Task tracker"),
            html.Div(
                [
                    dcc.Input(id="title", type="text", placeholder="New task", debounce=False),
                    dcc.Dropdown(
                        id="priority",
                        options=[{"label": f"Priority {p}", "value": p} for p in (1, 2, 3)],
                        value=2,
                        clearable=False,
                        style={"width": "140px", "display": "inline-block"},
                    ),
                    html.Button("Add", id="add", n_clicks=0),
                ]
            ),
            html.Div(id="kpis"),
            dcc.Graph(id="per-day"),
            dcc.Graph(id="by-priority"),
        ]
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
                s.add(Task(title=title.strip()[:200], priority=priority or 2))
                s.commit()
            per_day = pd.DataFrame(stats.completed_per_day(s), columns=["day", "completed"])
            prio = stats.open_by_priority(s)
            k = stats.kpis(s)
        bar = px.bar(per_day, x="day", y="completed", title="Completed per day (last 14 days)")
        pie = px.pie(
            names=[f"Priority {p}" for p in prio],
            values=list(prio.values()),
            title="Open tasks by priority",
        )
        summary = (
            f"Open: {k['open']}  |  Completed this week: {k['completed_this_week']}  |  "
            f"Avg time to complete: {k['avg_hours_to_complete']} h"
        )
        return bar, pie, summary, ""

    return dash_app
