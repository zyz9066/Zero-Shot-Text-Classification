FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv
FROM python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS dependencies
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /opt/app
ENV UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY app ./app
RUN uv sync --locked --no-dev --no-build-isolation

FROM python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS runtime
WORKDIR /opt/app
RUN test -s /etc/ssl/certs/ca-certificates.crt \
    && useradd --uid 10001 --create-home appuser \
    && mkdir -p /runtime/models /runtime/hf-home/hub /runtime/hub-cache \
       /runtime/xdg-cache /runtime/labels \
    && chown -R 10001:10001 /runtime
COPY --from=dependencies /opt/app/.venv /opt/app/.venv
COPY app ./app
COPY configs/app.yaml configs/models.yaml ./configs/
COPY scripts/check_deployment.py ./scripts/check_deployment.py
ENV PATH="/opt/app/.venv/bin:$PATH" \
    PYTHONPATH=/opt/app \
    PYTHONDONTWRITEBYTECODE=1 \
    MODEL_DIR=/runtime/models \
    HF_HOME=/runtime/hf-home \
    TRANSFORMERS_CACHE=/runtime/hub-cache \
    HF_HUB_CACHE=/runtime/hf-home/hub \
    XDG_CACHE_HOME=/runtime/xdg-cache \
    LABEL_CONFIG_FILE=/runtime/labels/catalog.yaml \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
USER 10001:10001
EXPOSE 8501
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]

FROM dependencies AS development-dependencies
RUN uv sync --locked --all-groups --no-build-isolation

FROM runtime AS validation
COPY --from=development-dependencies /opt/app/.venv /opt/app/.venv
COPY tests ./tests
COPY pyproject.toml uv.lock ./
COPY Dockerfile .dockerignore compose.yaml compose.minio.yaml ./
COPY .github/workflows/ci.yml ./.github/workflows/ci.yml
