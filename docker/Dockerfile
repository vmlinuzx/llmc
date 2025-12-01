
# docker/Dockerfile — LLMC MCP + TE (Single Container)
# M5 decision: single container, MCP calls TE as subprocess.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
# Namespaced session vars; legacy exported for compatibility
ENV LLMC_TE_AGENT_ID=agent-docker
ENV LLMC_TE_SESSION_ID=docker-dev
ENV LLMC_TE_MODEL=unknown

# System deps (git for editable installs; rg optional but handy for TE)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates ripgrep && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy minimal build context first for layer caching
COPY pyproject.toml* requirements.txt* /app/
RUN bash -lc 'if [ -f "pyproject.toml" ]; then pip install -e .; fi; \
              if [ -f "requirements.txt" ]; then pip install -r requirements.txt; fi'

# Copy the rest of the repo (kept late for cache efficiency)
COPY . /app

# Install again in case new modules were introduced
RUN bash -lc 'if [ -f "pyproject.toml" ]; then pip install -e .; fi; \
              if [ -f "requirements.txt" ]; then pip install -r requirements.txt; fi'

# Optional: install TE if it is a local subpackage (adjust as needed)
# RUN pip install -e llmc/te || true

# Runtime dirs for persistence (bind-mounted via compose)
RUN mkdir -p /workspace /data /metrics /logs /app/.llmc/te_handles

# Entry
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Default command starts MCP server on stdio
ENTRYPOINT ["/entrypoint.sh"]
