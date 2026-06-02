ARG ALPINE_VERSION=3.21
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS build

# Install uv via pip to avoid GitHub release download issues
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
RUN python -m pip install --no-cache-dir -i ${PIP_INDEX_URL} uv==0.5.9

# Set working directory in the container to /app
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Add the rest of the application code
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION}

RUN apk add --no-cache --update ca-certificates
WORKDIR /app

COPY --from=build /app /app

ENV PATH="/app/.venv/bin:${PATH}"
LABEL org.opencontainers.image.title="telegram-downloader"

# Start the bot
CMD ["python", "run.py"]
