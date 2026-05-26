# Use an official Python runtime as a parent image
FROM python:3.11.9-bookworm

# Install necessary packages
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Install uv via pip to avoid GitHub release download issues
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
RUN python -m pip install --no-cache-dir -i ${PIP_INDEX_URL} uv==0.5.9

# Set working directory in the container to /app
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Add the rest of the application code
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Start the bot
CMD ["uv", "run", "python", "run.py"]