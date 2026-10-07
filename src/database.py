from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from src.settings import PROJECT_ROOT


class Database:
    def __init__(self, storage_dir: Path) -> None:
        self.directory = storage_dir.resolve()
        self.engine = create_engine(
            URL.create("sqlite", database=str(self.directory / "metadata.sqlite3")),
            connect_args={"check_same_thread": False, "timeout": 30},
        )

        @event.listens_for(self.engine, "connect")
        def configure_sqlite(connection: Any, record: Any) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    def initialize(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA journal_mode=WAL")
            connection.commit()
            config = Config(str(PROJECT_ROOT / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            connection.commit()

    @contextmanager
    def read(self) -> Iterator[Session]:
        with Session(self.engine, expire_on_commit=False) as session:
            yield session

    @contextmanager
    def write(self) -> Iterator[Session]:
        with Session(self.engine, expire_on_commit=False) as session:
            try:
                session.execute(text("BEGIN IMMEDIATE"))
                yield session
                session.commit()
            except BaseException:
                session.rollback()
                raise

    def close(self) -> None:
        self.engine.dispose()

