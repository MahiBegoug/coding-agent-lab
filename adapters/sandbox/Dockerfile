FROM python:3.12-slim

RUN pip install --no-cache-dir pytest \
    && useradd --create-home --uid 10001 runner

ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /workspace
USER runner

CMD ["pytest", "-q", "-p", "no:cacheprovider"]
