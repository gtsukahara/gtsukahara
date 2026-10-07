"""Plain, unit-testable stats queries over Task."""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Task, utcnow


def completed_per_day(session: Session, days: int = 14, today: Optional[datetime] = None) -> list:
    """[(date, count)] for each of the last ``days`` days, oldest first, zeros included."""
    today = (today or utcnow()).date()
    start = today - timedelta(days=days - 1)
    rows = session.execute(
        select(func.date(Task.completed_at), func.count())
        .where(Task.status == "done", Task.completed_at >= datetime.combine(start, datetime.min.time()))
        .group_by(func.date(Task.completed_at))
    ).all()
    counts = {d: n for d, n in rows}
    result = []
    for i in range(days):
        day = start + timedelta(days=i)
        result.append((day, counts.get(day.isoformat(), 0)))
    return result


def open_by_priority(session: Session) -> dict:
    """{priority: open task count} for priorities 1-3, zeros included."""
    rows = session.execute(
        select(Task.priority, func.count()).where(Task.status == "open").group_by(Task.priority)
    ).all()
    counts = dict(rows)
    return {p: counts.get(p, 0) for p in (1, 2, 3)}


def kpis(session: Session, now: Optional[datetime] = None) -> dict:
    now = now or utcnow()
    open_count = session.scalar(select(func.count()).where(Task.status == "open"))
    week_ago = now - timedelta(days=7)
    done_week = session.scalar(
        select(func.count()).where(Task.status == "done", Task.completed_at >= week_ago)
    )
    done = session.scalars(select(Task).where(Task.status == "done")).all()
    durations = [(t.completed_at - t.created_at).total_seconds() for t in done if t.completed_at]
    avg_hours = sum(durations) / len(durations) / 3600 if durations else 0.0
    return {
        "open": open_count,
        "completed_this_week": done_week,
        "avg_hours_to_complete": round(avg_hours, 1),
    }
