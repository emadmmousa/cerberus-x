# Fast rebuild: layer new Python/UI code onto the last working orchestrator image.
FROM cerberus-x-orchestrator:latest
COPY src /app/src
ENV PYTHONPATH=/app/src
WORKDIR /app
