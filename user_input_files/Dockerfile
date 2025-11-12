FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy packaging + (optionally) your engine. If not present, runtime bind mount provides it.
COPY pyproject.toml /app/pyproject.toml
COPY tools/rag /app/tools/rag 2>/dev/null || true

RUN pip install -U pip wheel && \
    pip install '.[api,embed]' || true

COPY api /app/api
COPY llmc.toml /app/llmc.toml

EXPOSE 8000
CMD ["uvicorn","api.server:app","--host","0.0.0.0","--port","8000"]

