"""
Training data generation for LLMC tool calling.

Generates OpenAI-format training examples from mc* CLI usage for fine-tuning
local models on LLMC-specific tool calling patterns.

Output format (OpenAI fine-tuning compatible):
{
    "messages": [
        {"role": "user", "content": "...query..."},
        {"role": "assistant", "content": null, "tool_calls": [...]},
        {"role": "tool", "tool_call_id": "...", "content": "..."}
    ]
}
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallExample:
    """A single tool call training example."""
    
    tool_name: str
    arguments: dict[str, Any]
    user_query: str
    tool_output: str
    tool_call_id: str = field(default_factory=lambda: f"call_{uuid.uuid4().hex[:12]}")
    
    def to_openai_messages(self) -> list[dict]:
        """Convert to OpenAI fine-tuning message format."""
        return [
            {"role": "user", "content": self.user_query},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": self.tool_call_id,
                        "type": "function",
                        "function": {
                            "name": self.tool_name,
                            "arguments": json.dumps(self.arguments),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": self.tool_call_id,
                "name": self.tool_name,
                "content": self.tool_output,
            },
        ]
    
    def to_training_example(self) -> dict:
        """Convert to full training example format."""
        return {"messages": self.to_openai_messages()}
    
    def to_jsonl_line(self) -> str:
        """Convert to JSONL format for fine-tuning."""
        return json.dumps(self.to_training_example())


# Tool schemas for reference
TOOL_SCHEMAS = {
    "rag_search": {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "Search the codebase semantically using natural language queries",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        },
    },
    "read_file": {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file with optional line range",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"},
                    "start_line": {"type": "integer", "description": "Start line (1-indexed)"},
                    "end_line": {"type": "integer", "description": "End line (1-indexed)"},
                },
                "required": ["path"],
            },
        },
    },
    "inspect_symbol": {
        "type": "function",
        "function": {
            "name": "inspect_symbol",
            "description": "Inspect a code symbol (function, class, method) with graph context",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name to inspect",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    "run_cmd": {
        "type": "function",
        "function": {
            "name": "run_cmd",
            "description": "Run a shell command and capture output",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to run"},
                    "cwd": {"type": "string", "description": "Working directory"},
                },
                "required": ["command"],
            },
        },
    },
    "where_used": {
        "type": "function",
        "function": {
            "name": "where_used",
            "description": "Find callers, callees, and imports for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Symbol to look up"},
                },
                "required": ["symbol"],
            },
        },
    },
}


def emit_training_example(example: ToolCallExample, include_schema: bool = False) -> str:
    """Emit a training example as JSON.
    
    Args:
        example: The tool call example to emit
        include_schema: If True, include tool schema in output
        
    Returns:
        JSON string of the training example
    """
    output = example.to_training_example()
    
    if include_schema and example.tool_name in TOOL_SCHEMAS:
        output["tools"] = [TOOL_SCHEMAS[example.tool_name]]
    
    return json.dumps(output, indent=2)
