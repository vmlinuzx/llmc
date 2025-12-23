import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, "/home/vmlinux/src/llmc")

from llmc.rag.service import RAGService

# Mock dependencies
state = MagicMock()
tracker = MagicMock()

service = RAGService(state, tracker)
logger = logging.getLogger("llmc.rag.service")

print(f"Effective Log Level: {logger.getEffectiveLevel()}")
print("--- STARTING TEST ---")
# Use current directory which definitely exists
service.process_repo(".")
print("--- ENDING TEST ---")