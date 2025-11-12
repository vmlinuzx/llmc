# LLMC Textual TUI - Docker Distribution
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ncurses-term \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy LLMC TUI
COPY llmc_textual.py /usr/local/bin/llmc
RUN chmod +x /usr/local/bin/llmc

# Set entrypoint
ENTRYPOINT ["llmc"]

# Build command:
# docker build -t llmc-tui .
# 
# Run commands:
# docker run -it llmc-tui                    # Interactive mode
# docker run --rm -it llmc-tui               # Clean up after exit
# docker run --rm -it -v $(pwd):/workspace llmc-tui  # With file access