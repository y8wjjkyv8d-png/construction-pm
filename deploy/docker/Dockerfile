# syntax=docker/dockerfile:1.7
# Збірка з кореня репозиторію:
#   docker build -f deploy/docker/Dockerfile -t construction-pm:1.0 .

# ---------- Етап 1: builder — повний набір інструментів, збирає wheel ----------
FROM python:3.12.8-slim-bookworm AS builder
WORKDIR /build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# Спочатку лише маніфест збірки — шар із залежностями кешується, доки pyproject.toml не змінився
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir build==1.6.1 \
    && pip wheel --no-cache-dir --wheel-dir /wheels \
       "fastapi==0.163.1" "pydantic==2.14.3" "uvicorn==0.54.0" "httpx2==2.16.1"

# Потім вихідний код — змінюється часто, тому копіюється останнім
COPY src/ ./src/
RUN python -m build --wheel --outdir /wheels .

# ---------- Етап 2: runtime — лише інтерпретатор і готові wheel-пакети ----------
FROM python:3.12.8-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="construction-pm" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.source="https://github.com/y8wjjkyv8d-png/construction-pm"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CPM_HOST=0.0.0.0 \
    CPM_PORT=8000 \
    CPM_DB_PATH=/data/construction.db

# Окремий не-root користувач і група, каталог даних належить їм
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /data /app \
    && chown app:app /data /app

COPY --from=builder /wheels /tmp/wheels
RUN pip install --no-cache-dir --no-index --find-links=/tmp/wheels construction-pm==1.0.0 \
    && rm -rf /tmp/wheels

WORKDIR /app
USER 10001:10001
VOLUME ["/data"]
EXPOSE 8000

# Перевірка життєздатності без curl — вбудованим Python
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"CPM_PORT\",\"8000\")}/health', timeout=2).status == 200 else 1)"]

# exec-форма: процес застосунку отримує SIGTERM/SIGINT напряму (graceful shutdown)
ENTRYPOINT ["construction-pm"]
CMD ["serve"]
