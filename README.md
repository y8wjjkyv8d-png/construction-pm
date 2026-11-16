# ConstructionPM

Система управління будівельними проєктами: облік об’єктів, етапів робіт і їх прогресу, бригад та призначень бригад на етапи.

Навчальний проєкт з дисципліни «Технології програмування» (ЗНУ, магістратура F3 «Комп’ютерні науки», заочна форма). Автор: Клименко Д. С., гр. 7.F3.26-з.

| Етап | Зміст | Де шукати |
|---|---|---|
| ПР1 | Архітектурна модель: діаграма компонентів UML 2.5 | [`docs/architecture/`](docs/architecture/README.md) |
| ПР2 | Програмна реалізація компонентів | `src/construction_pm/` |
| ПР3 | Автоматизоване тестування | `tests/`, `docs/testing/` |
| ПР4 | Контейнеризація та оркестрація | `deploy/`, `docs/deployment/` |

## Технології

- Python ≥ 3.11
- FastAPI (REST), Pydantic (DTO та валідація), Uvicorn (вебсервер)
- SQLite (стандартний модуль `sqlite3`)
- Збірка: `pyproject.toml` (PEP 621, setuptools) + `python -m build`; версії залежностей зафіксовані
- Лінтер і форматер: Ruff
- CI: GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) — лінтер, перевірка форматування, збірка і демо-сценарій на кожен push і Pull Request

## Структура коду

```text
src/construction_pm/
├── common/            спільне ядро: типізовані доменні помилки
├── web_api/           компонент WebAPI          (вхідний адаптер, FastAPI)
├── project_core/      компонент ProjectCore     (домен)
├── workforce_core/    компонент WorkforceCore   (домен)
├── persistence/       компонент Persistence     (вихідний адаптер, SQLite)
├── notifications/     компонент Notifications   (вихідний адаптер)
└── main.py            Composition Root + CLI
```

Кожен доменний компонент має три модулі:
- `domain.py` — сутності та бізнес-правила;
- `ports.py` — абстрактні контракти (ABC), тобто інтерфейси надання і споживання;
- `service.py` — реалізація інтерфейсів надання.

Адаптери реалізують інтерфейси, оголошені в `ports.py` доменних компонентів.

## Таблиця трасованості: модель (ПР1) → код

| Елемент діаграми | Тип | Код |
|---|---|---|
| Компонент **WebAPI** | component | `web_api/app.py` (`create_app`), `web_api/dto.py` |
| Компонент **ProjectCore** | component | `project_core/domain.py` (`Project`, `Stage`), `project_core/service.py` (`ProjectService`) |
| Компонент **WorkforceCore** | component | `workforce_core/domain.py` (`Brigade`, `Assignment`), `workforce_core/service.py` (`AssignmentService`) |
| Компонент **Persistence** | component | `persistence/sqlite.py` (`Database`, `SqliteProjectRepository`, `SqliteBrigadeRepository`) |
| Компонент **Notifications** | component | `notifications/notifiers.py` (`ConsoleNotifier`, `TelegramNotifier`) |
| `IConstructionApi` | provided (порт підсистеми) | REST-ендпоінти в `web_api/app.py` |
| `IProjectService` | provided ProjectCore / required WebAPI | ABC `project_core/ports.py::IProjectService` → `ProjectService` |
| `IProjectQuery` | provided ProjectCore / required WorkforceCore | ABC `project_core/ports.py::IProjectQuery` → `ProjectService` |
| `IAssignmentService` | provided WorkforceCore / required WebAPI | ABC `workforce_core/ports.py::IAssignmentService` → `AssignmentService` |
| `IProjectRepository` | required ProjectCore / provided Persistence | ABC `project_core/ports.py::IProjectRepository` → `SqliteProjectRepository` |
| `IBrigadeRepository` | required WorkforceCore / provided Persistence | ABC `workforce_core/ports.py::IBrigadeRepository` → `SqliteBrigadeRepository` |
| `INotifier` | required WorkforceCore / provided Notifications | ABC `workforce_core/ports.py::INotifier` → `ConsoleNotifier`, `TelegramNotifier` |
| Delegation-конектор, assembly-конектори | зв’язування | `main.py::build()` (Composition Root) |
| «manifest» `construction_pm` (wheel) | artifact | `python -m build` → `dist/construction_pm-1.0.0-py3-none-any.whl` |
| «manifest» `construction.db` | artifact | файл SQLite, створюється `Database` |
| «manifest» `construction-pm:1.0` | artifact | OCI-образ — ПР4 |

## Принципи реалізації

- **Інтерфейси — абстрактні типи.** Усі контракти оголошено як `abc.ABC` з `@abstractmethod`. Компоненти залежать лише від них: наприклад, `AssignmentService` отримує `IBrigadeRepository`, `IProjectQuery` та `INotifier`.
- **Dependency Injection через конструктор.** Конкретні класи створюються тільки в Composition Root `main.py::build()`. Усередині компонентів немає жодного `ConcreteService()`.
- **DTO окремо від домену.** Pydantic-моделі `web_api/dto.py` живуть лише в адаптері. Домен працює з власними dataclass-сутностями, перетворення виконують функції `*_to_dto`.
- **Валідація на межах.**
  - На вході WebAPI: Pydantic-обмеження (`budget_uah ≥ 0`, `0 ≤ progress ≤ 100`, заборона зайвих полів).
  - У домені: інваріанти в `__post_init__` та методах.
- **Типізовані помилки.** `common/errors.py`: `ValidationError` → 422, `NotFoundError` → 404, `ConflictError` (`BrigadeBusyError`, `StageClosedError`) → 409. Помилки повертаються як JSON `{"error", "message"}`, процес не падає.

## Збирання та запуск

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # встановлення із зафіксованими залежностями

python -m build                  # збірка артефакту однією командою → dist/*.whl
ruff check . && ruff format --check .

construction-pm demo             # наскрізний демонстраційний сценарій
construction-pm serve --port 8000 --db construction.db   # REST API, документація: http://127.0.0.1:8000/docs
```

Сповіщення за замовчуванням виводяться в консоль. Щоб надсилати їх у Telegram, задайте змінну середовища `TELEGRAM_BOT_TOKEN`; тоді Composition Root підставить `TelegramNotifier`.

## Тестування

```bash
pytest --cov --cov-report=term --cov-report=html   # 91 тест, покриття 99 % (домен — 100 %)
```

Unit-тести кожного компонента з тестовими двійниками, інтеграційні тести через Composition Root, регресійні тести виправлених дефектів. Подробиці, таблиця дефектів і метрики: [`docs/testing/QA_REPORT.md`](docs/testing/QA_REPORT.md).

## Демонстраційний сценарій (вхід → вихід)

`construction-pm demo` проходить через усі 5 компонентів: HTTP (WebAPI) → ProjectCore → WorkforceCore → SQLite (Persistence) → сповіщення (Notifications). Скорочений вивід:

```text
> POST /projects  {"name": "ЖК «Південний», секція 2", "budget_uah": "12500000.00"}
< 201 {"id": "…", "name": "ЖК «Південний», секція 2", "budget_uah": "12500000.00", "progress": 0, "stages": []}

> POST /projects/{id}/stages  {"title": "Фундамент"}
< 201 {"id": "…", "title": "Фундамент", "status": "planned", "progress": 0}

> PATCH /stages/{id}/progress  {"progress": 40}
< 200 {"title": "Фундамент", "status": "in_progress", "progress": 40}

[сповіщення → Петренко О.] Бригаду призначено на етап «Фундамент» з 20.11.2026 по 05.12.2026
> POST /assignments  {"brigade_id": "1111…", "stage_id": "…", "start": "2026-11-20", "end": "2026-12-05"}
< 201 {...}

> POST /assignments  {"brigade_id": "1111…", "start": "2026-12-01", "end": "2026-12-10"}
< 409 {"error": "brigade_busy", "message": "Бригада Петренко О. зайнята з 2026-11-20 по 2026-12-05"}

> PATCH /stages/{id}/progress  {"progress": 150}
< 422 {"error": "validation_error", "message": "progress: Input should be less than or equal to 100"}

> GET /projects/{id}
< 200 {"progress": 20, "stages": [{"title": "Фундамент", "progress": 40}, {"title": "Каркас", "progress": 0}]}
```
