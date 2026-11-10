FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir "pytest==8.3.5" \
    && useradd --create-home --uid 10001 sandbox

USER sandbox
WORKDIR /workspace
