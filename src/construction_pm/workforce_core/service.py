"""Реалізація IAssignmentService."""

from __future__ import annotations

import logging
from datetime import date
from uuid import UUID

from construction_pm.common.errors import NotFoundError
from construction_pm.project_core.ports import IProjectQuery
from construction_pm.workforce_core.domain import Assignment, BrigadeBusyError, StageClosedError
from construction_pm.workforce_core.ports import IAssignmentService, IBrigadeRepository, INotifier

log = logging.getLogger(__name__)


class AssignmentService(IAssignmentService):
    """Усі залежності — абстрактні контракти, передані через конструктор."""

    def __init__(self, brigades: IBrigadeRepository, projects: IProjectQuery, notifier: INotifier) -> None:
        self._brigades = brigades
        self._projects = projects
        self._notifier = notifier

    def assign_brigade(self, brigade_id: UUID, stage_id: UUID, start: date, end: date) -> Assignment:
        brigade = self._brigades.get(brigade_id)
        if brigade is None:
            raise NotFoundError(f"Бригаду {brigade_id} не знайдено")
        stage = self._projects.get_stage(stage_id)
        if stage is None:
            raise NotFoundError(f"Етап {stage_id} не знайдено")
        if not self._projects.is_stage_open(stage_id):
            raise StageClosedError(f"Етап «{stage.title}» уже завершено")

        new = Assignment(brigade_id=brigade_id, stage_id=stage_id, start=start, end=end)
        for existing in self._brigades.assignments_for(brigade_id):
            if existing == new:
                return existing  # ідемпотентність: повторне те саме призначення
            if existing.overlaps(new):
                raise BrigadeBusyError(
                    f"Бригада {brigade.foreman} зайнята з {existing.start} по {existing.end}"
                )
        self._brigades.save_assignment(new)

        result = self._notifier.notify(
            brigade.contact or brigade.foreman,
            f"Бригаду призначено на етап «{stage.title}» з {start:%d.%m.%Y} по {end:%d.%m.%Y}",
        )
        if not result.delivered:
            # Помилка доставки не скасовує призначення (NFR компонента Notifications).
            log.warning("Сповіщення не доставлено: %s", result.error)
        return new

    def brigade_schedule(self, brigade_id: UUID) -> list[Assignment]:
        if self._brigades.get(brigade_id) is None:
            raise NotFoundError(f"Бригаду {brigade_id} не знайдено")
        return sorted(self._brigades.assignments_for(brigade_id), key=lambda a: a.start)
