"""SQLite-адаптери для IProjectRepository та IBrigadeRepository."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from uuid import UUID

from construction_pm.project_core.domain import Project, Stage, StageStatus
from construction_pm.project_core.ports import IProjectRepository
from construction_pm.workforce_core.domain import Assignment, Brigade
from construction_pm.workforce_core.ports import IBrigadeRepository

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    budget_uah TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stages (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL CHECK (progress BETWEEN 0 AND 100)
);
CREATE TABLE IF NOT EXISTS brigades (
    id TEXT PRIMARY KEY,
    foreman TEXT NOT NULL,
    size INTEGER NOT NULL,
    contact TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS assignments (
    brigade_id TEXT NOT NULL REFERENCES brigades(id),
    stage_id TEXT NOT NULL REFERENCES stages(id),
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    PRIMARY KEY (brigade_id, stage_id, start)
);
"""


class Database:
    """Одне з'єднання SQLite, захищене блокуванням (вебсервер працює в кількох потоках)."""

    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock, self._conn:
            yield self._conn

    def ping(self) -> bool:
        """Перевірка доступності БД (для readiness-проби)."""
        with self.transaction() as c:
            return c.execute("SELECT 1").fetchone() == (1,)

    def close(self) -> None:
        self._conn.close()


class SqliteProjectRepository(IProjectRepository):
    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, project: Project) -> None:
        with self._db.transaction() as c:
            c.execute(
                "INSERT INTO projects(id, name, budget_uah) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name = excluded.name, budget_uah = excluded.budget_uah",
                (str(project.id), project.name, str(project.budget_uah)),
            )
            for pos, s in enumerate(project.stages):
                c.execute(
                    "INSERT INTO stages(id, project_id, position, title, status, progress) "
                    "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                    "title = excluded.title, status = excluded.status, progress = excluded.progress",
                    (str(s.id), str(project.id), pos, s.title, s.status.value, s.progress),
                )

    def get(self, project_id: UUID) -> Project | None:
        with self._db.transaction() as c:
            row = c.execute(
                "SELECT id, name, budget_uah FROM projects WHERE id = ?", (str(project_id),)
            ).fetchone()
            if row is None:
                return None
            stages = c.execute(
                "SELECT id, title, status, progress FROM stages WHERE project_id = ? ORDER BY position",
                (row[0],),
            ).fetchall()
        project = Project(name=row[1], budget_uah=Decimal(row[2]), id=UUID(row[0]))
        project.stages = [
            Stage(title=t, id=UUID(i), status=StageStatus(st), progress=p) for i, t, st, p in stages
        ]
        return project

    def find_by_stage(self, stage_id: UUID) -> Project | None:
        with self._db.transaction() as c:
            row = c.execute("SELECT project_id FROM stages WHERE id = ?", (str(stage_id),)).fetchone()
        return self.get(UUID(row[0])) if row else None


class SqliteBrigadeRepository(IBrigadeRepository):
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, brigade: Brigade) -> None:
        """Службовий метод для початкового наповнення (викликається з Composition Root)."""
        with self._db.transaction() as c:
            c.execute(
                "INSERT OR IGNORE INTO brigades(id, foreman, size, contact) VALUES (?, ?, ?, ?)",
                (str(brigade.id), brigade.foreman, brigade.size, brigade.contact),
            )

    def get(self, brigade_id: UUID) -> Brigade | None:
        with self._db.transaction() as c:
            row = c.execute(
                "SELECT id, foreman, size, contact FROM brigades WHERE id = ?", (str(brigade_id),)
            ).fetchone()
        return Brigade(id=UUID(row[0]), foreman=row[1], size=row[2], contact=row[3]) if row else None

    def save_assignment(self, assignment: Assignment) -> None:
        with self._db.transaction() as c:
            c.execute(
                "INSERT OR REPLACE INTO assignments(brigade_id, stage_id, start, end) VALUES (?, ?, ?, ?)",
                (
                    str(assignment.brigade_id),
                    str(assignment.stage_id),
                    assignment.start.isoformat(),
                    assignment.end.isoformat(),
                ),
            )

    def assignments_for(self, brigade_id: UUID) -> list[Assignment]:
        with self._db.transaction() as c:
            rows = c.execute(
                "SELECT brigade_id, stage_id, start, end FROM assignments WHERE brigade_id = ?",
                (str(brigade_id),),
            ).fetchall()
        return [
            Assignment(UUID(b), UUID(s), date.fromisoformat(st), date.fromisoformat(en))
            for b, s, st, en in rows
        ]
