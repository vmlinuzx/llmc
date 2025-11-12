# CPU-only, minimal
FROM python:3.11-slim

WORKDIR /app

# Build deps for tree_sitter and friends
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only what's needed to build/install the package
COPY tools/rag /app/tools/rag
COPY pyproject.toml /app/pyproject.toml

RUN pip install -U pip wheel && \
    pip install . && \
    python - <<'PY'
import nltk; nltk.download('punkt')
PY

# Default to an API (can be overridden)
COPY api /app/api
EXPOSE 8000
CMD [ "python", "api/server.py" ]
