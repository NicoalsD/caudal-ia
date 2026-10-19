# Image for Hugging Face Spaces (Docker, CPU). See .agents/deployment.md.
ARG PYTHON_IMAGE=python:3.12.15-slim-trixie
FROM ${PYTHON_IMAGE}

ARG CHRONOS_MODEL_ID=autogluon/chronos-2-small
ARG APP_UID=1000

COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/

# Hugging Face Spaces requires the container to run as user 1000.
RUN useradd --create-home --uid ${APP_UID} --shell /usr/sbin/nologin app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    HF_HOME=/home/app/.cache/huggingface \
    PORT=7860 \
    CHRONOS_MODEL_ID=${CHRONOS_MODEL_ID}

WORKDIR /app

# Dependency layer: rebuilt only when pyproject.toml or uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

# Model weights baked into the image: startup does not depend on the network.
RUN mkdir -p "${HF_HOME}" \
    && chown -R app:app /home/app/.cache \
    && su app -s /bin/sh -c \
       'python -c "import os; from huggingface_hub import snapshot_download; snapshot_download(os.environ[\"CHRONOS_MODEL_ID\"])"'

# With the weights already downloaded, the service never calls Hugging Face.
# To change the model, rebuild with --build-arg CHRONOS_MODEL_ID=...
ENV HF_HUB_OFFLINE=1

USER app

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/v1/health' % os.environ.get('PORT', '7860'), timeout=4)"]

CMD ["sh", "-c", "exec uvicorn caudal_ia.main:app --host 0.0.0.0 --port ${PORT}"]
