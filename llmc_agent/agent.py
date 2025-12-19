"""Core agent logic for llmc_agent.

The agent is the orchestrator that ties together:
- Config loading
- RAG search
- Prompt assembly
- LLM generation
- Tool execution (progressive disclosure)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from llmc_agent.backends.base import GenerateRequest
from llmc_agent.backends.llmc import LLMCBackend, RAGResult
from llmc_agent.backends.ollama import OllamaBackend
from llmc_agent.config import Config
from llmc_agent.format import FormatNegotiator
from llmc_agent.prompt import assemble_prompt, count_tokens, load_system_prompt


@dataclass
class ToolCall:
    """A tool call from the model."""

    name: str
    arguments: dict[str, Any]
    result: Any = None


@dataclass
class AgentResponse:
    """Response from the agent."""

    content: str
    tokens_prompt: int
    tokens_completion: int
    rag_sources: list[str] | None
    model: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tier_used: int = 0


class Agent:
    """The llmc agent with progressive tool disclosure."""

    def __init__(self, config: Config):
        self.config = config

        # Initialize backends
        self.ollama = OllamaBackend(
            base_url=config.ollama.url,
            timeout=config.ollama.timeout,
            temperature=config.ollama.temperature,
            num_ctx=config.ollama.num_ctx,
        )

        self.rag: LLMCBackend | None = None
        if config.rag.enabled:
            self.rag = LLMCBackend()

        # Initialize tool registry
        from llmc_agent.tools import ToolRegistry

        self.tools = ToolRegistry(allowed_roots=["."])

        # Initialize UTP format negotiator for tool call parsing
        self.format_negotiator = FormatNegotiator()

    async def ask(
        self,
        question: str,
        session: Session | None = None,
    ) -> AgentResponse:
        """Ask the agent a question.

        This is the main entry point for the Crawl phase:
        1. Search for relevant code (RAG)
        2. Assemble prompt with context + history
        3. Generate response
        4. Update session if provided

        Args:
            question: The user's question
            session: Optional session for conversation continuity
        """

        # Step 1: RAG search (if enabled)
        rag_results: list[RAGResult] = []
        if self.rag:
            rag_results = await self.rag.search(
                question,
                limit=self.config.rag.max_results,
                min_score=self.config.rag.min_score,
            )

        # Step 2: Assemble prompt
        system_prompt = load_system_prompt(
            self.config.agent.model,
            prompts_dir=Path("prompts") if Path("prompts").exists() else None,
        )

        user_content = assemble_prompt(
            question,
            rag_results=rag_results,
            include_summary=self.config.rag.include_summary,
        )

        # Build messages list with history
        messages = []
        history_tokens = 0

        if session and session.messages:
            # Include history (oldest messages may be dropped if over budget)
            available_for_history = (
                self.config.agent.context_budget
                - count_tokens(system_prompt)
                - count_tokens(user_content)
                - self.config.agent.response_reserve
            ) // 2  # Reserve half for history, half for headroom

            # Add messages from newest to oldest until budget exhausted
            for msg in reversed(session.messages):
                if history_tokens + msg.tokens > available_for_history:
                    break
                messages.insert(0, {"role": msg.role, "content": msg.content})
                history_tokens += msg.tokens

        # Add current user message
        messages.append({"role": "user", "content": user_content})

        # Budget check on RAG
        total_tokens = (
            count_tokens(system_prompt) + count_tokens(user_content) + history_tokens
        )
        if total_tokens > self.config.agent.context_budget:
            # Trim RAG results if over budget
            while rag_results and total_tokens > self.config.agent.context_budget:
                rag_results.pop()
                user_content = assemble_prompt(
                    question,
                    rag_results=rag_results,
                    include_summary=self.config.rag.include_summary,
                )
                # Update the last message
                messages[-1] = {"role": "user", "content": user_content}
                total_tokens = (
                    count_tokens(system_prompt)
                    + count_tokens(user_content)
                    + history_tokens
                )

        # Step 3: Generate response
        request = GenerateRequest(
            messages=messages,
            system=system_prompt,
            model=self.config.agent.model,
            temperature=self.config.ollama.temperature,
            max_tokens=self.config.agent.response_reserve,
        )

        response = await self.ollama.generate(request)

        # Format sources
        rag_sources = None
        if rag_results:
            rag_sources = [f"{r.path}:{r.start_line}-{r.end_line}" for r in rag_results]

        # Step 4: Update session if provided
        if session:
            session.add_message(
                role="user",
                content=question,  # Store original question, not with RAG
                tokens=count_tokens(question),
                rag_sources=None,
            )
            session.add_message(
                role="assistant",
                content=response.content,
                tokens=response.tokens_completion,
                rag_sources=rag_sources,
            )

        return AgentResponse(
            content=response.content,
            tokens_prompt=response.tokens_prompt,
            tokens_completion=response.tokens_completion,
            rag_sources=rag_sources,
            model=response.model,
        )

    async def ask_with_tools(
        self,
        question: str,
        session: Session | None = None,
        max_tool_rounds: int = 5,
    ) -> AgentResponse:
        """Ask with tool support (Walk/Run phases).

        This method:
        1. Detects intent tier from the question
        2. Includes appropriate tools in the request
        3. Executes tool calls and loops until model is done
        4. Returns final response
        """
        from llmc_agent.tools import detect_intent_tier

        # Detect intent and unlock tier
        detected_tier = detect_intent_tier(question)
        self.tools.unlock_tier(detected_tier)

        # Get available tools for this tier
        tools_for_request = self.tools.to_ollama_tools()

        # Build system prompt with tool instructions
        system_prompt = load_system_prompt(
            self.config.agent.model,
            prompts_dir=Path("prompts") if Path("prompts").exists() else None,
        )

        # Always tell the model about available tools
        available_tools = self.tools.get_tools_for_tier()
        if available_tools:
            tool_descriptions = []
            for t in available_tools:
                tool_descriptions.append(f"- {t.name}: {t.description}")
            tools_text = "\n".join(tool_descriptions)
            system_prompt += f"\n\nYou have access to these tools:\n{tools_text}\n\nUse tools when you need to search code, read files, or get more information. Call tools to gather data before answering."

        # Step: RAG search for initial context (even if tools don't work)
        rag_results: list[RAGResult] = []
        rag_sources = None
        if self.rag:
            rag_results = await self.rag.search(
                question,
                limit=self.config.rag.max_results,
                min_score=self.config.rag.min_score,
            )
            if rag_results:
                rag_sources = [
                    f"{r.path}:{r.start_line}-{r.end_line}" for r in rag_results
                ]

        # Assemble user content with RAG context
        user_content = assemble_prompt(
            question,
            rag_results=rag_results,
            include_summary=self.config.rag.include_summary,
        )

        # Start message history
        messages = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        all_tool_calls: list[ToolCall] = []

        # Add user question with RAG context
        messages.append({"role": "user", "content": user_content})

        # Tool loop
        for round_num in range(max_tool_rounds):
            # Generate response
            request = GenerateRequest(
                messages=messages,
                system=system_prompt,
                model=self.config.agent.model,
                temperature=self.config.ollama.temperature,
                max_tokens=self.config.agent.response_reserve,
            )

            response = await self.ollama.generate_with_tools(request, tools_for_request)
            total_prompt_tokens += response.tokens_prompt
            total_completion_tokens += response.tokens_completion

            # === UTP: Parse tool calls from any format ===
            parser = self.format_negotiator.get_call_parser()
            parsed = parser.parse(response.raw_response or {})

            # Check for tool calls (now works with XML, native, etc.)
            if not parsed.tool_calls:
                # No tool calls, we're done
                final_content = parsed.content or response.content
                break

            # Execute tool calls from parsed response
            for tc in parsed.tool_calls:
                tool = self.tools.get_tool(tc.name)
                if not tool:
                    # Unknown tool - add error message
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id or "",
                            "content": json.dumps({"error": f"Tool '{tc.name}' not found"}),
                        }
                    )
                    continue

                # Check if available at current tier
                if not self.tools.is_tool_available(tc.name):
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id or "",
                            "content": json.dumps(
                                {"error": f"Tool '{tc.name}' not available at tier {self.tools.current_tier}"}
                            ),
                        }
                    )
                    continue

                # Execute tool
                try:
                    args = tc.arguments

                    # Async or sync execution
                    if asyncio.iscoroutinefunction(tool.function):
                        result = await tool.function(**args)
                    else:
                        result = tool.function(**args)

                    tool_call = ToolCall(
                        name=tool.name,
                        arguments=args,
                        result=result,
                    )
                    all_tool_calls.append(tool_call)

                    # Add assistant message with tool call
                    tc_id = tc.id or f"call_{round_num}_{tc.name}"
                    messages.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": tc_id,
                                    "function": {
                                        "name": tc.name,
                                        "arguments": json.dumps(tc.arguments),
                                    },
                                }
                            ],
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": json.dumps(result),
                        }
                    )

                except Exception as e:
                    # Tool execution failed
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id or "",
                            "content": json.dumps({"error": str(e)}),
                        }
                    )
        else:
            # Max rounds reached
            final_content = (
                parsed.content if "parsed" in dir() else "Max tool rounds reached."
            )

        # Update session if provided
        if session:
            session.add_message(
                role="user",
                content=question,
                tokens=count_tokens(question),
            )
            session.add_message(
                role="assistant",
                content=final_content,
                tokens=total_completion_tokens,
            )

        return AgentResponse(
            content=final_content,
            tokens_prompt=total_prompt_tokens,
            tokens_completion=total_completion_tokens,
            rag_sources=rag_sources,
            model=self.config.agent.model,
            tool_calls=all_tool_calls,
            tier_used=self.tools.current_tier,
        )

    async def health_check(self) -> dict[str, bool]:
        """Check health of all backends."""

        results = {
            "ollama": await self.ollama.health_check(),
        }

        if self.rag:
            results["rag"] = self.rag.available

        return results


async def run_agent(
    question: str, config: Config | None = None, use_tools: bool = False
) -> AgentResponse:
    """Convenience function to run the agent.

    Args:
        question: The question to ask
        config: Optional config (loads default if not provided)
        use_tools: If True, use ask_with_tools (Walk/Run), else use ask (Crawl)
    """

    if config is None:
        from llmc_agent.config import load_config

        config = load_config()

    agent = Agent(config)

    if use_tools:
        return await agent.ask_with_tools(question)
    else:
        return await agent.ask(question)
