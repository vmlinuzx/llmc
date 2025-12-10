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
    "qwen": """You are a code assistant with access to tools. Use tools proactively to answer questions.

IMPORTANT: When asked to read, show, or explain a file:
1. Use the read_file tool to get the actual content
2. Then answer based on what you read

When asked to find or search for something:
1. Use the search_code tool to find relevant code
2. Then explain what you found

Rules:
- USE TOOLS when you need file contents or to search code
- Reference files by path
- Be concise - every token counts
- Say "I don't see that in the context" only if tools return nothing useful""",
    
    "llama": """You are a helpful code assistant with tool access. Answer questions about the codebase.

When you need to read files or search code, use the tools provided.

- Be concise and direct
- Reference specific file paths
- Use code blocks for snippets
- Use tools to get information before saying you can't find something""",
}


def load_system_prompt(model: str, prompts_dir: Path | None = None) -> str:
    """Load the appropriate system prompt for the model.
    
    Priority:
    1. Custom prompt file (prompts/{model_family}.md)
    2. Built-in model-specific prompt
    3. Default prompt
    """
    
    # Extract model family - handle various naming schemes
    # Examples: "qwen3:4b", "hf.co/unsloth/Qwen3-Coder-30B-...", "llama3.1:8b"
    model_lower = model.lower()
    
    # Check for known model families anywhere in the name
    model_family = None
    for family in MODEL_PROMPTS.keys():
        if family in model_lower:
            model_family = family
            break
    
    # Check for custom prompt file
    if prompts_dir and model_family:
        prompt_file = prompts_dir / f"{model_family}.md"
        if prompt_file.exists():
            return prompt_file.read_text().strip()
    
    # Return model-specific prompt or default
    if model_family and model_family in MODEL_PROMPTS:
        return MODEL_PROMPTS[model_family]
    
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
