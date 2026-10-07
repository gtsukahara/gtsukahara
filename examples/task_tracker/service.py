"""Task operations shared by the Flask API and the Dash page.

Each function takes a SQLAlchemy ``Session`` and commits its own change, so the
validation rules live in one place and are tested once.
"""
from typing import Optional

from sqlalchemy.orm import Session

from .models import STATUSES, Task, utcnow

MAX_TITLE = 200
UNSET = object()  # distinguishes "not provided" from None in partial updates


class ValidationError(ValueError):
    """The input is not acceptable (the API maps this to HTTP 400)."""


class TaskNotFound(LookupError):
    """No task with that id (the API maps this to HTTP 404)."""


def validate_title(title) -> str:
    if not isinstance(title, str) or not title.strip():
        raise ValidationError("title is required")
    title = title.strip()
    if len(title) > MAX_TITLE:
        raise ValidationError(f"title must be at most {MAX_TITLE} characters")
    return title


def validate_priority(priority) -> int:
    if not isinstance(priority, int) or isinstance(priority, bool) or not 1 <= priority <= 3:
        raise ValidationError("priority must be an integer from 1 to 3")
    return priority


def validate_status(status) -> str:
    if status not in STATUSES:
        raise ValidationError(f"status must be one of {list(STATUSES)}")
    return status


def list_tasks(session: Session, status: Optional[str] = None) -> list:
    if status is not None:
        validate_status(status)
    query = session.query(Task).order_by(Task.id)
    if status:
        query = query.filter(Task.status == status)
    return list(query)


def get_task(session: Session, task_id: int) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise TaskNotFound(f"task {task_id} not found")
    return task


def create_task(session: Session, title, priority=2) -> Task:
    task = Task(title=validate_title(title), priority=validate_priority(priority))
    session.add(task)
    session.commit()
    return task


def update_task(session: Session, task_id: int, *, title=UNSET, priority=UNSET, status=UNSET) -> Task:
    """Change any subset of title, priority and status.

    Everything is validated before anything is changed. Marking an open task done
    stamps ``completed_at``; marking a done task done again keeps the original time;
    reopening clears it.
    """
    if title is UNSET and priority is UNSET and status is UNSET:
        raise ValidationError("nothing to update: provide title, priority or status")
    changes = {}
    if title is not UNSET:
        changes["title"] = validate_title(title)
    if priority is not UNSET:
        changes["priority"] = validate_priority(priority)
    if status is not UNSET:
        changes["status"] = validate_status(status)
    task = get_task(session, task_id)
    for field in ("title", "priority"):
        if field in changes:
            setattr(task, field, changes[field])
    if "status" in changes and changes["status"] != task.status:
        task.status = changes["status"]
        task.completed_at = utcnow() if task.status == "done" else None
    session.commit()
    return task


def delete_task(session: Session, task_id: int) -> None:
    session.delete(get_task(session, task_id))
    session.commit()
