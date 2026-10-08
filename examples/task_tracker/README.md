# Task tracker with stats

Flask + SQLAlchemy provide a CRUD API for tasks; a Dash page at `/dash/` shows
completion trends. Uses the `sqlalchemy` pin already in `requirements.txt`.

## API
- `GET /api/tasks?status=open|done`
- `POST /api/tasks` with `{"title": "...", "priority": 1-3}` (priority defaults to 2)
- `PATCH /api/tasks/<id>` with any of `title`, `priority`, `status`. Unknown fields and empty bodies are rejected,
  and nothing is applied unless everything is valid. Setting `status` to `done` stamps `completed_at` (marking an
  already-done task done again keeps the original time); `open` clears it.
- `DELETE /api/tasks/<id>`

Validation: non-empty title (max 200 chars), integer priority 1-3, 400 for bad
input, 404 for unknown ids.

## Dash page (`/dash/`)
- Bar chart: tasks completed per day, last 14 days
- Pie chart: open tasks by priority
- KPIs: open count, completed this week, average time to complete
- **All tasks** table (AG Grid): sortable, filterable, paged; open tasks first, done tasks dimmed
- **Click a bar** (tasks completed that day) **or a pie slice** (open tasks of that priority) to filter the table.
  Click the same bar or slice again, or press Clear filter, to remove the filter.
- **Click any row** to open a detail panel: edit the title, priority and status, then Save, or Delete (with a
  confirmation). Bad input shows an error in the panel and changes nothing.
- Add-task form that creates a task and refreshes the charts, KPIs and table
- Styled with the shared theme (see `examples/theme.py`); choose another with `EXAMPLES_THEME=FLATLY`

## Layout
```
models.py     # SQLAlchemy 2.0 Task model, session factory
service.py    # create/get/list/update/delete + validation, shared by the API and the dashboard
api.py        # Flask blueprint: maps the service to HTTP (400 for ValidationError, 404 for TaskNotFound)
stats.py      # plain stats queries (completed_per_day, open_by_priority, kpis)
dashboard.py  # Dash layout and callbacks: `add_task` writes and bumps a version counter; `refresh` redraws from the DB
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
- The dashboard has two callbacks: one that writes (add) and bumps a `version` store, and one that reads and redraws
  everything when `version` changes. Later edit/delete actions just bump the same counter.
- The table uses `dash-ag-grid`, not `dash_table.DataTable`, which Dash 4 has deprecated.
- A grid click event carries only the row's id (`rowId`), not its data. Rows therefore get a string `key` (`getRowId`),
  and the panel always loads the task from the database, so it never shows stale grid data.
- The chart-click filter lives in a `table-filter` store. `refresh` redraws the charts and KPIs; `refresh_table` redraws
  only the table, so a filter change does not re-render the charts. After each click the callback resets both
  charts' `clickData`, which is what lets the same bar or slice be clicked again later.
- Edits and deletes bump a separate `edits` counter (the add form bumps `version`); `refresh` listens to both, so no
  output has two writers.
- Plain SQLAlchemy with one session per request, not Flask-SQLAlchemy, to keep dependencies as they are.
- Charts pass the shared palette to Plotly Express explicitly (`px` fixes marker colours when it builds a figure, so a
  layout-level palette alone would not recolour the bars and slices).
- Timestamps are naive UTC because SQLite does not store timezone info.
- No authentication; out of scope for this example.
