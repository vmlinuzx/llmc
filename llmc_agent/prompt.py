"""Prompt management for llmc_agent.

Handles system prompt loading and context assembly.
"""

from __future__ import annotations

from pathlib import Path

from llmc_agent.backends.llmc import RAGResult, format_rag_results


# Default system prompt for Crawl phase (RAG Q&A)
DEFAULT_SYSTEM_PROMPT = """You are a code assistant. Answer questions about the codebase using the provided context.

Instructions:
- Be concise (you have limited context)
- Reference specific files and line numbers when you know them
- If the answer isn't in the provided context, say so briefly
- Use code blocks with language hints when showing code
- Don't pad responses with unnecessary caveats"""

# Model-specific prompts optimized for small models
MODEL_PROMPTS = {
    "qwen": """You are a code assistant running locally. Answer questions about code concisely.

Rules:
- Every token counts. Be direct.
- Reference files by path when you know them.
- If you see [Relevant code], use it to inform your answer.
- Say "I don't see that in the provided context" if you can't find something.""",
    
    "llama": """You are a helpful code assistant. Answer questions about the codebase using the context provided.

- Be concise and direct
- Reference specific file paths and line numbers
- Use code blocks for code snippets
- If information isn't in the context, say so""",
}


def load_system_prompt(model: str, prompts_dir: Path | None = None) -> str:
    """Load the appropriate system prompt for the model.
    
    Priority:
    1. Custom prompt file (prompts/{model_family}.md)
    2. Built-in model-specific prompt
    3. Default prompt
    """
    
    # Extract model family (e.g., "qwen3:4b" -> "qwen", "llama3.1:8b" -> "llama")
    import re
    model_base = model.split(":")[0].lower()
    model_prefix = model_base  # e.g., "qwen3"
    # Strip trailing version numbers/dots for family (e.g., "qwen3" -> "qwen")
    model_family = re.sub(r'[\d.]+$', '', model_base) or model_base
    
    # Check for custom prompt file
    if prompts_dir:
        for name in [model, model_prefix, model_family]:
            prompt_file = prompts_dir / f"{name}.md"
            if prompt_file.exists():
                return prompt_file.read_text().strip()
    
    # Check built-in model prompts
    for key in [model_prefix, model_family]:
        if key in MODEL_PROMPTS:
            return MODEL_PROMPTS[key]
    
    return DEFAULT_SYSTEM_PROMPT


def assemble_prompt(
    user_question: str,
    rag_results: list[RAGResult] | None = None,
    include_summary: bool = True,
) -> str:
    """Assemble the user prompt with RAG context.
    
    Returns the content that goes in the "user" message.
    """
    
    parts = []
    
    # Add RAG results if available
    if rag_results:
        rag_content = format_rag_results(rag_results, include_summary=include_summary)
        if rag_content:
            parts.append(rag_content)
    
    # Add user question
    parts.append(f"Question: {user_question}")
    
    return "\n\n".join(parts)


def count_tokens(text: str) -> int:
    """Estimate token count using conservative heuristic.
    
    Uses ~3 chars per token which is conservative (actual is ~4).
    This ensures we don't overflow context windows.
    """
    return len(text) // 3 + 1


def trim_to_budget(text: str, max_tokens: int) -> str:
    """Trim text to fit within token budget."""
    
    current = count_tokens(text)
    if current <= max_tokens:
        return text
    
    # Simple truncation with marker
    chars_to_keep = max_tokens * 3  # Reverse the estimation
    return text[:chars_to_keep] + "\n\n[...truncated...]"
