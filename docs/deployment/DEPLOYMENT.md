# Розгортання ConstructionPM (ПР4)

Усі команди виконуються з **кореня репозиторію**.

## Структура

| Каталог | Файли | Призначення |
|---|---|---|
| `deploy/docker/` | `Dockerfile`, `.dockerignore` (+ `Dockerfile.dockerignore` → посилання для BuildKit) | Багатоетапна збірка OCI-образу |
| `deploy/compose/` | `docker-compose.yml`, `.env.example`, `telegram-mock/mock.py` | Повний стек: застосунок + мок Telegram Bot API |
| `deploy/k8s/` | `00-namespace.yaml`, `configmap.yaml`, `deployment.yaml`, `service.yaml`, `secret.yaml.example` | Декларативні маніфести Kubernetes |

## 1. Образ Docker

Ключові рішення в `deploy/docker/Dockerfile`:

- **Multi-stage.**
  - Етап `builder` збирає wheel-пакети застосунку і залежностей.
  - Етап `runtime` на `python:3.12-slim` містить лише інтерпретатор і встановлені пакети: без компіляторів, `build`, тестів і вихідного коду.
- **Кеш шарів.** Спочатку копіюється тільки `pyproject.toml` і встановлюються залежності, потім `src/`. Зміна коду не перезбирає шар залежностей.
- **Безпека.**
  - Окремий користувач `app` (UID/GID 10001), інструкція `USER 10001:10001`.
  - У образі немає секретів: токен Telegram передається лише змінною середовища під час запуску.
- **Сигнали.** Exec-форма `ENTRYPOINT ["construction-pm"]` + `CMD ["serve"]`. PID 1 — сам застосунок, тож SIGTERM/SIGINT отримує Uvicorn і коректно завершує запити.
- **HEALTHCHECK.** Вбудованим Python (curl в образі немає) перевіряється `GET /health`.

```bash
# Збірка
docker build -f deploy/docker/Dockerfile -t construction-pm:1.0 .

# Запуск (дані SQLite — в іменованому томі)
docker run -d --name cpm -p 8000:8000 -v cpm-data:/data construction-pm:1.0

# Перевірка
docker ps --filter name=cpm                         # STATUS: Up … (healthy)
curl http://localhost:8000/health                   # {"status":"ok"}
curl http://localhost:8000/ready                    # {"status":"ready"}
docker logs cpm

# Зупинка (graceful shutdown до 20 с)
docker stop -t 20 cpm && docker rm cpm
```

## 2. Docker Compose

Стек складається з двох сервісів у власній мережі `backend` (bridge):

| Сервіс | Образ | Призначення |
|---|---|---|
| `telegram-mock` | `python:3.12-alpine` | Емулює Telegram Bot API (`/bot<token>/sendMessage`), має healthcheck |
| `app` | `construction-pm:1.0` (збирається з `deploy/docker/Dockerfile`) | Застосунок. Стартує лише після `telegram-mock: condition: service_healthy`. Дані в томі `app-data` |

Запуск одним рядком (після створення `.env`):

```bash
cp deploy/compose/.env.example deploy/compose/.env
docker compose -f deploy/compose/docker-compose.yml up -d
```

Перевірка:

```bash
docker compose -f deploy/compose/docker-compose.yml ps        # обидва сервіси healthy
curl http://localhost:8000/ready
docker compose -f deploy/compose/docker-compose.yml logs -f telegram-mock   # тут видно сповіщення бригадирам
docker compose -f deploy/compose/docker-compose.yml down       # зупинка (дані в томі зберігаються; -v — видалити)
```

## 3. Kubernetes

Маніфести в `deploy/k8s/`:

- **Deployment:**
  - `replicas: 2`;
  - `RollingUpdate` (`maxSurge: 1`, `maxUnavailable: 0`);
  - `requests` / `limits` (CPU 100m/500m, RAM 128/256 Mi);
  - probes:
    - `startupProbe` → `/health`, до 60 с на старт;
    - `livenessProbe` → `/health`;
    - `readinessProbe` → `/ready`, перевіряє доступність БД;
  - `securityContext`: non-root, `readOnlyRootFilesystem`, без capabilities;
  - pod anti-affinity.
- **ConfigMap** `construction-pm-config` — несекретні змінні: `CPM_*`.
- **Secret** `construction-pm-secret` — `TELEGRAM_BOT_TOKEN`. У Git лише шаблон `secret.yaml.example`.
- **Service:** `ClusterIP` `construction-pm` (внутрішній) і `NodePort` `construction-pm-nodeport` (порт 30080) для доступу ззовні.

Локальний кластер (Kind, Minikube або K3s):

```bash
# 1. Кластер і образ (приклад для Kind)
kind create cluster --name cpm
docker build -f deploy/docker/Dockerfile -t construction-pm:1.0 .
kind load docker-image construction-pm:1.0 --name cpm
#    Minikube: minikube image load construction-pm:1.0

# 2. Секрет (необов'язково — без нього сповіщення йдуть у журнал)
kubectl apply -f deploy/k8s/00-namespace.yaml
kubectl -n construction-pm create secret generic construction-pm-secret --from-literal=TELEGRAM_BOT_TOKEN='<токен>'

# 3. Застосування маніфестів
kubectl apply -f deploy/k8s/
kubectl -n construction-pm rollout status deployment/construction-pm
```

Перевірка працездатності:

```bash
kubectl -n construction-pm get pods -o wide            # 2 Pod у стані Running, READY 1/1
kubectl -n construction-pm get svc
kubectl -n construction-pm describe deployment construction-pm
kubectl -n construction-pm logs deployment/construction-pm --tail=20

kubectl -n construction-pm port-forward svc/construction-pm 8080:80 &
curl http://localhost:8080/health
curl http://localhost:8080/ready
#    або через NodePort: curl http://<IP вузла>:30080/health  (minikube: minikube service -n construction-pm construction-pm-nodeport --url)
```

## 4. Перевірка в CI

Workflow `.github/workflows/ci.yml` на кожен push і Pull Request виконує три задачі.

**`build-and-test`** — лінтер, тести з порогом покриття, збірка пакета.

**`container`:**
- `hadolint` для `Dockerfile`;
- smoke build образу;
- перевірка, що процес у контейнері працює не від root;
- запуск контейнера з очікуванням статусу `healthy` і коректна зупинка;
- `docker compose config`;
- підйом повного стеку `up --wait` і наскрізний запит: призначення бригади → повідомлення з’являється в журналі `telegram-mock`.

**`kubernetes`:**
- синтаксична і схемна валідація маніфестів (`kubeconform -strict`);
- `kube-linter`;
- розгортання в кластері Kind (`kubectl apply -f deploy/k8s/` → `rollout status`);
- запити до `/health` і `/ready` через Service.

## 5. Обмеження

SQLite — файлова БД, тому в Kubernetes кожна репліка тримає власну копію даних (`emptyDir`). Для двох реплік зі спільними даними потрібна мережева СУБД, наприклад PostgreSQL. Завдяки гексагональній архітектурі для переходу достатньо нового адаптера `IProjectRepository` / `IBrigadeRepository` у компоненті Persistence, доменний код не змінюється.
