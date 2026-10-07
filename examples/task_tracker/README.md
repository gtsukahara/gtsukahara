# Task tracker with stats

Flask + SQLAlchemy provide a CRUD API for tasks; a Dash page at `/dash/` shows
completion trends. Uses the `sqlalchemy` pin already in `requirements.txt`.

## API
- `GET /api/tasks?status=open|done`
- `POST /api/tasks` with `{"title": "...", "priority": 1-3}` (priority defaults to 2)
- `PATCH /api/tasks/<id>` with `{"status": "open"|"done"}` (sets or clears `completed_at`)
- `DELETE /api/tasks/<id>`

Validation: non-empty title (max 200 chars), integer priority 1-3, 400 for bad
input, 404 for unknown ids.

## Dash page (`/dash/`)
- Bar chart: tasks completed per day, last 14 days
- Pie chart: open tasks by priority
- KPIs: open count, completed this week, average time to complete
- Add-task form that creates a task and refreshes the charts

## Layout
```
models.py     # SQLAlchemy 2.0 Task model, session factory
api.py        # Flask blueprint with the CRUD routes
stats.py      # plain stats queries (completed_per_day, open_by_priority, kpis)
dashboard.py  # Dash layout and callback
app.py        # create_app(db_url), demo seed data, entry point
test_task_tracker.py
```

## Run
From the repo root, in a venv with `requirements.txt` installed:

```bash
python -m examples.task_tracker.app
```

Then open http://127.0.0.1:5002/dash/ . This creates `tasks.db` in the current
directory (git-ignored) and seeds sample tasks if it is empty.

## Test
```bash
pytest examples/task_tracker
```
Tests use in-memory SQLite.

## Design notes
- Plain SQLAlchemy with one session per request, not Flask-SQLAlchemy, to keep dependencies as they are.
- Timestamps are naive UTC because SQLite does not store timezone info.
- No authentication; out of scope for this example.
