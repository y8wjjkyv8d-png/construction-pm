"""Тестові двійники (Fakes) для інтерфейсів споживання."""

from __future__ import annotations

import copy
from uuid import UUID

from construction_pm.project_core.domain import Project
from construction_pm.project_core.ports import IProjectRepository
from construction_pm.workforce_core.domain import Assignment, Brigade
from construction_pm.workforce_core.ports import DeliveryResult, IBrigadeRepository, INotifier


class InMemoryProjectRepository(IProjectRepository):
    """Зберігає глибокі копії, щоб тест бачив лише явно збережений стан."""

    def __init__(self) -> None:
        self.items: dict[UUID, Project] = {}
        self.saves = 0

    def save(self, project: Project) -> None:
        self.saves += 1
        self.items[project.id] = copy.deepcopy(project)

    def get(self, project_id: UUID) -> Project | None:
        p = self.items.get(project_id)
        return copy.deepcopy(p) if p else None

    def find_by_stage(self, stage_id: UUID) -> Project | None:
        for p in self.items.values():
            if any(s.id == stage_id for s in p.stages):
                return copy.deepcopy(p)
        return None


class InMemoryBrigadeRepository(IBrigadeRepository):
    def __init__(self, *brigades: Brigade) -> None:
        self.brigades = {b.id: b for b in brigades}
        self.assignments: list[Assignment] = []

    def get(self, brigade_id: UUID) -> Brigade | None:
        return self.brigades.get(brigade_id)

    def save_assignment(self, assignment: Assignment) -> None:
        self.assignments.append(assignment)

    def assignments_for(self, brigade_id: UUID) -> list[Assignment]:
        return [a for a in self.assignments if a.brigade_id == brigade_id]


class RecordingNotifier(INotifier):
    def __init__(self, result: DeliveryResult | None = None) -> None:
        self.sent: list[tuple[str, str]] = []
        self.result = result or DeliveryResult(delivered=True)

    def notify(self, recipient: str, text: str) -> DeliveryResult:
        self.sent.append((recipient, text))
        return self.result
