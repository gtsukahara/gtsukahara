# Task tracker with stats (outline)

Status: **outline only, nothing implemented yet.**

Flask plus SQLAlchemy handle CRUD for tasks; a Dash page shows completion trends.
Uses the `sqlalchemy==2.0.20` pin already in `requirements.txt`.

## Goal
Create, complete and delete tasks through a Flask API, and see throughput charts in Dash.

## Layout
```
examples/task_tracker/
  app.py          # create_app(config): Flask app, DB setup, Dash mount
  models.py       # SQLAlchemy 2.0 declarative model: Task
  api.py          # Flask blueprint with CRUD routes
  dashboard.py    # Dash layout and callbacks
  test_app.py
```

## Data model
`Task(id, title, status["open"|"done"], created_at, completed_at, priority 1-3)`
SQLite file for the demo; in-memory SQLite (`sqlite://`) in tests.

## Flask API
- `GET /api/tasks?status=open|done`
- `POST /api/tasks` with `{title, priority}`
- `PATCH /api/tasks/<id>` with `{status}` (sets `completed_at` when done)
- `DELETE /api/tasks/<id>`
- Basic validation: non-empty title, priority 1-3, 404 for unknown id

## Dash page (`/dash/`)
- Bar: tasks completed per day (last 14 days)
- Pie: open tasks by priority
- KPI: open count, completed this week, average time to complete
- Optional: input box that POSTs a new task, then refreshes the charts

## Tests
- CRUD round trip against in-memory DB
- validation errors return 400/404
- stats query returns the expected counts for a seeded set of tasks

## Build steps
1. `models.py` and DB session handling
2. CRUD blueprint with tests
3. Stats queries (plain functions, unit-tested)
4. Dash charts on top of the stats queries
5. Optional add-task form

## Open questions
- Use Flask-SQLAlchemy, or plain SQLAlchemy with a per-request session? (plain keeps dependencies as they are)
- Authentication: out of scope for the first draft
