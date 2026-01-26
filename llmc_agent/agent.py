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

from llmc_agent.backends.base import Backend, GenerateRequest
from llmc_agent.backends.llmc import LLMCBackend, RAGResult
from llmc_agent.backends.ollama import OllamaBackend
from llmc_agent.backends.openai_compat import OpenAICompatBackend

# LiteLLM backend import is deferred to avoid import cost when not used
from llmc_agent.config import Config
from llmc_agent.format import FormatNegotiator
from llmc_agent.session import Session
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

        # Initialize LLM backend based on provider
        self.backend: Backend = self._create_backend(config)
        # For compatibility, also expose as .ollama (legacy code paths)
        self.ollama = self.backend

        # Initialize other components
        self._init_components(config)

    def _create_backend(self, config: Config) -> Backend:
        """Create the appropriate backend based on configuration.
        
        Priority:
        1. LiteLLM (if enabled) - unified provider abstraction
        2. OpenAI-compatible (if provider="openai")
        3. Ollama (default)
        """
        # Check if LiteLLM is enabled (feature flag)
        if config.litellm.enabled:
            from llmc.backends import LiteLLMAgentBackend, LiteLLMConfig
            
            litellm_config = LiteLLMConfig(
                model=config.litellm.model,
                api_key=config.litellm.api_key,
                api_base=config.litellm.api_base,
                temperature=config.litellm.temperature,
                max_tokens=config.litellm.max_tokens,
                timeout=config.litellm.timeout,
                num_retries=config.litellm.num_retries,
            )
            return LiteLLMAgentBackend(litellm_config)
        
        # Legacy backends
        if config.agent.provider == "openai":
            # Use OpenAI-compatible backend (llama-server, vLLM, etc.)
            return OpenAICompatBackend(
                base_url=config.openai.url,
                api_key=config.openai.api_key,
                timeout=config.openai.timeout,
                temperature=config.openai.temperature,
                model=config.openai.model,
            )
        
        # Default: Ollama backend
        return OllamaBackend(
            base_url=config.ollama.url,
            timeout=config.ollama.timeout,
            temperature=config.ollama.temperature,
            num_ctx=config.ollama.num_ctx,
        )

    def _init_components(self, config: Config) -> None:
        """Initialize RAG, tools, and format negotiator."""
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
            # PINNING STRATEGY: Protect critical context from truncation
            # Pin: First 2 messages (user's original objective + first response)
            # Pin: Last 3 turns (6 messages) for recent context continuity
            # Truncate: Middle messages first
            
            available_for_history = (
                self.config.agent.context_budget
                - count_tokens(system_prompt)
                - count_tokens(user_content)
                - self.config.agent.response_reserve
            ) // 2  # Reserve half for history, half for headroom

            all_msgs = session.messages
            n = len(all_msgs)
            
            # Define pinned regions
            PIN_HEAD = 2  # First 2 messages (original objective)
            PIN_TAIL = 6  # Last 6 messages (3 turns of user+assistant)
            
            if n <= PIN_HEAD + PIN_TAIL:
                # Session is small enough - include everything that fits
                for msg in reversed(all_msgs):
                    if history_tokens + msg.tokens > available_for_history:
                        break
                    messages.insert(0, {"role": msg.role, "content": msg.content})
                    history_tokens += msg.tokens
            else:
                # Large session - use pinning strategy
                head_msgs = all_msgs[:PIN_HEAD]
                tail_msgs = all_msgs[-PIN_TAIL:]
                middle_msgs = all_msgs[PIN_HEAD:-PIN_TAIL]
                
                # Calculate token costs
                head_tokens = sum(m.tokens for m in head_msgs)
                tail_tokens = sum(m.tokens for m in tail_msgs)
                pinned_tokens = head_tokens + tail_tokens
                
                if pinned_tokens <= available_for_history:
                    # Add pinned head (always)
                    for msg in head_msgs:
                        messages.append({"role": msg.role, "content": msg.content})
                        history_tokens += msg.tokens
                    
                    # Add as much middle as fits (from most recent backward)
                    remaining_budget = available_for_history - pinned_tokens
                    middle_to_add = []
                    for msg in reversed(middle_msgs):
                        if sum(m.tokens for m in middle_to_add) + msg.tokens > remaining_budget:
                            break
                        middle_to_add.insert(0, msg)
                    
                    for msg in middle_to_add:
                        messages.append({"role": msg.role, "content": msg.content})
                        history_tokens += msg.tokens
                    
                    # Add pinned tail (always)
                    for msg in tail_msgs:
                        messages.append({"role": msg.role, "content": msg.content})
                        history_tokens += msg.tokens
                else:
                    # Budget too tight even for pinned - prioritize tail (recency)
                    for msg in reversed(tail_msgs):
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
        verbose_callback: callable | None = None,
    ) -> AgentResponse:
        """Ask with tool support (Walk/Run phases).

        This method:
        1. Detects intent tier from the question
        2. Includes appropriate tools in the request
        3. Executes tool calls and loops until model is done
        4. Returns final response
        
        If verbose_callback is provided, it will be called with status updates:
        - ("thinking", "..reasoning text..")
        - ("tool_call", "tool_name", {args})
        - ("tool_result", "tool_name", "..result..")
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
        # Note: For models with native tool support (like qwen3-next-80b-tools),
        # the modelfile template handles tool format instructions.
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

            # Show any reasoning/thinking if verbose mode
            if verbose_callback and parsed.content:
                verbose_callback("thinking", parsed.content)

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

                # Verbose: show tool being called
                if verbose_callback:
                    verbose_callback("tool_call", tc.name, tc.arguments)

                # Execute tool
                try:
                    args = tc.arguments

                    # Async or sync execution
                    if asyncio.iscoroutinefunction(tool.function):
                        result = await tool.function(**args)
                    else:
                        result = tool.function(**args)

                    # Verbose: show tool result summary
                    if verbose_callback:
                        result_summary = str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
                        verbose_callback("tool_result", tc.name, result_summary)

                    tool_call = ToolCall(
                        name=tool.name,
                        arguments=args,
                        result=result,
                    )
                    all_tool_calls.append(tool_call)

                    # Add assistant message with tool call
                    tc_id = tc.id or f"call_{round_num}_{tc.name}"
                    
                    # Format arguments based on provider
                    # OpenAI/llama-server: Arguments must be JSON string
                    # Ollama: Arguments should be dict
                    if self.config.agent.provider == "openai":
                        args_formatted = json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else tc.arguments
                    else:
                        args_formatted = tc.arguments
                    
                    messages.append(
                        {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": tc_id,
                                    "type": "function",  # Required by OpenAI spec
                                    "function": {
                                        "name": tc.name,
                                        "arguments": args_formatted,
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
            # Max rounds reached - the last response likely had tool calls
            # Make one final request WITHOUT tools to get the synthesized answer
            final_content = parsed.content if "parsed" in dir() else ""
            
            if not final_content and messages:
                # Ask the model to synthesize an answer from what it learned
                messages.append({
                    "role": "user",
                    "content": "Now synthesize your findings into a helpful answer. Do NOT use any more tools. Just answer the original question directly based on what you learned."
                })
                
                # Use a simpler system prompt that doesn't mention tools
                simple_system = "You are a helpful assistant. Answer questions directly and concisely based on the information gathered."
                
                # Request WITHOUT tools to force a text response
                request = GenerateRequest(
                    messages=messages,
                    system=simple_system,
                    model=self.config.agent.model,
                    temperature=self.config.ollama.temperature,
                    max_tokens=self.config.agent.response_reserve,
                )
                
                # Don't pass tools - force text response
                response = await self.ollama.generate(request)
                final_content = response.content
                total_prompt_tokens += response.tokens_prompt
                total_completion_tokens += response.tokens_completion

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
