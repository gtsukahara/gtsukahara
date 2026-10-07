"""Task tracker: Flask + SQLAlchemy CRUD API with a Dash stats page at /dash/.

Run from the repo root:  python -m examples.task_tracker.app
Uses tasks.db in the current directory and seeds sample data if it is empty.
"""
import random
from datetime import timedelta

from flask import Flask

from .api import bp
from .dashboard import register_dashboard
from .models import Task, make_session_factory, utcnow


def seed_demo(factory, count=15, seed=42):
    rng = random.Random(seed)
    now = utcnow()
    with factory() as s:
        if s.query(Task).count():
            return
        for i in range(count):
            created = now - timedelta(days=rng.randint(1, 14), hours=rng.randint(0, 12))
            task = Task(title=f"Sample task {i + 1}", priority=rng.randint(1, 3), created_at=created)
            if rng.random() < 0.6:
                task.status = "done"
                task.completed_at = min(now, created + timedelta(hours=rng.randint(1, 72)))
            s.add(task)
        s.commit()


def create_app(db_url="sqlite:///tasks.db") -> Flask:
    server = Flask(__name__)
    server.extensions["task_sessions"] = make_session_factory(db_url)
    server.register_blueprint(bp)
    register_dashboard(server)
    return server


if __name__ == "__main__":
    app = create_app()
    seed_demo(app.extensions["task_sessions"])
    app.run(debug=True, port=5002)
