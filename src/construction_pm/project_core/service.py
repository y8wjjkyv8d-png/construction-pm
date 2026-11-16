"""Реалізація інтерфейсів ProjectCore."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from construction_pm.common.errors import NotFoundError
from construction_pm.project_core.domain import Project, Stage
from construction_pm.project_core.ports import (
    IProjectQuery,
    IProjectRepository,
    IProjectService,
    StageView,
)


class ProjectService(IProjectService, IProjectQuery):
    """Сервіс проєктів. Репозиторій передається ззовні (Constructor Injection)."""

    def __init__(self, repository: IProjectRepository) -> None:
        self._repo = repository

    # --- IProjectService -------------------------------------------------
    def create_project(self, name: str, budget_uah: Decimal) -> Project:
        project = Project(name=name, budget_uah=budget_uah)
        self._repo.save(project)
        return project

    def add_stage(self, project_id: UUID, title: str) -> Stage:
        project = self.get_project(project_id)
        stage = project.add_stage(title)
        self._repo.save(project)
        return stage

    def update_progress(self, stage_id: UUID, percent: int) -> Stage:
        project = self._repo.find_by_stage(stage_id)
        if project is None:
            raise NotFoundError(f"Етап {stage_id} не знайдено")
        stage = project.stage(stage_id)
        stage.set_progress(percent)
        self._repo.save(project)
        return stage

    def get_project(self, project_id: UUID) -> Project:
        project = self._repo.get(project_id)
        if project is None:
            raise NotFoundError(f"Проєкт {project_id} не знайдено")
        return project

    # --- IProjectQuery ---------------------------------------------------
    def get_stage(self, stage_id: UUID) -> StageView | None:
        project = self._repo.find_by_stage(stage_id)
        if project is None:
            return None
        stage = project.stage(stage_id)
        return StageView(id=stage.id, project_id=project.id, title=stage.title, status=stage.status)

    def is_stage_open(self, stage_id: UUID) -> bool:
        view = self.get_stage(stage_id)
        return view is not None and view.status.value != "done"
