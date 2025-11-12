FROM python:3.11-slim

WORKDIR /app

# Build deps for tree_sitter and friends
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy only packaging and API (your repo will be bind-mounted at runtime)
COPY pyproject.toml /app/pyproject.toml
COPY tools/rag /app/tools/rag 2>/dev/null || true
RUN pip install -U pip wheel && pip install . || true

COPY api /app/api
EXPOSE 8000
CMD ["python", "api/server.py"]
