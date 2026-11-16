"""Контракти WorkforceCore.

Provided: IAssignmentService (для WebAPI).
Required: IBrigadeRepository (Persistence), INotifier (Notifications),
          IProjectQuery (ProjectCore — оголошено в project_core.ports).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from construction_pm.workforce_core.domain import Assignment, Brigade


@dataclass(frozen=True)
class DeliveryResult:
    delivered: bool
    error: str | None = None


class IAssignmentService(ABC):
    """Provided interface: призначення бригад на етапи."""

    @abstractmethod
    def assign_brigade(self, brigade_id: UUID, stage_id: UUID, start: date, end: date) -> Assignment: ...

    @abstractmethod
    def brigade_schedule(self, brigade_id: UUID) -> list[Assignment]: ...


class IBrigadeRepository(ABC):
    """Required interface: бригади та їх призначення."""

    @abstractmethod
    def get(self, brigade_id: UUID) -> Brigade | None: ...

    @abstractmethod
    def save_assignment(self, assignment: Assignment) -> None: ...

    @abstractmethod
    def assignments_for(self, brigade_id: UUID) -> list[Assignment]: ...


class INotifier(ABC):
    """Required interface: доставка повідомлення бригадиру."""

    @abstractmethod
    def notify(self, recipient: str, text: str) -> DeliveryResult: ...
