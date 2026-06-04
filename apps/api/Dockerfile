FROM python:3.10-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY apps ./apps
COPY packages ./packages

RUN python -m pip install --no-cache-dir -e .

EXPOSE 8000
