from datetime import datetime, timedelta

import pytest

import dash_bootstrap_components as dbc

from examples.task_tracker import stats
from examples.task_tracker.app import create_app, seed_demo
from examples.task_tracker.dashboard import kpi_cards, per_day_figure, priority_figure
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

def update(client, n_clicks, title="Ship it", priority=1):
    payload = {
        "output": "..per-day.figure...by-priority.figure...kpis.children...title.value..",
        "outputs": [
            {"id": "per-day", "property": "figure"},
            {"id": "by-priority", "property": "figure"},
            {"id": "kpis", "property": "children"},
            {"id": "title", "property": "value"},
        ],
        "inputs": [{"id": "add", "property": "n_clicks", "value": n_clicks}],
        "state": [
            {"id": "title", "property": "value", "value": title},
            {"id": "priority", "property": "value", "value": priority},
        ],
        "changedPropIds": ["add.n_clicks"],
    }
    return client.post("/dash/_dash-update-component", json=payload)


def test_dash_layout_mounted(client):
    assert "Task tracker" in str(client.get("/dash/_dash-layout").get_json())


def test_dash_priority_can_arrive_as_a_string(client):
    assert update(client, n_clicks=1, priority="3").status_code == 200
    assert client.get("/api/tasks").get_json()[0]["priority"] == 3


def test_dash_invalid_priority_falls_back_to_default(client):
    assert update(client, n_clicks=1, priority="9").status_code == 200
    assert client.get("/api/tasks").get_json()[0]["priority"] == 2


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


def test_dash_add_task_callback(client):
    first = update(client, n_clicks=0)  # initial load: nothing added
    assert first.status_code == 200
    assert client.get("/api/tasks").get_json() == []

    resp = update(client, n_clicks=1)
    assert resp.status_code == 200
    body = resp.get_json()["response"]
    cards = str(body["kpis"]["children"])
    assert "Open" in cards and "Completed this week" in cards and "Avg time to complete" in cards
    assert body["title"]["value"] == ""
    tasks = client.get("/api/tasks").get_json()
    assert [(t["title"], t["priority"]) for t in tasks] == [("Ship it", 1)]
