"""DTO (JSON) та перетворення DTO ↔ доменні сутності. Існують лише в адаптері WebAPI."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from construction_pm.project_core.domain import Project, Stage
from construction_pm.workforce_core.domain import Assignment


class ProjectCreateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    budget_uah: Decimal = Field(ge=0, max_digits=15, decimal_places=2)


class StageCreateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)


class ProgressDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    progress: int = Field(ge=0, le=100)


class StageDTO(BaseModel):
    id: UUID
    title: str
    status: str
    progress: int


class ProjectDTO(BaseModel):
    id: UUID
    name: str
    budget_uah: Decimal
    progress: int
    stages: list[StageDTO]


class AssignmentDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brigade_id: UUID
    stage_id: UUID
    start: date
    end: date


class ErrorDTO(BaseModel):
    error: str
    message: str


def stage_to_dto(s: Stage) -> StageDTO:
    return StageDTO(id=s.id, title=s.title, status=s.status.value, progress=s.progress)


def project_to_dto(p: Project) -> ProjectDTO:
    return ProjectDTO(
        id=p.id,
        name=p.name,
        budget_uah=p.budget_uah,
        progress=p.progress,
        stages=[stage_to_dto(s) for s in p.stages],
    )


def assignment_to_dto(a: Assignment) -> AssignmentDTO:
    return AssignmentDTO(brigade_id=a.brigade_id, stage_id=a.stage_id, start=a.start, end=a.end)
