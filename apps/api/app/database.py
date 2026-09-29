"""Small persistent demo store; aggregate revisions prevent silent lost updates."""
import os
from pathlib import Path

from sqlalchemy import JSON, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = "records"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(40), index=True)
    data: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": revision}


def make_engine(url: str | None = None):
    default = Path(__file__).resolve().parents[1] / "data" / "launchpad.db"
    selected = url or os.getenv("DATABASE_URL")
    if not selected:
        default.parent.mkdir(parents=True, exist_ok=True)
        selected = f"sqlite:///{default.as_posix()}"
    options = {"check_same_thread": False, "timeout": 20} if selected.startswith("sqlite") else {}
    return create_engine(selected, connect_args=options)


def make_sessions(engine):
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
