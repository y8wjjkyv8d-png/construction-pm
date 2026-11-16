"""Інтеграційні тести: усі компоненти разом через Composition Root на SQLite :memory:."""

import pytest
from fastapi.testclient import TestClient

from construction_pm.main import SEED_BRIGADES, build, main
from tests.fakes import RecordingNotifier

BRIGADE = str(SEED_BRIGADES[0].id)


@pytest.fixture
def notifier():
    return RecordingNotifier()


@pytest.fixture
def client(notifier):
    container = build(":memory:", notifier=notifier)
    yield TestClient(container.app)
    container.db.close()


def create_project_with_stage(client, title="Фундамент"):
    project = client.post("/projects", json={"name": "ЖК «Південний»", "budget_uah": "12500000.00"}).json()
    stage = client.post(f"/projects/{project['id']}/stages", json={"title": title}).json()
    return project, stage


def test_full_flow_from_http_to_db_and_notification(client, notifier):
    project, stage = create_project_with_stage(client)
    client.patch(f"/stages/{stage['id']}/progress", json={"progress": 40})

    resp = client.post(
        "/assignments",
        json={"brigade_id": BRIGADE, "stage_id": stage["id"], "start": "2026-11-20", "end": "2026-12-05"},
    )

    assert resp.status_code == 201
    assert notifier.sent and "Фундамент" in notifier.sent[0][1]
    stored = client.get(f"/projects/{project['id']}").json()
    assert stored["stages"][0]["progress"] == 40
    assert stored["budget_uah"] == "12500000.00"  # Decimal без втрат через SQLite
    assert client.get(f"/brigades/{BRIGADE}/schedule").json()[0]["stage_id"] == stage["id"]


def test_conflicting_assignment_returns_409(client):
    _, stage = create_project_with_stage(client)
    body = {"brigade_id": BRIGADE, "stage_id": stage["id"], "start": "2026-12-01", "end": "2026-12-10"}
    client.post("/assignments", json=body)

    resp = client.post("/assignments", json={**body, "start": "2026-12-05", "end": "2026-12-20"})

    assert resp.status_code == 409
    assert resp.json()["error"] == "brigade_busy"


def test_assignment_to_finished_stage_returns_409(client):
    _, stage = create_project_with_stage(client)
    client.patch(f"/stages/{stage['id']}/progress", json={"progress": 100})

    resp = client.post(
        "/assignments",
        json={"brigade_id": BRIGADE, "stage_id": stage["id"], "start": "2026-12-01", "end": "2026-12-02"},
    )

    assert resp.status_code == 409
    assert resp.json()["error"] == "stage_closed"


def test_domain_validation_reaches_client_as_422(client):
    project, _ = create_project_with_stage(client, "Каркас")

    resp = client.post(f"/projects/{project['id']}/stages", json={"title": "каркас"})

    assert resp.status_code == 422
    assert "уже існує" in resp.json()["message"]


def test_unknown_project_returns_404(client):
    resp = client.get("/projects/00000000-0000-0000-0000-000000000000")

    assert resp.status_code == 404


def test_cli_demo_runs_successfully(capsys):
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "< 201" in out and "< 409" in out and "[сповіщення" in out


def test_readiness_checks_real_database(client):
    assert client.get("/ready").json() == {"status": "ready"}


def test_telegram_notifier_is_selected_from_environment(monkeypatch):
    from construction_pm.notifications.notifiers import TelegramNotifier

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_API_BASE", "http://telegram-mock:8081/")
    captured = {}
    monkeypatch.setattr(
        "construction_pm.main.AssignmentService",
        lambda brigades, projects, notifier: captured.setdefault("n", notifier),
    )
    monkeypatch.setattr("construction_pm.main.create_app", lambda *a, **k: None)

    build(":memory:")

    assert isinstance(captured["n"], TelegramNotifier)
    assert captured["n"]._url == "http://telegram-mock:8081/botT/sendMessage"
