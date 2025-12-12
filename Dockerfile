FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/vmlinuzx/llmc"
LABEL org.opencontainers.image.description="LLMC - LLM Cost Compression through RAG"

WORKDIR /llmc

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY llmc/ llmc/
COPY llmcwrapper/ llmcwrapper/
COPY llmc_mcp/ llmc_mcp/
COPY llmc_agent/ llmc_agent/
COPY tools/ tools/
COPY scripts/ scripts/

# Install LLMC with all extras
RUN pip install --no-cache-dir -e ".[rag,tui,agent,daemon]"

# Default working directory for user repos
WORKDIR /repo

ENTRYPOINT ["llmc-cli"]
CMD ["--help"]
