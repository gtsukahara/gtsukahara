"""Dash page: completion trend, open tasks by priority, KPIs, add-task form."""
from datetime import date

import dash_ag_grid as dag
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, State, ctx, dcc, html, no_update

from ..theme import COLORWAY, graph_card, kpi_card, style_figure
from . import service, stats
from .service import TaskNotFound, ValidationError


def kpi_cards(k: dict) -> list:
    return [
        kpi_card("Open", str(k["open"])),
        kpi_card("Completed this week", str(k["completed_this_week"])),
        kpi_card("Avg time to complete", f"{k['avg_hours_to_complete']} h"),
    ]


def table_rows(tasks) -> list:
    """Rows for the task table: open tasks first, then by priority, newest first."""
    ordered = sorted(tasks, key=lambda t: (t.status == "done", t.priority, -t.id))
    return [
        {
            "id": t.id,
            "key": str(t.id),  # AG Grid row ids must be strings, and dash-ag-grid only reads plain property paths
            "title": t.title,
            "priority": t.priority,
            "status": t.status,
            "created": t.created_at.strftime("%Y-%m-%d %H:%M"),
            "completed": t.completed_at.strftime("%Y-%m-%d %H:%M") if t.completed_at else "",
        }
        for t in ordered
    ]


COLUMN_DEFS = [
    {"field": "title", "headerName": "Title", "flex": 3, "minWidth": 180},
    {"field": "priority", "headerName": "Priority", "width": 110, "filter": "agNumberColumnFilter"},
    {"field": "status", "headerName": "Status", "width": 110},
    {"field": "created", "headerName": "Created", "width": 160},
    {"field": "completed", "headerName": "Completed", "width": 160},
]

# AG Grid theme built from the Bootstrap theme's CSS variables, so the table follows whichever theme is active.
GRID_THEME = (
    "themeQuartz.withParams({"
    "backgroundColor: 'transparent', foregroundColor: 'var(--bs-body-color)', "
    "headerBackgroundColor: 'transparent', headerTextColor: 'var(--bs-body-color)', "
    "borderColor: 'var(--bs-border-color)', rowHoverColor: 'rgba(128,128,128,0.15)', "
    "fontFamily: 'inherit', wrapperBorder: false})"
)


def task_grid():
    return dag.AgGrid(
        id="task-table",
        rowData=[],
        columnDefs=COLUMN_DEFS,
        defaultColDef={"sortable": True, "filter": True, "resizable": True},
        getRowId="params.data.key",
        getRowStyle={"styleConditions": [{"condition": "params.data.status === 'done'", "style": {"opacity": 0.55}}]},
        dashGridOptions={
            "pagination": True,
            "paginationPageSize": 10,
            "paginationPageSizeSelector": [10, 25, 50],
            "domLayout": "autoHeight",
            "animateRows": False,
            "theme": {"function": GRID_THEME},
        },
        style={"width": "100%"},
    )


def meta_text(task) -> str:
    text = f"Created {task.created_at.strftime('%Y-%m-%d %H:%M')} UTC"
    if task.completed_at:
        text += f"  ·  Completed {task.completed_at.strftime('%Y-%m-%d %H:%M')} UTC"
    return text


def filter_from_click(kind: str, click_data):
    """Turn a chart click into a table filter, or None if the click does not identify one.

    ``kind`` is "day" (the completed-per-day bars) or "priority" (the pie slices).
    """
    try:
        point = click_data["points"][0]
        if kind == "day":
            return {"kind": "day", "value": date.fromisoformat(str(point["x"])[:10]).isoformat()}
        label = str(point["label"])  # e.g. "Priority 2"
        return {"kind": "priority", "value": int(label.rsplit(" ", 1)[1])}
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def filter_kwargs(table_filter) -> dict:
    """Keyword arguments for ``service.list_tasks``; an invalid or empty filter means no filtering."""
    try:
        if table_filter["kind"] == "day":
            return {"completed_on": date.fromisoformat(table_filter["value"])}
        if table_filter["kind"] == "priority" and table_filter["value"] in (1, 2, 3):
            return {"status": "open", "priority": table_filter["value"]}
    except (KeyError, TypeError, ValueError):
        pass
    return {}


FILTER_HINT = "Click a bar or a pie slice to filter this table."


def describe_filter(table_filter, count: int):
    """(label text, style for the Clear button) for the filter bar above the table."""
    kwargs = filter_kwargs(table_filter)
    noun = "task" if count == 1 else "tasks"
    if "completed_on" in kwargs:
        return f"Completed on {kwargs['completed_on'].isoformat()}: {count} {noun}", {}
    if "priority" in kwargs:
        return f"Open, priority {kwargs['priority']}: {count} {noun}", {}
    return FILTER_HINT, {"display": "none"}


def clicked_task_id(clicked):
    """The task id from a dash-ag-grid ``cellClicked`` event.

    The event carries ``rowId`` (the grid's row id, which is our string ``key``), not the row's data.
    """
    row_id = (clicked or {}).get("rowId")
    return int(row_id) if str(row_id).isdigit() else None


def error_alert(message: str):
    return dbc.Alert(message, color="danger", className="py-2 mb-3") if message else ""


def _as_int(value):
    """dbc.Select may send numbers as strings; leave anything else for the service to reject."""
    return int(value) if isinstance(value, str) and value.isdigit() else value


def detail_panel():
    """Slide-in panel for viewing, editing and deleting one task."""
    return dbc.Offcanvas(
        [
            html.Div(id="detail-meta", className="text-muted small mb-3"),
            html.Div(id="detail-error"),
            dbc.Label("Title", html_for="edit-title"),
            dbc.Input(id="edit-title", type="text", maxLength=service.MAX_TITLE, className="mb-3"),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Label("Priority", html_for="edit-priority"),
                            dbc.Select(
                                id="edit-priority",
                                options=[{"label": f"Priority {p}", "value": p} for p in (1, 2, 3)],
                            ),
                        ]
                    ),
                    dbc.Col(
                        [
                            dbc.Label("Status", html_for="edit-status"),
                            dbc.Select(
                                id="edit-status",
                                options=[{"label": s.capitalize(), "value": s} for s in ("open", "done")],
                            ),
                        ]
                    ),
                ],
                className="g-2 mb-4",
            ),
            html.Div(
                [
                    dbc.Button("Save", id="save", n_clicks=0, color="primary", className="me-2"),
                    dbc.Button("Delete", id="delete", n_clicks=0, color="danger", outline=True),
                ]
            ),
            dcc.ConfirmDialog(id="confirm-delete", message="Delete this task? This cannot be undone."),
        ],
        id="detail",
        title="Task details",
        placement="end",
        is_open=False,
    )


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
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.Div(
                                    [
                                        html.H5("All tasks", className="mb-0 me-3"),
                                        html.Span(FILTER_HINT, id="filter-label", className="text-muted small"),
                                        dbc.Button(
                                            "Clear filter", id="clear-filter", n_clicks=0, size="sm",
                                            outline=True, color="light", className="ms-2", style={"display": "none"},
                                        ),
                                    ],
                                    className="d-flex align-items-center flex-wrap mb-3",
                                ),
                                task_grid(),
                            ]
                        )
                    )
                ),
                className="mt-3",
            ),
            detail_panel(),
            dcc.Store(id="version", data=0),
            dcc.Store(id="edits", data=0),
            dcc.Store(id="table-filter", data=None),
            dcc.Store(id="selected-id", data=None),
        ],
        fluid="lg",
        className="pb-4",
    )

    @dash_app.callback(
        Output("version", "data"),
        Output("title", "value"),
        Input("add", "n_clicks"),
        State("title", "value"),
        State("priority", "value"),
        State("version", "data"),
        prevent_initial_call=True,
    )
    def add_task(_n_clicks, title, priority, version):
        if not (title and title.strip()):
            return no_update, no_update
        with factory() as s:
            service.create_task(s, title.strip()[:service.MAX_TITLE], _priority(priority))
        return version + 1, ""

    @dash_app.callback(
        Output("per-day", "figure"),
        Output("by-priority", "figure"),
        Output("kpis", "children"),
        Input("version", "data"),
        Input("edits", "data"),
    )
    def refresh(_version, _edits):
        with factory() as s:
            per_day = pd.DataFrame(stats.completed_per_day(s), columns=["day", "completed"])
            prio = stats.open_by_priority(s)
            k = stats.kpis(s)
        return (
            style_figure(per_day_figure(per_day), template),
            style_figure(priority_figure(prio), template),
            kpi_cards(k),
        )

    @dash_app.callback(
        Output("task-table", "rowData"),
        Output("filter-label", "children"),
        Output("clear-filter", "style"),
        Input("version", "data"),
        Input("edits", "data"),
        Input("table-filter", "data"),
    )
    def refresh_table(_version, _edits, table_filter):
        with factory() as s:
            rows = table_rows(service.list_tasks(s, **filter_kwargs(table_filter)))
        label, style = describe_filter(table_filter, len(rows))
        return rows, label, style

    @dash_app.callback(
        Output("table-filter", "data"),
        Output("per-day", "clickData"),
        Output("by-priority", "clickData"),
        Input("per-day", "clickData"),
        Input("by-priority", "clickData"),
        Input("clear-filter", "n_clicks"),
        State("table-filter", "data"),
        prevent_initial_call=True,
    )
    def set_filter(day_click, priority_click, _clear, current):
        trigger = ctx.triggered_id
        if trigger == "clear-filter":
            new = None
        elif trigger == "per-day":
            new = filter_from_click("day", day_click)
        else:
            new = filter_from_click("priority", priority_click)
        if new is None and trigger != "clear-filter":
            return no_update, no_update, no_update  # e.g. the reset below, or a click that is not on a bar/slice
        if new == current:
            new = None  # clicking the active bar/slice again clears the filter
        # Reset both clickData values so the same bar or slice can be clicked again later.
        return new, None, None

    NO_CHANGE = (no_update,) * 8

    @dash_app.callback(
        Output("edits", "data"),
        Output("detail", "is_open"),
        Output("selected-id", "data"),
        Output("edit-title", "value"),
        Output("edit-priority", "value"),
        Output("edit-status", "value"),
        Output("detail-meta", "children"),
        Output("detail-error", "children"),
        Input("task-table", "cellClicked"),
        Input("save", "n_clicks"),
        Input("confirm-delete", "submit_n_clicks"),
        State("selected-id", "data"),
        State("edit-title", "value"),
        State("edit-priority", "value"),
        State("edit-status", "value"),
        State("edits", "data"),
        prevent_initial_call=True,
    )
    def detail(clicked, _save, _delete, selected, title, priority, status, edits):
        trigger = ctx.triggered_id
        with factory() as s:
            if trigger == "task-table":
                task_id = clicked_task_id(clicked)
                if task_id is None:
                    return NO_CHANGE
                try:
                    task = service.get_task(s, task_id)
                except TaskNotFound:  # deleted since the table was drawn: refresh instead of opening
                    return (edits + 1, False, None, no_update, no_update, no_update, no_update, "")
                return (no_update, True, task.id, task.title, task.priority, task.status, meta_text(task), "")
            if selected is None:
                return NO_CHANGE
            try:
                if trigger == "save":
                    service.update_task(s, selected, title=title, priority=_as_int(priority), status=status)
                elif trigger == "confirm-delete":
                    service.delete_task(s, selected)
            except ValidationError as exc:  # keep the panel open so the edit can be fixed
                return (no_update,) * 7 + (error_alert(str(exc)),)
            except TaskNotFound:  # already gone: close and refresh
                pass
        return (edits + 1, False, None, no_update, no_update, no_update, no_update, "")

    @dash_app.callback(
        Output("confirm-delete", "displayed"),
        Input("delete", "n_clicks"),
        prevent_initial_call=True,
    )
    def ask_to_delete(_n_clicks):
        return True

    return dash_app
