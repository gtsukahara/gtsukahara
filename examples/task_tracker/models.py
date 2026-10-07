"""SQLAlchemy 2.0 model and session helpers."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

STATUSES = ("open", "done")


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite does not store tzinfo)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (CheckConstraint("priority BETWEEN 1 AND 3", name="ck_priority"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(10), default="open")
    priority: Mapped[int] = mapped_column(default=2)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(default=None)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


def make_session_factory(db_url: str) -> sessionmaker:
    """Create the engine and tables. In-memory SQLite shares one connection."""
    if db_url in ("sqlite://", "sqlite:///:memory:"):
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
