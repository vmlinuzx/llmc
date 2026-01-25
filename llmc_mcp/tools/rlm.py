from __future__ import annotations

from typing import Any

from mcp.types import Tool, TextContent

from llmc.rlm.session import RLMSession
from llmc_mcp.config import RLMConfig


class RLMTool:
    """Run a Recursive Loop Manager (RLM) session."""

    def __init__(self, config: RLMConfig):
        self.config = config
        self.name = "run_rlm"
        self.description = "Run a Recursive Loop Manager (RLM) session to solve a complex task using Python code and available tools."
        self.inputSchema = {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "The goal or task for the RLM to solve.",
                },
                "context": {
                    "type": "string",
                    "description": "Optional initial context (text or code) for the session.",
                },
                "max_turns": {
                    "type": "integer",
                    "description": "Maximum number of turns (loops) allowed.",
                },
            },
            "required": ["goal"],
        }

    def to_mcp_tool(self) -> Tool:
        return Tool(
            name=self.name,
            description=self.description,
            inputSchema=self.inputSchema,
        )

    async def run(self, arguments: dict[str, Any]) -> list[TextContent]:
        if not self.config.enabled:
            raise ValueError("RLM is disabled")

        goal = arguments.get("goal")
        if not goal:
            raise ValueError("Missing 'goal' argument")

        context = arguments.get("context")
        max_turns = arguments.get("max_turns")

        if max_turns is None:
            max_turns = self.config.max_loops

        # Initialize session
        # We rely on RLMSession loading its config from llmc.toml
        session = RLMSession()

        if context:
            session.load_context(context)

        result = await session.run(task=goal, max_turns=max_turns)

        output_parts = [f"RLM Session {result.session_id}"]
        output_parts.append(f"Success: {result.success}")
        
        if result.answer:
            output_parts.append(f"Answer: {result.answer}")
        
        if result.error:
            output_parts.append(f"Error: {result.error}")
            
        return [TextContent(type="text", text="\n".join(output_parts))]
