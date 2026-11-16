from decimal import Decimal
from unittest.mock import create_autospec
from uuid import uuid4

import pytest

from construction_pm.common.errors import NotFoundError, ValidationError
from construction_pm.project_core.domain import StageStatus
from construction_pm.project_core.ports import IProjectRepository
from construction_pm.project_core.service import ProjectService
from tests.fakes import InMemoryProjectRepository


@pytest.fixture
def repo():
    return InMemoryProjectRepository()


@pytest.fixture
def service(repo):
    return ProjectService(repository=repo)


def test_create_project_persists_it(service, repo):
    project = service.create_project("ЖК «Південний»", Decimal("12500000"))

    assert repo.items[project.id].name == "ЖК «Південний»"


def test_create_project_invalid_budget_is_not_saved():
    # Mock: перевіряємо, що в інтерфейс споживання нічого не передано
    repo = create_autospec(IProjectRepository, instance=True)
    service = ProjectService(repository=repo)

    with pytest.raises(ValidationError):
        service.create_project("Тест", Decimal("-1"))
    repo.save.assert_not_called()


def test_add_stage_saves_project_with_new_stage(service, repo):
    p = service.create_project("Об'єкт", Decimal("10"))

    stage = service.add_stage(p.id, "Фундамент")

    assert [s.id for s in repo.items[p.id].stages] == [stage.id]


def test_add_stage_to_unknown_project_raises_not_found(service):
    with pytest.raises(NotFoundError):
        service.add_stage(uuid4(), "Фундамент")


def test_update_progress_is_saved(service, repo):
    p = service.create_project("Об'єкт", Decimal("10"))
    stage = service.add_stage(p.id, "Фундамент")

    service.update_progress(stage.id, 60)

    saved = repo.items[p.id].stage(stage.id)
    assert (saved.progress, saved.status) == (60, StageStatus.IN_PROGRESS)


def test_update_progress_calls_repository_with_updated_project():
    repo = create_autospec(IProjectRepository, instance=True)
    real = InMemoryProjectRepository()
    service = ProjectService(repository=real)
    p = service.create_project("Об'єкт", Decimal("10"))
    stage = service.add_stage(p.id, "Фундамент")
    repo.find_by_stage.return_value = real.get(p.id)
    service = ProjectService(repository=repo)

    service.update_progress(stage.id, 100)

    repo.find_by_stage.assert_called_once_with(stage.id)
    repo.save.assert_called_once()
    (saved,), _ = repo.save.call_args
    assert saved.stage(stage.id).status is StageStatus.DONE


def test_update_progress_of_unknown_stage_raises_not_found(service):
    with pytest.raises(NotFoundError):
        service.update_progress(uuid4(), 10)


def test_get_project_unknown_raises_not_found(service):
    with pytest.raises(NotFoundError):
        service.get_project(uuid4())


def test_get_stage_returns_read_only_view(service):
    p = service.create_project("Об'єкт", Decimal("10"))
    stage = service.add_stage(p.id, "Каркас")

    view = service.get_stage(stage.id)

    assert (view.id, view.project_id, view.title, view.status) == (
        stage.id,
        p.id,
        "Каркас",
        StageStatus.PLANNED,
    )
    with pytest.raises(AttributeError):
        view.title = "інше"


def test_get_stage_unknown_returns_none(service):
    assert service.get_stage(uuid4()) is None


def test_is_stage_open(service):
    p = service.create_project("Об'єкт", Decimal("10"))
    open_stage = service.add_stage(p.id, "A")
    done_stage = service.add_stage(p.id, "B")
    service.update_progress(done_stage.id, 100)

    assert service.is_stage_open(open_stage.id) is True
    assert service.is_stage_open(done_stage.id) is False
    assert service.is_stage_open(uuid4()) is False
