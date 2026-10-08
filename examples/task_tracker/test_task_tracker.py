from datetime import date, datetime, timedelta

import pytest

import dash_bootstrap_components as dbc

from examples.task_tracker import stats
from examples.task_tracker.app import create_app, seed_demo
from examples.task_tracker.dashboard import (
    _as_int, clicked_task_id, describe_filter, error_alert, filter_from_click, filter_kwargs, kpi_cards, meta_text,
    per_day_figure, priority_figure, table_rows,
)
from examples.theme import COLORWAY
from examples.task_tracker.models import Task

NOW = datetime(2026, 10, 7, 12, 0)


@pytest.fixture
def server():
    return create_app("sqlite://")


@pytest.fixture
def client(server):
    return server.test_client()


def make_task(factory, status="open", priority=2, created=NOW, completed=None):
    with factory() as s:
        s.add(Task(title="t", status=status, priority=priority, created_at=created, completed_at=completed))
        s.commit()


# --- CRUD -----------------------------------------------------------------

def test_crud_round_trip(client):
    created = client.post("/api/tasks", json={"title": " Write docs ", "priority": 1})
    assert created.status_code == 201
    task = created.get_json()
    assert task["title"] == "Write docs" and task["status"] == "open" and task["completed_at"] is None

    assert [t["id"] for t in client.get("/api/tasks").get_json()] == [task["id"]]

    done = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}).get_json()
    assert done["status"] == "done" and done["completed_at"] is not None
    assert client.get("/api/tasks?status=open").get_json() == []
    assert len(client.get("/api/tasks?status=done").get_json()) == 1

    reopened = client.patch(f"/api/tasks/{task['id']}", json={"status": "open"}).get_json()
    assert reopened["completed_at"] is None

    assert client.delete(f"/api/tasks/{task['id']}").status_code == 204
    assert client.get("/api/tasks").get_json() == []


def test_default_priority(client):
    assert client.post("/api/tasks", json={"title": "x"}).get_json()["priority"] == 2


@pytest.mark.parametrize(
    "body",
    [{}, {"title": ""}, {"title": "   "}, {"title": 5}, {"title": "x" * 201},
     {"title": "x", "priority": 0}, {"title": "x", "priority": 4},
     {"title": "x", "priority": "2"}, {"title": "x", "priority": True}],
)
def test_create_validation(client, body):
    assert client.post("/api/tasks", json=body).status_code == 400


def test_update_and_delete_errors(client):
    assert client.patch("/api/tasks/999", json={"status": "done"}).status_code == 404
    assert client.delete("/api/tasks/999").status_code == 404
    task_id = client.post("/api/tasks", json={"title": "x"}).get_json()["id"]
    assert client.patch(f"/api/tasks/{task_id}", json={"status": "bogus"}).status_code == 400
    assert client.get("/api/tasks?status=bogus").status_code == 400


def test_patch_edits_title_and_priority(client):
    task_id = client.post("/api/tasks", json={"title": "old", "priority": 3}).get_json()["id"]
    edited = client.patch(f"/api/tasks/{task_id}", json={"title": " new ", "priority": 1}).get_json()
    assert (edited["title"], edited["priority"], edited["status"]) == ("new", 1, "open")


def test_patch_can_change_several_fields_at_once(client):
    task_id = client.post("/api/tasks", json={"title": "old"}).get_json()["id"]
    done = client.patch(f"/api/tasks/{task_id}", json={"title": "x", "status": "done"}).get_json()
    assert done["title"] == "x" and done["completed_at"] is not None


@pytest.mark.parametrize(
    "body",
    [{}, {"title": ""}, {"priority": 0}, {"priority": "2"}, {"status": "bogus"}, {"colour": "red"},
     {"title": "ok", "priority": 99}],
)
def test_patch_validation(client, body):
    task_id = client.post("/api/tasks", json={"title": "keep", "priority": 2}).get_json()["id"]
    assert client.patch(f"/api/tasks/{task_id}", json=body).status_code == 400
    unchanged = client.get("/api/tasks").get_json()[0]
    assert (unchanged["title"], unchanged["priority"]) == ("keep", 2)  # nothing half-applied


def test_patch_error_messages_are_specific(client):
    task_id = client.post("/api/tasks", json={"title": "a"}).get_json()["id"]
    assert "unknown field" in client.patch(f"/api/tasks/{task_id}", json={"colour": 1}).get_json()["error"]
    assert "nothing to update" in client.patch(f"/api/tasks/{task_id}", json={}).get_json()["error"]


# --- stats ----------------------------------------------------------------

@pytest.fixture
def seeded(server):
    f = server.extensions["task_sessions"]
    day = timedelta(days=1)
    make_task(f, "done", created=NOW - 2 * day, completed=NOW)
    make_task(f, "done", created=NOW - 2 * day, completed=NOW)
    make_task(f, "done", created=NOW - 4 * day, completed=NOW - 3 * day)
    make_task(f, "done", created=NOW - 25 * day, completed=NOW - 20 * day)
    make_task(f, "open", priority=1)
    make_task(f, "open", priority=3)
    make_task(f, "open", priority=3)
    return f


def test_completed_per_day(seeded):
    with seeded() as s:
        rows = stats.completed_per_day(s, days=14, today=NOW)
    assert len(rows) == 14
    assert rows[-1] == (NOW.date(), 2)
    assert dict(rows)[(NOW - timedelta(days=3)).date()] == 1
    assert sum(n for _, n in rows) == 3  # the 20-day-old completion is outside the window


def test_open_by_priority(seeded):
    with seeded() as s:
        assert stats.open_by_priority(s) == {1: 1, 2: 0, 3: 2}


def test_kpis(seeded):
    with seeded() as s:
        k = stats.kpis(s, now=NOW)
    assert k["open"] == 3
    assert k["completed_this_week"] == 3
    # durations: 48h, 48h, 24h, 120h -> mean 60h
    assert k["avg_hours_to_complete"] == 60.0


def test_kpis_empty(server):
    with server.extensions["task_sessions"]() as s:
        assert stats.kpis(s, now=NOW) == {"open": 0, "completed_this_week": 0, "avg_hours_to_complete": 0.0}


def test_seed_demo_is_idempotent(server):
    f = server.extensions["task_sessions"]
    seed_demo(f, count=10)
    seed_demo(f, count=10)
    with f() as s:
        assert s.query(Task).count() == 10


# --- dashboard ------------------------------------------------------------

def add(client, n_clicks=1, title="Ship it", priority=1, version=0):
    """Fire the add-task callback the way the browser does."""
    payload = {
        "output": "..version.data...title.value..",
        "outputs": [
            {"id": "version", "property": "data"},
            {"id": "title", "property": "value"},
        ],
        "inputs": [{"id": "add", "property": "n_clicks", "value": n_clicks}],
        "state": [
            {"id": "title", "property": "value", "value": title},
            {"id": "priority", "property": "value", "value": priority},
            {"id": "version", "property": "data", "value": version},
        ],
        "changedPropIds": ["add.n_clicks"],
    }
    return client.post("/dash/_dash-update-component", json=payload)


def refresh_table(client, version=0, edits=0, table_filter=None):
    """Fire the table callback; returns (rows, filter label, clear-button style)."""
    payload = {
        "output": "..task-table.rowData...filter-label.children...clear-filter.style..",
        "outputs": [
            {"id": "task-table", "property": "rowData"},
            {"id": "filter-label", "property": "children"},
            {"id": "clear-filter", "property": "style"},
        ],
        "inputs": [
            {"id": "version", "property": "data", "value": version},
            {"id": "edits", "property": "data", "value": edits},
            {"id": "table-filter", "property": "data", "value": table_filter},
        ],
        "changedPropIds": ["table-filter.data"],
    }
    body = client.post("/dash/_dash-update-component", json=payload).get_json()["response"]
    return body["task-table"]["rowData"], body["filter-label"]["children"], body["clear-filter"]["style"]


def refresh(client, version=0, edits=0):
    """Fire the refresh callback (what runs on page load and after every change)."""
    payload = {
        "output": "..per-day.figure...by-priority.figure...kpis.children..",
        "outputs": [
            {"id": "per-day", "property": "figure"},
            {"id": "by-priority", "property": "figure"},
            {"id": "kpis", "property": "children"},
        ],
        "inputs": [
            {"id": "version", "property": "data", "value": version},
            {"id": "edits", "property": "data", "value": edits},
        ],
        "changedPropIds": ["version.data"],
    }
    return client.post("/dash/_dash-update-component", json=payload)


def test_dash_layout_mounted(client):
    assert "Task tracker" in str(client.get("/dash/_dash-layout").get_json())


def test_add_callback_creates_a_task_bumps_the_version_and_clears_the_input(client):
    resp = add(client, title="Ship it", priority=1, version=4)
    assert resp.status_code == 200
    body = resp.get_json()["response"]
    assert body["version"]["data"] == 5
    assert body["title"]["value"] == ""
    assert [(t["title"], t["priority"]) for t in client.get("/api/tasks").get_json()] == [("Ship it", 1)]


@pytest.mark.parametrize("title", ["", "   ", None])
def test_add_callback_ignores_a_blank_title(client, title):
    resp = add(client, title=title)
    assert resp.status_code == 200
    assert resp.get_json()["response"] == {}  # no_update on every output: version unchanged, input not cleared
    assert client.get("/api/tasks").get_json() == []


def test_dash_priority_can_arrive_as_a_string(client):
    assert add(client, priority="3").status_code == 200
    assert client.get("/api/tasks").get_json()[0]["priority"] == 3


def test_dash_invalid_priority_falls_back_to_default(client):
    assert add(client, priority="9").status_code == 200
    assert client.get("/api/tasks").get_json()[0]["priority"] == 2


def test_add_callback_truncates_an_overlong_title(client):
    assert add(client, title="x" * 500).status_code == 200
    assert len(client.get("/api/tasks").get_json()[0]["title"]) == 200


def test_refresh_returns_figures_kpis_and_table_rows(client):
    client.post("/api/tasks", json={"title": "one", "priority": 1})
    client.post("/api/tasks", json={"title": "two", "priority": 3})
    body = refresh(client).get_json()["response"]
    assert len(body["per-day"]["figure"]["data"]) == 1
    assert "Open" in str(body["kpis"]["children"])
    assert "task-table" not in body  # the table has its own callback, so charts do not redraw on a filter change
    rows, _, _ = refresh_table(client)
    assert [r["title"] for r in rows] == ["one", "two"]


def test_a_task_added_through_the_dashboard_shows_up_in_the_table(client):
    add(client, title="From the form")
    rows, _, _ = refresh_table(client, version=1)
    assert [r["title"] for r in rows] == ["From the form"]


def test_table_rows_order_open_first_then_priority_then_newest():
    def task(id_, status, priority):
        t = Task(id=id_, title=f"t{id_}", status=status, priority=priority, created_at=NOW)
        t.completed_at = NOW if status == "done" else None
        return t

    rows = table_rows([task(1, "done", 1), task(2, "open", 3), task(3, "open", 1), task(4, "open", 1)])
    assert [r["id"] for r in rows] == [4, 3, 2, 1]


def test_table_row_shape_and_date_format():
    t = Task(id=7, title="x", status="done", priority=2, created_at=datetime(2026, 1, 2, 3, 4), completed_at=datetime(2026, 1, 5, 6, 7))
    assert table_rows([t]) == [
        {"id": 7, "key": "7", "title": "x", "priority": 2, "status": "done", "created": "2026-01-02 03:04", "completed": "2026-01-05 06:07"}
    ]
    t.completed_at = None
    assert table_rows([t])[0]["completed"] == ""


def test_the_grid_is_mounted_with_an_id_per_row(client):
    layout = str(client.get("/dash/_dash-layout").get_json())
    assert "AgGrid" in layout and "task-table" in layout and "params.data.key" in layout


def test_kpi_cards_show_values():
    text = str(kpi_cards({"open": 4, "completed_this_week": 2, "avg_hours_to_complete": 12.5}))
    assert "12.5 h" in text and "'4'" in text and "'2'" in text


def test_charts_use_the_shared_palette_not_the_theme_colours():
    import pandas as pd

    bar = per_day_figure(pd.DataFrame({"day": ["a", "b"], "completed": [1, 2]}))
    assert bar.data[0].marker.color == COLORWAY[0]
    pie = priority_figure({1: 2, 2: 1, 3: 0})
    assert list(pie.layout.piecolorway) == COLORWAY
    assert list(pie.data[0].labels) == ["Priority 1", "Priority 2"]  # empty slice skipped


def test_pie_with_no_open_tasks_says_so():
    fig = priority_figure({1: 0, 2: 0, 3: 0})
    assert [a.text for a in fig.layout.annotations] == ["No open tasks"]


def test_page_links_the_chosen_theme_and_rejects_unknown_ones():
    html = create_app("sqlite://", theme="flatly").test_client().get("/dash/").get_data(as_text=True)
    assert dbc.themes.FLATLY in html
    with pytest.raises(ValueError, match="unknown theme"):
        create_app("sqlite://", theme="neon")


# --- detail panel ---------------------------------------------------------

DETAIL_OUTPUTS = [
    "edits.data", "detail.is_open", "selected-id.data", "edit-title.value",
    "edit-priority.value", "edit-status.value", "detail-meta.children", "detail-error.children",
]
TRIGGERS = {"click": "task-table.cellClicked", "save": "save.n_clicks", "delete": "confirm-delete.submit_n_clicks"}


def detail(client, trigger, *, clicked=None, selected=None, title=None, priority=None, status=None, edits=0):
    """Fire the detail-panel callback as the browser would; return {component id: new value}.

    Outputs the callback leaves alone (no_update) are absent from the result.
    """
    payload = {
        "output": "..{}..".format("...".join(DETAIL_OUTPUTS)),
        "outputs": [{"id": o.split(".")[0], "property": o.split(".")[1]} for o in DETAIL_OUTPUTS],
        "inputs": [
            {"id": "task-table", "property": "cellClicked", "value": clicked},
            {"id": "save", "property": "n_clicks", "value": 1 if trigger == "save" else 0},
            {"id": "confirm-delete", "property": "submit_n_clicks", "value": 1 if trigger == "delete" else 0},
        ],
        "state": [
            {"id": "selected-id", "property": "data", "value": selected},
            {"id": "edit-title", "property": "value", "value": title},
            {"id": "edit-priority", "property": "value", "value": priority},
            {"id": "edit-status", "property": "value", "value": status},
            {"id": "edits", "property": "data", "value": edits},
        ],
        "changedPropIds": [TRIGGERS[trigger]],
    }
    resp = client.post("/dash/_dash-update-component", json=payload)
    assert resp.status_code == 200
    return {cid: next(iter(props.values())) for cid, props in resp.get_json()["response"].items()}


def new_task(client, title="Write docs", priority=2):
    return client.post("/api/tasks", json={"title": title, "priority": priority}).get_json()


def row_click(task):
    """A dash-ag-grid cellClicked event, as captured from a real browser session (note: no ``data`` field)."""
    return {"value": task["title"], "colId": "title", "rowIndex": 0, "rowId": str(task["id"]), "timestamp": 1791417601932}


def test_clicking_a_row_opens_the_panel_filled_from_the_database(client):
    task = new_task(client, "Write docs", 3)
    out = detail(client, "click", clicked=row_click(task))
    assert out["detail"] is True
    assert out["selected-id"] == task["id"]
    assert (out["edit-title"], out["edit-priority"], out["edit-status"]) == ("Write docs", 3, "open")
    assert out["detail-meta"].startswith("Created ") and out["detail-error"] == ""
    assert "edits" not in out  # opening changes nothing, so no refresh


def test_the_row_id_in_the_click_event_is_what_selects_the_task(client):
    first, second = new_task(client, "first"), new_task(client, "second")
    assert detail(client, "click", clicked=row_click(second))["edit-title"] == "second"
    assert detail(client, "click", clicked=row_click(first))["edit-title"] == "first"


@pytest.mark.parametrize("clicked", [None, {}, {"rowId": None}, {"rowId": "abc"}, {"data": {"id": 1}}])
def test_a_click_without_a_row_changes_nothing(client, clicked):
    assert detail(client, "click", clicked=clicked) == {}


def test_clicking_a_row_deleted_elsewhere_refreshes_instead_of_opening(client):
    task = new_task(client)
    client.delete(f"/api/tasks/{task['id']}")
    out = detail(client, "click", clicked=row_click(task), edits=4)
    assert out["edits"] == 5 and out["detail"] is False and out["selected-id"] is None


def test_saving_applies_all_three_fields_closes_the_panel_and_triggers_a_refresh(client):
    task = new_task(client, "old", 3)
    out = detail(client, "save", selected=task["id"], title=" new ", priority=1, status="done", edits=2)
    assert out["edits"] == 3 and out["detail"] is False and out["selected-id"] is None and out["detail-error"] == ""
    saved = client.get("/api/tasks").get_json()[0]
    assert (saved["title"], saved["priority"], saved["status"]) == ("new", 1, "done")
    assert saved["completed_at"] is not None


def test_saving_accepts_a_priority_sent_as_a_string(client):
    task = new_task(client)
    detail(client, "save", selected=task["id"], title="x", priority="3", status="open")
    assert client.get("/api/tasks").get_json()[0]["priority"] == 3


@pytest.mark.parametrize(
    "fields,message",
    [
        ({"title": "   ", "priority": 2, "status": "open"}, "title is required"),
        ({"title": "ok", "priority": "9", "status": "open"}, "priority must be"),
        ({"title": "ok", "priority": "abc", "status": "open"}, "priority must be"),
        ({"title": "ok", "priority": 2, "status": "bogus"}, "status must be"),
    ],
)
def test_saving_a_bad_edit_shows_an_error_keeps_the_panel_open_and_changes_nothing(client, fields, message):
    task = new_task(client, "keep", 2)
    out = detail(client, "save", selected=task["id"], **fields)
    assert message in str(out["detail-error"])
    assert "detail" not in out and "edits" not in out and "selected-id" not in out  # stays open, nothing to refresh
    unchanged = client.get("/api/tasks").get_json()[0]
    assert (unchanged["title"], unchanged["priority"], unchanged["status"]) == ("keep", 2, "open")


def test_saving_a_task_that_was_deleted_elsewhere_closes_the_panel_and_refreshes(client):
    task = new_task(client)
    client.delete(f"/api/tasks/{task['id']}")
    out = detail(client, "save", selected=task["id"], title="x", priority=1, status="open", edits=0)
    assert out["detail"] is False and out["edits"] == 1 and out["detail-error"] == ""


def test_confirming_delete_removes_the_task_and_closes_the_panel(client):
    keep, drop = new_task(client, "keep"), new_task(client, "drop")
    out = detail(client, "delete", selected=drop["id"], edits=7)
    assert out["edits"] == 8 and out["detail"] is False and out["selected-id"] is None
    assert [t["id"] for t in client.get("/api/tasks").get_json()] == [keep["id"]]


def test_confirming_delete_for_an_already_deleted_task_is_harmless(client):
    task = new_task(client)
    client.delete(f"/api/tasks/{task['id']}")
    out = detail(client, "delete", selected=task["id"])
    assert out["detail"] is False and out["detail-error"] == ""


@pytest.mark.parametrize("trigger", ["save", "delete"])
def test_save_and_delete_do_nothing_when_no_task_is_selected(client, trigger):
    new_task(client)
    assert detail(client, trigger, selected=None, title="x", priority=1, status="open") == {}
    assert len(client.get("/api/tasks").get_json()) == 1


def test_the_delete_button_asks_for_confirmation_first(client):
    payload = {
        "output": "confirm-delete.displayed",
        "outputs": {"id": "confirm-delete", "property": "displayed"},
        "inputs": [{"id": "delete", "property": "n_clicks", "value": 1}],
        "changedPropIds": ["delete.n_clicks"],
    }
    resp = client.post("/dash/_dash-update-component", json=payload)
    assert resp.get_json()["response"]["confirm-delete"]["displayed"] is True


def test_an_edit_made_in_the_panel_shows_up_in_the_table(client):
    task = new_task(client, "before", 3)
    detail(client, "save", selected=task["id"], title="after", priority=1, status="open", edits=0)
    rows, _, _ = refresh_table(client, edits=1)
    assert [(r["title"], r["priority"]) for r in rows] == [("after", 1)]


def test_the_panel_and_its_controls_are_in_the_layout(client):
    layout = str(client.get("/dash/_dash-layout").get_json())
    for piece in ("Offcanvas", "ConfirmDialog", "edit-title", "edit-priority", "edit-status", "'save'", "'delete'"):
        assert piece in layout


def test_clicked_task_id():
    assert clicked_task_id({"rowId": "14"}) == 14 and clicked_task_id({"rowId": 14}) == 14
    assert clicked_task_id(None) is None and clicked_task_id({}) is None and clicked_task_id({"rowId": "x"}) is None


def test_panel_helpers():
    t = Task(id=1, title="x", status="open", priority=2, created_at=datetime(2026, 1, 2, 3, 4))
    assert meta_text(t) == "Created 2026-01-02 03:04 UTC"
    t.completed_at = datetime(2026, 1, 5, 6, 7)
    assert meta_text(t) == "Created 2026-01-02 03:04 UTC  ·  Completed 2026-01-05 06:07 UTC"
    assert error_alert("") == "" and "boom" in str(error_alert("boom"))
    assert (_as_int("3"), _as_int(2), _as_int("abc"), _as_int(None)) == (3, 2, "abc", None)


# --- chart-click filters ---------------------------------------------------

# Captured from a real browser session (dash 4.4.1, plotly 7.1.0). Extra keys are what Plotly really sends.
BAR_CLICK = {"points": [{"curveNumber": 0, "pointNumber": 5, "pointIndex": 5, "x": "2026-09-30", "y": 3,
                         "label": "2026-09-30", "value": 3, "xPixel": 251.575, "yPixel": 104.8,
                         "bbox": {"x0": 252.26, "x1": 282.89, "y0": 120.8, "y1": 120.8}}], "timestamp": 1791417796073}
PIE_CLICK = {"points": [{"curveNumber": 0, "label": "Priority 3", "color": "#E69F00", "value": 1,
                         "percent": 0.14285714285714285, "v": 1, "i": 1, "pointNumber": 1,
                         "bbox": {"x0": 73.5, "x1": 149.5, "y0": 165.2, "y1": 241.1}, "pointNumbers": [1]}],
             "timestamp": 1791417804947}


def set_filter(client, trigger, *, day=None, priority=None, clear=0, current=None):
    """Fire the chart-click callback; returns {component id: new value} for the outputs it changed."""
    payload = {
        "output": "..table-filter.data...per-day.clickData...by-priority.clickData..",
        "outputs": [
            {"id": "table-filter", "property": "data"},
            {"id": "per-day", "property": "clickData"},
            {"id": "by-priority", "property": "clickData"},
        ],
        "inputs": [
            {"id": "per-day", "property": "clickData", "value": day},
            {"id": "by-priority", "property": "clickData", "value": priority},
            {"id": "clear-filter", "property": "n_clicks", "value": clear},
        ],
        "state": [{"id": "table-filter", "property": "data", "value": current}],
        "changedPropIds": [{"day": "per-day.clickData", "priority": "by-priority.clickData", "clear": "clear-filter.n_clicks"}[trigger]],
    }
    resp = client.post("/dash/_dash-update-component", json=payload)
    assert resp.status_code == 200
    return {cid: next(iter(props.values())) for cid, props in resp.get_json()["response"].items()}


def test_filter_from_a_real_bar_click():
    assert filter_from_click("day", BAR_CLICK) == {"kind": "day", "value": "2026-09-30"}


def test_filter_from_a_real_pie_click():
    assert filter_from_click("priority", PIE_CLICK) == {"kind": "priority", "value": 3}


@pytest.mark.parametrize(
    "kind,click",
    [("day", None), ("day", {}), ("day", {"points": []}), ("day", {"points": [{"x": "not a date"}]}),
     ("day", {"points": [{"y": 3}]}), ("priority", None), ("priority", {"points": [{"label": "Priority"}]}),
     ("priority", {"points": [{"label": "Priority x"}]}), ("priority", {"points": [{"value": 1}]})],
)
def test_filter_from_click_ignores_malformed_clicks(kind, click):
    assert filter_from_click(kind, click) is None


def test_a_timestamp_style_day_value_is_accepted():
    assert filter_from_click("day", {"points": [{"x": "2026-09-30T00:00:00"}]}) == {"kind": "day", "value": "2026-09-30"}


def test_filter_kwargs():
    assert filter_kwargs({"kind": "day", "value": "2026-09-30"}) == {"completed_on": date(2026, 9, 30)}
    assert filter_kwargs({"kind": "priority", "value": 3}) == {"status": "open", "priority": 3}
    for bad in (None, {}, {"kind": "day"}, {"kind": "day", "value": "nope"}, {"kind": "priority", "value": 9},
                {"kind": "priority", "value": "3"}, {"kind": "weird", "value": 1}, "text"):
        assert filter_kwargs(bad) == {}


def test_describe_filter():
    assert describe_filter(None, 5)[1] == {"display": "none"} and "Click a bar" in describe_filter(None, 5)[0]
    label, style = describe_filter({"kind": "day", "value": "2026-09-30"}, 3)
    assert label == "Completed on 2026-09-30: 3 tasks" and style == {}
    assert describe_filter({"kind": "priority", "value": 2}, 1)[0] == "Open, priority 2: 1 task"
    assert describe_filter({"kind": "priority", "value": 2}, 0)[0] == "Open, priority 2: 0 tasks"


def test_clicking_a_bar_sets_a_day_filter_and_resets_both_click_values(client):
    out = set_filter(client, "day", day=BAR_CLICK)
    assert out == {"table-filter": {"kind": "day", "value": "2026-09-30"}, "per-day": None, "by-priority": None}


def test_clicking_a_slice_sets_a_priority_filter(client):
    assert set_filter(client, "priority", priority=PIE_CLICK)["table-filter"] == {"kind": "priority", "value": 3}


def test_clicking_a_different_bar_replaces_the_filter(client):
    current = {"kind": "priority", "value": 3}
    assert set_filter(client, "day", day=BAR_CLICK, current=current)["table-filter"] == {"kind": "day", "value": "2026-09-30"}


def test_clicking_the_active_bar_or_slice_again_clears_the_filter(client):
    assert set_filter(client, "day", day=BAR_CLICK, current={"kind": "day", "value": "2026-09-30"})["table-filter"] is None
    assert set_filter(client, "priority", priority=PIE_CLICK, current={"kind": "priority", "value": 3})["table-filter"] is None


def test_the_clear_button_clears_the_filter(client):
    out = set_filter(client, "clear", clear=1, current={"kind": "priority", "value": 1})
    assert out["table-filter"] is None


@pytest.mark.parametrize("trigger,kw", [("day", {"day": None}), ("priority", {"priority": None}),
                                        ("day", {"day": {"points": []}}), ("priority", {"priority": {"points": [{"label": "?"}]}})])
def test_a_click_that_is_not_on_a_bar_or_slice_changes_nothing(client, trigger, kw):
    assert set_filter(client, trigger, current={"kind": "day", "value": "2026-09-30"}, **kw) == {}


def _seed_for_filters(client):
    ids = {}
    for title, priority in (("a", 1), ("b", 3), ("c", 3), ("d", 2), ("e", 3)):
        ids[title] = new_task(client, title, priority)["id"]
    for title in ("d", "e"):  # done today (UTC); "e" is priority 3, so the pie filter must exclude it
        client.patch(f"/api/tasks/{ids[title]}", json={"status": "done"})
    return ids


def test_the_table_shows_only_open_tasks_of_the_clicked_priority(client):
    _seed_for_filters(client)
    rows, label, style = refresh_table(client, table_filter={"kind": "priority", "value": 3})
    assert sorted(r["title"] for r in rows) == ["b", "c"] and all(r["status"] == "open" for r in rows)
    assert label == "Open, priority 3: 2 tasks" and style == {}


def test_the_table_shows_only_tasks_completed_on_the_clicked_day(client):
    _seed_for_filters(client)
    today = datetime.utcnow().date().isoformat()
    rows, label, _ = refresh_table(client, table_filter={"kind": "day", "value": today})
    assert sorted(r["title"] for r in rows) == ["d", "e"] and label == f"Completed on {today}: 2 tasks"
    rows, label, _ = refresh_table(client, table_filter={"kind": "day", "value": "2001-01-01"})
    assert rows == [] and label == "Completed on 2001-01-01: 0 tasks"


def test_with_no_filter_the_table_shows_everything_and_hides_the_clear_button(client):
    _seed_for_filters(client)
    rows, label, style = refresh_table(client, table_filter=None)
    assert len(rows) == 5 and "Click a bar" in label and style == {"display": "none"}


def test_a_garbage_stored_filter_falls_back_to_showing_everything(client):
    _seed_for_filters(client)
    rows, _, style = refresh_table(client, table_filter={"kind": "day", "value": "garbage"})
    assert len(rows) == 5 and style == {"display": "none"}


def test_the_filter_bar_and_store_are_in_the_layout(client):
    layout = str(client.get("/dash/_dash-layout").get_json())
    for piece in ("table-filter", "filter-label", "clear-filter"):
        assert piece in layout
