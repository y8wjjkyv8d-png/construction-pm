from decimal import Decimal
from uuid import uuid4

import pytest

from construction_pm.common.errors import NotFoundError, ValidationError
from construction_pm.project_core.domain import Project, Stage, StageStatus


def make_project(**kw) -> Project:
    return Project(name=kw.get("name", "ЖК «Південний»"), budget_uah=kw.get("budget", Decimal("1000")))


class TestStage:
    def test_new_stage_is_planned_with_zero_progress(self):
        stage = Stage(title="Фундамент")

        assert stage.status is StageStatus.PLANNED
        assert stage.progress == 0
        assert stage.is_open

    def test_title_is_trimmed(self):
        assert Stage(title="  Каркас  ").title == "Каркас"

    @pytest.mark.parametrize("title", ["", "   ", "x" * 121])
    def test_invalid_title_is_rejected(self, title):
        with pytest.raises(ValidationError):
            Stage(title=title)

    @pytest.mark.parametrize(
        ("percent", "status"),
        [
            (0, StageStatus.PLANNED),
            (1, StageStatus.IN_PROGRESS),
            (99, StageStatus.IN_PROGRESS),
            (100, StageStatus.DONE),
        ],
    )
    def test_progress_sets_status(self, percent, status):
        stage = Stage(title="Покрівля")

        stage.set_progress(percent)

        assert stage.progress == percent
        assert stage.status is status

    @pytest.mark.parametrize("percent", [-1, 101, 150])
    def test_progress_out_of_range_is_rejected(self, percent):
        stage = Stage(title="Покрівля")

        with pytest.raises(ValidationError):
            stage.set_progress(percent)
        assert stage.progress == 0

    def test_done_stage_cannot_be_reopened(self):
        stage = Stage(title="Фундамент")
        stage.set_progress(100)

        with pytest.raises(ValidationError):
            stage.set_progress(50)
        assert stage.status is StageStatus.DONE
        assert not stage.is_open


class TestProject:
    def test_name_is_required(self):
        with pytest.raises(ValidationError):
            make_project(name="   ")

    def test_negative_budget_is_rejected(self):
        with pytest.raises(ValidationError):
            make_project(budget=Decimal("-0.01"))

    def test_zero_budget_is_allowed(self):
        assert make_project(budget=Decimal("0")).budget_uah == 0

    def test_add_stage_appends_in_order(self):
        p = make_project()

        p.add_stage("Фундамент")
        p.add_stage("Каркас")

        assert [s.title for s in p.stages] == ["Фундамент", "Каркас"]

    def test_duplicate_stage_title_is_rejected_case_insensitive(self):
        p = make_project()
        p.add_stage("Фундамент")

        with pytest.raises(ValidationError):
            p.add_stage("  фундамент ")

    def test_stage_lookup_unknown_raises_not_found(self):
        with pytest.raises(NotFoundError):
            make_project().stage(uuid4())

    def test_progress_of_empty_project_is_zero(self):
        assert make_project().progress == 0

    def test_progress_is_average_of_stages(self):
        p = make_project()
        p.add_stage("A").set_progress(40)
        p.add_stage("B")

        assert p.progress == 20
