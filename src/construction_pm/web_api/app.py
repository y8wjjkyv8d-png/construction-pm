"""REST-ендпоінти IConstructionApi. Сервіси передаються ззовні (create_app — фабрика)."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from construction_pm.common.errors import ConflictError, DomainError, NotFoundError, ValidationError
from construction_pm.project_core.ports import IProjectService
from construction_pm.web_api.dto import (
    AssignmentDTO,
    ProgressDTO,
    ProjectCreateDTO,
    ProjectDTO,
    StageCreateDTO,
    StageDTO,
    assignment_to_dto,
    project_to_dto,
    stage_to_dto,
)
from construction_pm.workforce_core.ports import IAssignmentService

HTTP_BY_ERROR: list[tuple[type[DomainError], int]] = [
    (NotFoundError, status.HTTP_404_NOT_FOUND),
    (ConflictError, status.HTTP_409_CONFLICT),
    (ValidationError, status.HTTP_422_UNPROCESSABLE_CONTENT),
]


def create_app(
    projects: IProjectService,
    assignments: IAssignmentService,
    readiness: Callable[[], bool] = lambda: True,
) -> FastAPI:
    """readiness — перевірка готовності залежностей (передається з Composition Root)."""
    app = FastAPI(title="ConstructionPM API", version="1.0.0")

    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        code = next((c for t, c in HTTP_BY_ERROR if isinstance(exc, t)), status.HTTP_400_BAD_REQUEST)
        return JSONResponse(status_code=code, content={"error": exc.code, "message": exc.message})

    @app.exception_handler(RequestValidationError)
    async def dto_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0]
        loc = list(first["loc"])
        if loc and loc[0] in ("body", "path", "query", "header", "cookie"):
            loc = loc[1:]
        field = ".".join(str(x) for x in loc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": "validation_error", "message": f"{field}: {first['msg']}"},
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Liveness: процес живий і обробляє запити."""
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> JSONResponse:
        """Readiness: залежності (база даних) доступні — можна приймати трафік."""
        try:
            ok = readiness()
        except Exception:  # noqa: BLE001
            ok = False
        code = status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=code, content={"status": "ready" if ok else "not_ready"})

    @app.post("/projects", status_code=status.HTTP_201_CREATED, response_model=ProjectDTO)
    def create_project(body: ProjectCreateDTO) -> ProjectDTO:
        return project_to_dto(projects.create_project(body.name, body.budget_uah))

    @app.get("/projects/{project_id}", response_model=ProjectDTO)
    def get_project(project_id: UUID) -> ProjectDTO:
        return project_to_dto(projects.get_project(project_id))

    @app.post("/projects/{project_id}/stages", status_code=status.HTTP_201_CREATED, response_model=StageDTO)
    def add_stage(project_id: UUID, body: StageCreateDTO) -> StageDTO:
        return stage_to_dto(projects.add_stage(project_id, body.title))

    @app.patch("/stages/{stage_id}/progress", response_model=StageDTO)
    def update_progress(stage_id: UUID, body: ProgressDTO) -> StageDTO:
        return stage_to_dto(projects.update_progress(stage_id, body.progress))

    @app.post("/assignments", status_code=status.HTTP_201_CREATED, response_model=AssignmentDTO)
    def assign(body: AssignmentDTO) -> AssignmentDTO:
        a = assignments.assign_brigade(body.brigade_id, body.stage_id, body.start, body.end)
        return assignment_to_dto(a)

    @app.get("/brigades/{brigade_id}/schedule", response_model=list[AssignmentDTO])
    def schedule(brigade_id: UUID) -> list[AssignmentDTO]:
        return [assignment_to_dto(a) for a in assignments.brigade_schedule(brigade_id)]

    return app
