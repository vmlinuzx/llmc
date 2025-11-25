#!/usr/bin/env bash
# Log Purge Script for LLMC RAG Service
# Rotates/purges logs to prevent unbounded growth

LOG_DIR="${HOME}/.llmc/logs/rag-daemon"
MAIN_LOG="${LOG_DIR}/rag-service.log"

echo "=== LLMC RAG Log Purge ==="
echo "Log dir: ${LOG_DIR}"

# Check if log file exists
if [ ! -f "${MAIN_LOG}" ]; then
    echo "Log file not found: ${MAIN_LOG}"
    exit 0
fi

# Get current stats
CURRENT_SIZE=$(stat -f%z "${MAIN_LOG}" 2>/dev/null || stat -c%s "${MAIN_LOG}" 2>/dev/null)
CURRENT_LINES=$(wc -l < "${MAIN_LOG}")

echo "Current log: ${CURRENT_SIZE} bytes, ${CURRENT_LINES} lines"

# Purge if too big
MAX_LINES=50000  # Keep last 50k lines
MAX_SIZE=$((50 * 1024 * 1024))  # 50MB

if [ ${CURRENT_LINES} -gt ${MAX_LINES} ] || [ ${CURRENT_SIZE} -gt ${MAX_SIZE} ]; then
    echo "Log file too large - purging..."
    
    # Create backup
    BACKUP="${MAIN_LOG}.old"
    cp "${MAIN_LOG}" "${BACKUP}"
    
    # Keep only last MAX_LINES
    tail -n ${MAX_LINES} "${MAIN_LOG}" > "${MAIN_LOG}.tmp"
    mv "${MAIN_LOG}.tmp" "${MAIN_LOG}"
    
    # Compress old log
    gzip "${BACKUP}"
    
    NEW_LINES=$(wc -l < "${MAIN_LOG}")
    echo "Purged ${CURRENT_LINES} lines, kept ${NEW_LINES} lines"
    echo "Compressed old log: ${BACKUP}.gz"
else
    echo "Log file size OK (${CURRENT_LINES} lines, ${CURRENT_SIZE} bytes)"
fi

# Clean old compressed logs (keep last 5)
cd "${LOG_DIR}" || exit 1
find . -name "*.gz" -type f | sort -r | tail -n +6 | xargs rm -f 2>/dev/null || true

echo "=== Purge complete ==="
