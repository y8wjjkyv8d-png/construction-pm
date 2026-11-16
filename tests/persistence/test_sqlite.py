"""Тести адаптера Persistence на SQLite у пам'яті (:memory:)."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from construction_pm.persistence.sqlite import Database, SqliteBrigadeRepository, SqliteProjectRepository
from construction_pm.project_core.domain import Project, StageStatus
from construction_pm.workforce_core.domain import Assignment, Brigade


@pytest.fixture
def db():
    database = Database(":memory:")
    yield database
    database.close()


@pytest.fixture
def projects(db):
    return SqliteProjectRepository(db)


@pytest.fixture
def brigades(db):
    return SqliteBrigadeRepository(db)


def test_project_round_trip_keeps_stages_order_and_state(projects):
    p = Project(name="ЖК «Південний»", budget_uah=Decimal("12500000.50"))
    p.add_stage("Фундамент").set_progress(100)
    p.add_stage("Каркас").set_progress(30)
    projects.save(p)

    loaded = projects.get(p.id)

    assert loaded == p
    assert loaded.budget_uah == Decimal("12500000.50")
    assert [s.status for s in loaded.stages] == [StageStatus.DONE, StageStatus.IN_PROGRESS]


def test_save_updates_existing_project(projects):
    p = Project(name="Об'єкт", budget_uah=Decimal("1"))
    projects.save(p)
    p.name, p.budget_uah = "Об'єкт 2", Decimal("2")
    p.add_stage("A")
    projects.save(p)

    loaded = projects.get(p.id)

    assert (loaded.name, loaded.budget_uah, len(loaded.stages)) == ("Об'єкт 2", Decimal("2"), 1)


def test_get_unknown_project_returns_none(projects):
    assert projects.get(uuid4()) is None


def test_find_by_stage(projects):
    p = Project(name="Об'єкт", budget_uah=Decimal("1"))
    stage = p.add_stage("A")
    projects.save(p)

    assert projects.find_by_stage(stage.id).id == p.id
    assert projects.find_by_stage(uuid4()) is None


def test_brigade_and_assignments_round_trip(projects, brigades):
    p = Project(name="Об'єкт", budget_uah=Decimal("1"))
    stage = p.add_stage("A")
    projects.save(p)
    b = Brigade(foreman="Петренко", size=5, contact="@p")
    brigades.add(b)
    brigades.add(b)  # повторне додавання ігнорується
    a = Assignment(b.id, stage.id, date(2026, 12, 1), date(2026, 12, 5))

    brigades.save_assignment(a)
    brigades.save_assignment(a)  # ідемпотентно

    assert brigades.get(b.id) == b
    assert brigades.assignments_for(b.id) == [a]
    assert brigades.assignments_for(uuid4()) == []
    assert brigades.get(uuid4()) is None
