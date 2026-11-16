from datetime import date
from unittest.mock import create_autospec
from uuid import uuid4

import pytest

from construction_pm.common.errors import NotFoundError
from construction_pm.project_core.domain import StageStatus
from construction_pm.project_core.ports import IProjectQuery, StageView
from construction_pm.workforce_core.domain import Brigade, BrigadeBusyError, StageClosedError
from construction_pm.workforce_core.ports import DeliveryResult
from construction_pm.workforce_core.service import AssignmentService
from tests.fakes import InMemoryBrigadeRepository, RecordingNotifier

D1, D10, D15, D20 = date(2026, 12, 1), date(2026, 12, 10), date(2026, 12, 15), date(2026, 12, 20)


@pytest.fixture
def brigade():
    return Brigade(foreman="Петренко О.", size=6, contact="@petrenko")


@pytest.fixture
def stage_id():
    return uuid4()


@pytest.fixture
def projects(stage_id):
    """Stub для IProjectQuery: етап існує і відкритий."""
    stub = create_autospec(IProjectQuery, instance=True)
    stub.get_stage.side_effect = lambda sid: (
        StageView(id=sid, project_id=uuid4(), title="Фундамент", status=StageStatus.IN_PROGRESS)
        if sid == stage_id
        else None
    )
    stub.is_stage_open.return_value = True
    return stub


@pytest.fixture
def brigades(brigade):
    return InMemoryBrigadeRepository(brigade)


@pytest.fixture
def notifier():
    return RecordingNotifier()


@pytest.fixture
def service(brigades, projects, notifier):
    return AssignmentService(brigades=brigades, projects=projects, notifier=notifier)


def test_assign_saves_and_notifies_foreman(service, brigades, notifier, brigade, stage_id):
    result = service.assign_brigade(brigade.id, stage_id, D1, D10)

    assert brigades.assignments == [result]
    assert len(notifier.sent) == 1
    recipient, text = notifier.sent[0]
    assert recipient == "@petrenko"
    assert "Фундамент" in text and "01.12.2026" in text and "10.12.2026" in text


def test_notification_falls_back_to_foreman_name_without_contact(projects, notifier, stage_id):
    b = Brigade(foreman="Коваль І.", size=4)
    service = AssignmentService(InMemoryBrigadeRepository(b), projects, notifier)

    service.assign_brigade(b.id, stage_id, D1, D10)

    assert notifier.sent[0][0] == "Коваль І."


def test_overlapping_assignment_is_rejected(service, brigades, notifier, brigade, stage_id):
    service.assign_brigade(brigade.id, stage_id, D1, D10)

    with pytest.raises(BrigadeBusyError):
        service.assign_brigade(brigade.id, stage_id, D10, D20)
    assert len(brigades.assignments) == 1
    assert len(notifier.sent) == 1


def test_same_assignment_twice_is_idempotent(service, brigades, notifier, brigade, stage_id):
    first = service.assign_brigade(brigade.id, stage_id, D1, D10)

    second = service.assign_brigade(brigade.id, stage_id, D1, D10)

    assert second == first
    assert len(brigades.assignments) == 1
    assert len(notifier.sent) == 1


def test_non_overlapping_assignments_are_allowed(service, brigade, stage_id):
    service.assign_brigade(brigade.id, stage_id, D15, D20)
    service.assign_brigade(brigade.id, stage_id, D1, D10)

    schedule = service.brigade_schedule(brigade.id)

    assert [a.start for a in schedule] == [D1, D15]  # відсортовано за датою


def test_unknown_brigade_raises_not_found(service, stage_id):
    with pytest.raises(NotFoundError):
        service.assign_brigade(uuid4(), stage_id, D1, D10)


def test_unknown_stage_raises_not_found(service, brigade):
    with pytest.raises(NotFoundError):
        service.assign_brigade(brigade.id, uuid4(), D1, D10)


def test_closed_stage_is_rejected(service, projects, brigades, notifier, brigade, stage_id):
    projects.is_stage_open.return_value = False

    with pytest.raises(StageClosedError):
        service.assign_brigade(brigade.id, stage_id, D1, D10)
    projects.is_stage_open.assert_called_once_with(stage_id)
    assert brigades.assignments == [] and notifier.sent == []


def test_failed_delivery_does_not_cancel_assignment(brigades, projects, brigade, stage_id, caplog):
    notifier = RecordingNotifier(DeliveryResult(delivered=False, error="timeout"))
    service = AssignmentService(brigades, projects, notifier)

    service.assign_brigade(brigade.id, stage_id, D1, D10)

    assert len(brigades.assignments) == 1
    assert "timeout" in caplog.text


def test_schedule_of_unknown_brigade_raises_not_found(service):
    with pytest.raises(NotFoundError):
        service.brigade_schedule(uuid4())
