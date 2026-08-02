FROM python:3.10

ENV WORK_DIR=/code

RUN useradd -ms /bin/bash django

RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Use the base image's Python; don't let uv download its own into /root
ENV UV_PYTHON_DOWNLOADS=0

# Install Python dependencies in a cacheable layer before copying app code
WORKDIR ${WORK_DIR}
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY --chown=django:django pickem ${WORK_DIR}
COPY --chown=django:django docker/app/docker-entrypoint.sh ${WORK_DIR}/bin/docker-entrypoint.sh

USER django

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=${WORK_DIR}/.venv
ENV PATH="${WORK_DIR}/.venv/bin:${PATH}"

EXPOSE 8000
ENTRYPOINT ["/code/bin/docker-entrypoint.sh"]
