"""Контракти ProjectCore.

Provided: IProjectService (для WebAPI), IProjectQuery (для WorkforceCore).
Required: IProjectRepository (реалізує Persistence).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from construction_pm.project_core.domain import Project, Stage, StageStatus


@dataclass(frozen=True)
class StageView:
    """Подання етапу лише для читання — те, що бачать інші компоненти."""

    id: UUID
    project_id: UUID
    title: str
    status: StageStatus


class IProjectService(ABC):
    """Provided interface: керування проєктами та етапами."""

    @abstractmethod
    def create_project(self, name: str, budget_uah: Decimal) -> Project: ...

    @abstractmethod
    def add_stage(self, project_id: UUID, title: str) -> Stage: ...

    @abstractmethod
    def update_progress(self, stage_id: UUID, percent: int) -> Stage: ...

    @abstractmethod
    def get_project(self, project_id: UUID) -> Project: ...


class IProjectQuery(ABC):
    """Provided interface: вузький доступ лише для читання (для WorkforceCore)."""

    @abstractmethod
    def get_stage(self, stage_id: UUID) -> StageView | None: ...

    @abstractmethod
    def is_stage_open(self, stage_id: UUID) -> bool: ...


class IProjectRepository(ABC):
    """Required interface: збереження агрегата Project."""

    @abstractmethod
    def save(self, project: Project) -> None: ...

    @abstractmethod
    def get(self, project_id: UUID) -> Project | None: ...

    @abstractmethod
    def find_by_stage(self, stage_id: UUID) -> Project | None: ...
