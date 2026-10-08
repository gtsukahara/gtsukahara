from datetime import date, datetime

import pytest

from examples.task_tracker import service
from examples.task_tracker.models import Task, make_session_factory
from examples.task_tracker.service import UNSET, TaskNotFound, ValidationError


@pytest.fixture
def session():
    with make_session_factory("sqlite://")() as s:
        yield s


# --- validation -----------------------------------------------------------

def test_validate_title_strips_and_rejects_bad_values():
    assert service.validate_title("  hi  ") == "hi"
    for bad in ("", "   ", None, 5, "x" * (service.MAX_TITLE + 1)):
        with pytest.raises(ValidationError):
            service.validate_title(bad)
    assert service.validate_title("x" * service.MAX_TITLE)  # boundary is allowed


def test_validate_priority_is_strict():
    assert [service.validate_priority(p) for p in (1, 2, 3)] == [1, 2, 3]
    for bad in (0, 4, "2", 2.0, True, None):
        with pytest.raises(ValidationError):
            service.validate_priority(bad)


def test_validate_status():
    assert service.validate_status("open") == "open"
    with pytest.raises(ValidationError):
        service.validate_status("bogus")


# --- create / get / list / delete ----------------------------------------

def test_create_and_get(session):
    task = service.create_task(session, " Write docs ", 1)
    assert (task.title, task.priority, task.status) == ("Write docs", 1, "open")
    assert service.get_task(session, task.id).id == task.id


def test_create_validates_before_writing(session):
    with pytest.raises(ValidationError):
        service.create_task(session, "ok", 9)
    assert session.query(Task).count() == 0


def test_get_missing_task_raises(session):
    with pytest.raises(TaskNotFound):
        service.get_task(session, 999)


def test_list_filters_by_status_and_validates_it(session):
    a = service.create_task(session, "a")
    b = service.create_task(session, "b")
    service.update_task(session, b.id, status="done")
    assert [t.id for t in service.list_tasks(session)] == [a.id, b.id]
    assert [t.id for t in service.list_tasks(session, "done")] == [b.id]
    with pytest.raises(ValidationError):
        service.list_tasks(session, "bogus")


def test_delete(session):
    task = service.create_task(session, "a")
    service.delete_task(session, task.id)
    assert session.query(Task).count() == 0
    with pytest.raises(TaskNotFound):
        service.delete_task(session, task.id)


# --- update ---------------------------------------------------------------

def test_update_any_subset_leaves_other_fields_alone(session):
    task = service.create_task(session, "old", 3)
    service.update_task(session, task.id, title="new")
    assert (task.title, task.priority, task.status) == ("new", 3, "open")
    service.update_task(session, task.id, priority=1)
    assert (task.title, task.priority) == ("new", 1)


def test_update_with_nothing_is_rejected(session):
    task = service.create_task(session, "a")
    with pytest.raises(ValidationError, match="nothing to update"):
        service.update_task(session, task.id)


def test_update_is_all_or_nothing(session):
    task = service.create_task(session, "keep", 2)
    with pytest.raises(ValidationError):
        service.update_task(session, task.id, title="changed", priority=99)
    session.refresh(task)
    assert (task.title, task.priority) == ("keep", 2)


def test_update_missing_task_raises(session):
    with pytest.raises(TaskNotFound):
        service.update_task(session, 999, title="x")


def test_completing_stamps_time_and_reopening_clears_it(session):
    task = service.create_task(session, "a")
    assert task.completed_at is None
    service.update_task(session, task.id, status="done")
    assert task.completed_at is not None
    service.update_task(session, task.id, status="open")
    assert task.completed_at is None


def test_marking_done_twice_keeps_the_original_completion_time(session):
    task = service.create_task(session, "a")
    service.update_task(session, task.id, status="done")
    original = datetime(2026, 1, 1, 12, 0)
    task.completed_at = original
    session.commit()
    service.update_task(session, task.id, status="done")
    assert task.completed_at == original


def test_editing_title_or_priority_does_not_touch_completion(session):
    task = service.create_task(session, "a")
    service.update_task(session, task.id, status="done")
    stamp = task.completed_at
    service.update_task(session, task.id, title="b", priority=3)
    assert task.completed_at == stamp and task.status == "done"


def test_unset_is_distinct_from_none(session):
    task = service.create_task(session, "a")
    with pytest.raises(ValidationError):
        service.update_task(session, task.id, title=None)  # None is a value, not "not provided"
    assert UNSET is not None


# --- list filters ---------------------------------------------------------

def _seed(session):
    day1, day2 = datetime(2026, 10, 1, 23, 59), datetime(2026, 10, 2, 0, 1)
    rows = [
        ("open p1", "open", 1, None), ("open p3", "open", 3, None), ("open p3b", "open", 3, None),
        ("done p1 day1", "done", 1, day1), ("done p3 day2", "done", 3, day2), ("done p1 day2", "done", 1, day2),
    ]
    for title, status, priority, completed in rows:
        session.add(Task(title=title, status=status, priority=priority, created_at=datetime(2026, 9, 1), completed_at=completed))
    session.commit()


def _titles(tasks):
    return [t.title for t in tasks]


def test_list_filters_by_priority(session):
    _seed(session)
    assert _titles(service.list_tasks(session, priority=3)) == ["open p3", "open p3b", "done p3 day2"]


def test_list_filters_by_completion_day_and_only_returns_done_tasks(session):
    _seed(session)
    assert _titles(service.list_tasks(session, completed_on=date(2026, 10, 2))) == ["done p3 day2", "done p1 day2"]
    assert _titles(service.list_tasks(session, completed_on=date(2026, 10, 1))) == ["done p1 day1"]  # 23:59 stays on day 1
    assert service.list_tasks(session, completed_on=date(2026, 12, 25)) == []


def test_list_filters_combine(session):
    _seed(session)
    assert _titles(service.list_tasks(session, status="open", priority=3)) == ["open p3", "open p3b"]
    assert _titles(service.list_tasks(session, priority=1, completed_on=date(2026, 10, 2))) == ["done p1 day2"]


def test_list_rejects_bad_filter_values(session):
    for kwargs in ({"priority": 7}, {"priority": "1"}, {"status": "x"}, {"completed_on": "2026-10-01"}):
        with pytest.raises(ValidationError):
            service.list_tasks(session, **kwargs)
