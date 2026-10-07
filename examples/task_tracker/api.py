"""CRUD blueprint for tasks."""
from flask import Blueprint, current_app, jsonify, request

from .models import STATUSES, Task, utcnow

bp = Blueprint("api", __name__, url_prefix="/api")


def _session():
    return current_app.extensions["task_sessions"]()


def _error(message, code):
    return jsonify(error=message), code


def _valid_priority(value):
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 3


@bp.get("/tasks")
def list_tasks():
    status = request.args.get("status")
    if status is not None and status not in STATUSES:
        return _error(f"status must be one of {list(STATUSES)}", 400)
    with _session() as s:
        query = s.query(Task).order_by(Task.id)
        if status:
            query = query.filter(Task.status == status)
        return jsonify([t.to_dict() for t in query])


@bp.post("/tasks")
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    priority = data.get("priority", 2)
    if not isinstance(title, str) or not title.strip():
        return _error("title is required", 400)
    if len(title.strip()) > 200:
        return _error("title must be at most 200 characters", 400)
    if not _valid_priority(priority):
        return _error("priority must be an integer from 1 to 3", 400)
    with _session() as s:
        task = Task(title=title.strip(), priority=priority)
        s.add(task)
        s.commit()
        return jsonify(task.to_dict()), 201


@bp.patch("/tasks/<int:task_id>")
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in STATUSES:
        return _error(f"status must be one of {list(STATUSES)}", 400)
    with _session() as s:
        task = s.get(Task, task_id)
        if task is None:
            return _error("task not found", 404)
        task.status = status
        task.completed_at = utcnow() if status == "done" else None
        s.commit()
        return jsonify(task.to_dict())


@bp.delete("/tasks/<int:task_id>")
def delete_task(task_id):
    with _session() as s:
        task = s.get(Task, task_id)
        if task is None:
            return _error("task not found", 404)
        s.delete(task)
        s.commit()
        return "", 204
