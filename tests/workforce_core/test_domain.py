from datetime import date
from uuid import uuid4

import pytest

from construction_pm.common.errors import ValidationError
from construction_pm.workforce_core.domain import Assignment, Brigade

B, S = uuid4(), uuid4()


def a(start: str, end: str) -> Assignment:
    return Assignment(B, S, date.fromisoformat(start), date.fromisoformat(end))


@pytest.mark.parametrize(("foreman", "size"), [("", 3), ("   ", 3), ("Петренко", 0), ("Петренко", -2)])
def test_invalid_brigade_is_rejected(foreman, size):
    with pytest.raises(ValidationError):
        Brigade(foreman=foreman, size=size)


def test_end_before_start_is_rejected():
    with pytest.raises(ValidationError):
        a("2026-12-10", "2026-12-01")


def test_one_day_assignment_is_allowed():
    assert a("2026-12-01", "2026-12-01").start == date(2026, 12, 1)


@pytest.mark.parametrize(
    ("other", "expected"),
    [
        (("2026-12-05", "2026-12-15"), True),  # часткове перекриття
        (("2026-11-01", "2026-12-01"), True),  # дотик межі включно
        (("2026-12-02", "2026-12-03"), True),  # вкладений період
        (("2026-12-11", "2026-12-20"), False),  # одразу після
        (("2026-11-01", "2026-11-30"), False),  # одразу перед
    ],
)
def test_overlaps(other, expected):
    base = a("2026-12-01", "2026-12-10")

    assert base.overlaps(a(*other)) is expected
    assert a(*other).overlaps(base) is expected  # симетричність
