"""Core agent logic for llmc_agent.

The agent is the orchestrator that ties together:
- Config loading
- RAG search
- Prompt assembly
- LLM generation
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from llmc_agent.backends.base import GenerateRequest
from llmc_agent.backends.llmc import LLMCBackend, RAGResult
from llmc_agent.backends.ollama import OllamaBackend
from llmc_agent.config import Config
from llmc_agent.prompt import assemble_prompt, count_tokens, load_system_prompt


@dataclass
class AgentResponse:
    """Response from the agent."""
    
    content: str
    tokens_prompt: int
    tokens_completion: int
    rag_sources: list[str] | None
    model: str


class Agent:
    """The llmc agent."""
    
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
    
    async def ask(
        self,
        question: str,
        session: "Session | None" = None,
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
        from llmc_agent.session import Session  # Avoid circular import
        
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
        total_tokens = count_tokens(system_prompt) + count_tokens(user_content) + history_tokens
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
                total_tokens = count_tokens(system_prompt) + count_tokens(user_content) + history_tokens
        
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
            rag_sources = [
                f"{r.path}:{r.start_line}-{r.end_line}"
                for r in rag_results
            ]
        
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
    
    async def health_check(self) -> dict[str, bool]:
        """Check health of all backends."""
        
        results = {
            "ollama": await self.ollama.health_check(),
        }
        
        if self.rag:
            results["rag"] = self.rag.available
        
        return results


async def run_agent(question: str, config: Config | None = None) -> AgentResponse:
    """Convenience function to run the agent."""
    
    if config is None:
        from llmc_agent.config import load_config
        config = load_config()
    
    agent = Agent(config)
    return await agent.ask(question)
