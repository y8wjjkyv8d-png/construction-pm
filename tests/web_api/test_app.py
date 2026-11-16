"""Тести WebAPI в ізоляції: сервіси підмінені mock-об'єктами за контрактами."""

from datetime import date
from decimal import Decimal
from unittest.mock import create_autospec
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from construction_pm.common.errors import NotFoundError, ValidationError
from construction_pm.project_core.domain import Project, Stage
from construction_pm.project_core.ports import IProjectService
from construction_pm.web_api.app import create_app
from construction_pm.workforce_core.domain import Assignment, BrigadeBusyError
from construction_pm.workforce_core.ports import IAssignmentService


@pytest.fixture
def projects():
    return create_autospec(IProjectService, instance=True)


@pytest.fixture
def assignments():
    return create_autospec(IAssignmentService, instance=True)


@pytest.fixture
def client(projects, assignments):
    return TestClient(create_app(projects, assignments))


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_project_maps_dto_to_domain_call(client, projects):
    projects.create_project.return_value = Project(name="ЖК", budget_uah=Decimal("10.50"))

    resp = client.post("/projects", json={"name": "ЖК", "budget_uah": "10.50"})

    assert resp.status_code == 201
    assert resp.json()["budget_uah"] == "10.50"
    projects.create_project.assert_called_once_with("ЖК", Decimal("10.50"))


@pytest.mark.parametrize(
    "body",
    [
        {"name": "ЖК", "budget_uah": "-1"},
        {"name": "", "budget_uah": "1"},
        {"name": "ЖК"},
        {"name": "ЖК", "budget_uah": "1", "extra": True},
        {"name": "ЖК", "budget_uah": "1.999"},
    ],
)
def test_invalid_project_dto_is_rejected_before_domain(client, projects, body):
    resp = client.post("/projects", json=body)

    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"
    projects.create_project.assert_not_called()


def test_get_project_returns_progress_and_stages(client, projects):
    p = Project(name="ЖК", budget_uah=Decimal("1"))
    p.add_stage("Фундамент").set_progress(50)
    projects.get_project.return_value = p

    body = client.get(f"/projects/{p.id}").json()

    assert body["progress"] == 50
    assert body["stages"][0] == {
        "id": str(p.stages[0].id),
        "title": "Фундамент",
        "status": "in_progress",
        "progress": 50,
    }


@pytest.mark.parametrize(
    ("error", "code"),
    [(NotFoundError("нема"), 404), (ValidationError("погано"), 422), (BrigadeBusyError("зайнята"), 409)],
)
def test_domain_errors_are_mapped_to_http(client, projects, error, code):
    projects.get_project.side_effect = error

    resp = client.get(f"/projects/{uuid4()}")

    assert resp.status_code == code
    assert resp.json() == {"error": error.code, "message": error.message}


def test_add_stage_and_progress(client, projects):
    projects.add_stage.return_value = Stage(title="Каркас")
    pid = uuid4()

    assert client.post(f"/projects/{pid}/stages", json={"title": "Каркас"}).status_code == 201
    projects.add_stage.assert_called_once_with(pid, "Каркас")

    projects.update_progress.return_value = Stage(title="Каркас", progress=10)
    sid = uuid4()
    assert client.patch(f"/stages/{sid}/progress", json={"progress": 10}).status_code == 200
    projects.update_progress.assert_called_once_with(sid, 10)


@pytest.mark.parametrize("progress", [-1, 101, "abc"])
def test_invalid_progress_is_rejected(client, projects, progress):
    resp = client.patch(f"/stages/{uuid4()}/progress", json={"progress": progress})

    assert resp.status_code == 422
    projects.update_progress.assert_not_called()


def test_assign_and_schedule(client, assignments):
    b, s = uuid4(), uuid4()
    a = Assignment(b, s, date(2026, 12, 1), date(2026, 12, 5))
    assignments.assign_brigade.return_value = a
    assignments.brigade_schedule.return_value = [a]
    body = {"brigade_id": str(b), "stage_id": str(s), "start": "2026-12-01", "end": "2026-12-05"}

    assert client.post("/assignments", json=body).json() == body
    assignments.assign_brigade.assert_called_once_with(b, s, date(2026, 12, 1), date(2026, 12, 5))
    assert client.get(f"/brigades/{b}/schedule").json() == [body]


def test_invalid_uuid_in_path_is_rejected(client):
    resp = client.get("/projects/not-a-uuid")

    assert resp.status_code == 422


def test_d5_validation_message_names_field_without_location_prefix(client):
    """Регресійний тест D5: у повідомленні має бути «project_id: …», а не «path.project_id: …»."""
    resp = client.get("/projects/not-a-uuid")

    assert resp.json()["message"].startswith("project_id: ")
