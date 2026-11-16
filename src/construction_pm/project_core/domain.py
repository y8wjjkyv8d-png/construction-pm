"""Доменні сутності ProjectCore. Не залежать від HTTP, БД чи DTO."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from construction_pm.common.errors import NotFoundError, ValidationError


class StageStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    DONE = "done"


@dataclass
class Stage:
    title: str
    id: UUID = field(default_factory=uuid4)
    status: StageStatus = StageStatus.PLANNED
    progress: int = 0

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        if not self.title:
            raise ValidationError("Назва етапу не може бути порожньою")
        if len(self.title) > 120:
            raise ValidationError("Назва етапу довша за 120 символів")

    def set_progress(self, percent: int) -> None:
        """Оновлює прогрес і статус: 0 → planned, 1..99 → in_progress, 100 → done."""
        if not 0 <= percent <= 100:
            raise ValidationError(f"Прогрес має бути в межах 0..100, отримано {percent}")
        if self.status is StageStatus.DONE and percent < 100:
            raise ValidationError("Завершений етап не можна повернути в роботу")
        self.progress = percent
        if percent == 100:
            self.status = StageStatus.DONE
        elif percent > 0:
            self.status = StageStatus.IN_PROGRESS
        else:
            self.status = StageStatus.PLANNED

    @property
    def is_open(self) -> bool:
        return self.status is not StageStatus.DONE


@dataclass
class Project:
    name: str
    budget_uah: Decimal
    id: UUID = field(default_factory=uuid4)
    stages: list[Stage] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError("Назва проєкту не може бути порожньою")
        if self.budget_uah < 0:
            raise ValidationError("Бюджет не може бути від'ємним")

    def add_stage(self, title: str) -> Stage:
        if any(s.title.lower() == title.strip().lower() for s in self.stages):
            raise ValidationError(f"Етап «{title.strip()}» уже існує в проєкті")
        stage = Stage(title=title)
        self.stages.append(stage)
        return stage

    def stage(self, stage_id: UUID) -> Stage:
        for s in self.stages:
            if s.id == stage_id:
                return s
        raise NotFoundError(f"Етап {stage_id} не знайдено")

    @property
    def progress(self) -> int:
        """Середній прогрес проєкту за етапами, округлений «до більшого» з 0,5 (0, якщо етапів немає)."""
        if not self.stages:
            return 0
        total, n = sum(s.progress for s in self.stages), len(self.stages)
        return (2 * total + n) // (2 * n)  # ціле округлення half-up без float
