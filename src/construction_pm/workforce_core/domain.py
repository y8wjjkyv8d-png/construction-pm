"""Доменні сутності WorkforceCore."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID, uuid4

from construction_pm.common.errors import ConflictError, ValidationError


class BrigadeBusyError(ConflictError):
    """Бригада вже зайнята в обраний період."""

    code = "brigade_busy"


class StageClosedError(ConflictError):
    """Етап завершено — призначати на нього бригаду не можна."""

    code = "stage_closed"


@dataclass(frozen=True)
class Brigade:
    foreman: str
    size: int
    contact: str = ""
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.foreman.strip():
            raise ValidationError("Ім'я бригадира не може бути порожнім")
        if self.size < 1:
            raise ValidationError("У бригаді має бути щонайменше 1 працівник")


@dataclass(frozen=True)
class Assignment:
    brigade_id: UUID
    stage_id: UUID
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValidationError("Дата завершення раніша за дату початку")

    def overlaps(self, other: Assignment) -> bool:
        """Чи перетинаються періоди (межі включно)."""
        return self.start <= other.end and other.start <= self.end
