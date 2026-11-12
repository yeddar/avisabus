# AvisaBus backend image (deployment_rpi design §2): built on the Mac for linux/arm64.
#   docker compose -f deploy/compose.yaml build   (see deploy/README.md)

# --- build: dependencies (without the dev group) and the package, in /app/.venv -------------------
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.12
WORKDIR /app
# Dependencies first: this layer is reused while uv.lock does not change.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# --- runtime -----------------------------------------------------------------------------------------
FROM python:3.12-slim
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AVISABUS_ENV=prod
RUN groupadd --system --gid 10001 avisabus \
    && useradd --system --uid 10001 --gid avisabus --no-create-home --shell /usr/sbin/nologin avisabus \
    && mkdir -p /data \
    && chown avisabus:avisabus /data
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
# The SAE recording, so AVISABUS_ARRIVALS_SOURCE=replay works without rebuilding (AC-02).
COPY tests/fixtures/sae_recordings/stop_508_peak /app/replay/stop_508_peak
USER avisabus
VOLUME ["/data"]
# No EXPOSE: the port is only reachable by `web` through the internal network (AC-02, AC-03).
# One process (ADR-003). The proxy headers are trusted from anyone because only `web` can reach
# the backend, and it rewrites X-Forwarded-For with a single value (AC-05).
CMD ["uvicorn", "avisabus.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
