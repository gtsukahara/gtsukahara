"""CRUD blueprint for tasks. The rules live in ``service``; this maps them to HTTP."""
from flask import Blueprint, current_app, jsonify, request

from . import service
from .service import UNSET, TaskNotFound, ValidationError

bp = Blueprint("api", __name__, url_prefix="/api")

UPDATABLE = ("title", "priority", "status")


def _session():
    return current_app.extensions["task_sessions"]()


@bp.errorhandler(ValidationError)
def _bad_request(exc):
    return jsonify(error=str(exc)), 400


@bp.errorhandler(TaskNotFound)
def _not_found(_exc):
    return jsonify(error="task not found"), 404


@bp.get("/tasks")
def list_tasks():
    with _session() as s:
        return jsonify([t.to_dict() for t in service.list_tasks(s, request.args.get("status"))])


@bp.post("/tasks")
def create_task():
    data = request.get_json(silent=True) or {}
    with _session() as s:
        task = service.create_task(s, data.get("title"), data.get("priority", 2))
        return jsonify(task.to_dict()), 201


@bp.patch("/tasks/<int:task_id>")
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    unknown = sorted(set(data) - set(UPDATABLE))
    if unknown:
        raise ValidationError(f"unknown field(s): {', '.join(unknown)}")
    with _session() as s:
        task = service.update_task(s, task_id, **{f: data.get(f, UNSET) for f in UPDATABLE})
        return jsonify(task.to_dict())


@bp.delete("/tasks/<int:task_id>")
def delete_task(task_id):
    with _session() as s:
        service.delete_task(s, task_id)
        return "", 204
