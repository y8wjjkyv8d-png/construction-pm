"""Composition Root: єдине місце, де створюються конкретні класи і зв'язуються інтерфейси.

Запуск:
    construction-pm serve [--db construction.db] [--port 8000]
    construction-pm demo
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from uuid import UUID

from fastapi import FastAPI

from construction_pm.notifications.notifiers import ConsoleNotifier, TelegramNotifier
from construction_pm.persistence.sqlite import Database, SqliteBrigadeRepository, SqliteProjectRepository
from construction_pm.project_core.service import ProjectService
from construction_pm.web_api.app import create_app
from construction_pm.workforce_core.domain import Brigade
from construction_pm.workforce_core.ports import INotifier
from construction_pm.workforce_core.service import AssignmentService

# Фіксовані бригади для демонстрації (у реальній системі — довідник).
SEED_BRIGADES = [
    Brigade(id=UUID("11111111-1111-1111-1111-111111111111"), foreman="Петренко О.", size=6),
    Brigade(id=UUID("22222222-2222-2222-2222-222222222222"), foreman="Коваль І.", size=4),
]


@dataclass
class Container:
    app: FastAPI
    db: Database


def build(db_path: str = "construction.db", notifier: INotifier | None = None) -> Container:
    """Збирає систему: Persistence → ProjectCore → WorkforceCore → WebAPI."""
    db = Database(db_path)
    project_repo = SqliteProjectRepository(db)
    brigade_repo = SqliteBrigadeRepository(db)
    for b in SEED_BRIGADES:
        brigade_repo.add(b)

    if notifier is None:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        notifier = TelegramNotifier(token) if token else ConsoleNotifier()

    project_service = ProjectService(repository=project_repo)
    assignment_service = AssignmentService(brigades=brigade_repo, projects=project_service, notifier=notifier)
    return Container(app=create_app(project_service, assignment_service), db=db)


def run_demo() -> int:
    """Наскрізний сценарій через усі 5 компонентів (HTTP → домен → SQLite → сповіщення)."""
    from fastapi.testclient import TestClient

    container = build(":memory:")
    client = TestClient(container.app)

    def call(method: str, url: str, body: dict | None = None) -> dict:
        resp = client.request(method, url, json=body)
        print(f"\n> {method} {url}" + (f"  {json.dumps(body, ensure_ascii=False)}" if body else ""))
        print(f"< {resp.status_code} {json.dumps(resp.json(), ensure_ascii=False, indent=2)}")
        return resp.json()

    brigade = str(SEED_BRIGADES[0].id)
    project = call("POST", "/projects", {"name": "ЖК «Південний», секція 2", "budget_uah": "12500000.00"})
    foundation = call("POST", f"/projects/{project['id']}/stages", {"title": "Фундамент"})
    call("POST", f"/projects/{project['id']}/stages", {"title": "Каркас"})
    call("PATCH", f"/stages/{foundation['id']}/progress", {"progress": 40})
    call(
        "POST",
        "/assignments",
        {"brigade_id": brigade, "stage_id": foundation["id"], "start": "2026-11-20", "end": "2026-12-05"},
    )
    call(
        "POST",
        "/assignments",  # конфлікт: бригада вже зайнята в цей період
        {"brigade_id": brigade, "stage_id": foundation["id"], "start": "2026-12-01", "end": "2026-12-10"},
    )
    call("PATCH", f"/stages/{foundation['id']}/progress", {"progress": 150})  # помилка валідації
    call("GET", f"/brigades/{brigade}/schedule")
    call("GET", f"/projects/{project['id']}")
    container.db.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="construction-pm", description="ConstructionPM")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="запустити REST API")
    serve.add_argument("--db", default="construction.db")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    sub.add_parser("demo", help="виконати демонстраційний сценарій")
    args = parser.parse_args(argv)

    if args.command == "demo":
        return run_demo()

    import uvicorn

    uvicorn.run(build(args.db).app, host=args.host, port=args.port)
    return 0
