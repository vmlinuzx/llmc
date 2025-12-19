# SDD: Unified Tool Protocol (UTP) Implementation

**Version:** 1.0  
**Date:** 2025-12-18  
**Author:** Antigravity (with Dave)  
**Status:** Ready for Implementation  
**HLD Reference:** `HLD_Unified_Tool_Protocol.md`  
**UAT Reference:** `UAT_Unified_Tool_Protocol.md`

---

## 1. Problem Statement

### 1.1 The P0 Issue

**Symptom:** `bx` (llmc_agent) successfully retrieves RAG context, the model decides to use tools, but tool calls are printed as text instead of executed.

**Root Cause:** The agent checks `response.tool_calls` (Ollama native API field), but custom modelfiles like `qwen3-next-80b-tools` output tool calls as XML in `response.content`:

```xml
<tools>
{"name": "search_code", "arguments": {"query": "authentication"}}
</tools>
```

**Impact:** Blocks local LLM agentic workflows with Boxxie (80B model @ 32 t/s on Strix Halo).

### 1.2 What Exists Today

| Component | Location | Status |
|-----------|----------|--------|
| Tool tier system | `llmc_agent/tools.py` | ✅ Working |
| Tool definitions | `llmc_agent/tools.py` | ✅ Working (Ollama format) |
| Ollama backend | `llmc_agent/backends/ollama.py` | ⚠️ Only parses native `tool_calls` |
| Agent loop | `llmc_agent/agent.py:193-364` | ⚠️ Assumes native format |
| Tool Envelope | `llmc/te/` | ✅ Working (orthogonal) |
| Progressive disclosure | `llmc_agent/tools.py:ToolTier` | ✅ Working |

### 1.3 What Needs to Change

1. **Add format translation layer** between Ollama response and agent execution
2. **Parse tool calls from multiple formats** (native, XML, JSON-in-content)
3. **Normalize to internal representation** before tier checking and execution
4. **Make format configurable** per-profile in `llmc.toml`

---

## 2. Scope

### 2.1 In Scope

- New `llmc_agent/format/` package with parsers and adapters
- Modification to `llmc_agent/agent.py` to use format layer
- Modification to `llmc_agent/backends/ollama.py` to expose raw response
- Configuration schema for `[profiles.*.tools]` in `llmc.toml`
- Unit tests for parsers
- Integration test with Boxxie

### 2.2 Out of Scope

- Anthropic API backend (future work)
- OpenAI API backend (future work)
- Changes to RAG indexing, graph, or enrichment
- Changes to Tool Envelope
- Changes to MCP server

---

## 3. Design

### 3.1 Package Structure

```
llmc_agent/
├── format/                    # NEW PACKAGE
│   ├── __init__.py
│   ├── types.py              # ToolCall, ToolResult, ParsedResponse
│   ├── protocols.py          # Protocol definitions
│   ├── negotiator.py         # FormatNegotiator factory
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── openai.py         # OpenAINativeParser
│   │   ├── xml.py            # XMLToolParser
│   │   └── composite.py      # CompositeParser (tries all)
│   └── adapters/
│       ├── __init__.py
│       ├── openai.py         # OpenAI definition/result adapters
│       └── anthropic.py      # Anthropic adapters (stub for now)
├── agent.py                  # MODIFY: use format layer
├── backends/
│   └── ollama.py             # MODIFY: return raw response
├── tools.py                  # NO CHANGE
└── config.py                 # MODIFY: add tools config
```

### 3.2 Data Flow (After Implementation)

```
User Question
      ↓
Intent Detection → Tier Unlock → Available Tools (existing)
      ↓
FormatNegotiator.get_definition_adapter()
      ↓
DefinitionAdapter.format_tools() → Ollama API request
      ↓
Ollama Response (may have tool_calls or XML in content)
      ↓
FormatNegotiator.get_call_parser()
      ↓
CompositeParser.parse(response) → list[ToolCall]  ← NEW STEP
      ↓
ToolRegistry.is_tool_available() → Tier Check (existing)
      ↓
Tool Execution → Tool Envelope formatting (existing)
      ↓
ResultAdapter.format_result() → Inject to conversation
      ↓
Loop or Final Response
```

---

## 4. Implementation Tasks

### Phase 0: Foundation (4 hours)

#### Task 0.1: Create package structure
```bash
mkdir -p llmc_agent/format/parsers llmc_agent/format/adapters
touch llmc_agent/format/__init__.py
touch llmc_agent/format/parsers/__init__.py
touch llmc_agent/format/adapters/__init__.py
```

#### Task 0.2: Implement `types.py`

**File:** `llmc_agent/format/types.py`

```python
"""Internal representations for Unified Tool Protocol (UTP)."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolFormat(Enum):
    """Supported tool calling formats."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    AUTO = "auto"


@dataclass
class ToolCall:
    """Normalized tool call - the lingua franca."""
    name: str
    arguments: dict[str, Any]
    id: str | None = None
    raw: Any = None  # Original format for debugging


@dataclass
class ToolResult:
    """Normalized tool result."""
    call_id: str | None
    tool_name: str
    result: Any
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class ParsedResponse:
    """Result of parsing a model response."""
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    raw_response: Any = None
```

#### Task 0.3: Implement `protocols.py`

**File:** `llmc_agent/format/protocols.py`

```python
"""Protocol definitions for format adapters and parsers."""

from typing import Any, Protocol, runtime_checkable

from llmc_agent.format.types import ParsedResponse, ToolCall, ToolResult


@runtime_checkable
class ToolCallParser(Protocol):
    """Extracts tool calls from model responses."""
    
    def can_parse(self, response: Any) -> bool:
        """Check if this parser can handle the response."""
        ...
    
    def parse(self, response: Any) -> ParsedResponse:
        """Parse response and extract tool calls."""
        ...


@runtime_checkable
class ToolDefinitionAdapter(Protocol):
    """Converts internal tool definitions to provider format."""
    
    def format_tools(self, tools: list) -> Any:
        """Convert tools to provider-specific format."""
        ...


@runtime_checkable
class ToolResultAdapter(Protocol):
    """Converts tool results to provider message format."""
    
    def format_result(self, call: ToolCall, result: ToolResult) -> dict[str, Any]:
        """Convert result to provider-specific message."""
        ...
```

---

### Phase 1: Parsers (6 hours)

#### Task 1.1: Implement `OpenAINativeParser`

**File:** `llmc_agent/format/parsers/openai.py`

```python
"""Parser for OpenAI/Ollama native tool_calls field."""

from __future__ import annotations

import json
from typing import Any

from llmc_agent.format.types import ParsedResponse, ToolCall


class OpenAINativeParser:
    """Parses OpenAI/Ollama native tool_calls field.
    
    Priority 1 parser - checks the structured API field first.
    """
    
    def can_parse(self, response: Any) -> bool:
        """Check for tool_calls in response."""
        if isinstance(response, dict):
            msg = response.get("message", response)
            tool_calls = msg.get("tool_calls")
            return bool(tool_calls)
        return False
    
    def parse(self, response: Any) -> ParsedResponse:
        """Extract tool calls from native field."""
        if isinstance(response, dict):
            msg = response.get("message", response)
            tool_calls_raw = msg.get("tool_calls", [])
            content = msg.get("content", "") or ""
        else:
            tool_calls_raw = []
            content = ""
        
        tool_calls = []
        for tc in tool_calls_raw:
            func = tc.get("function", tc)
            args = func.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            
            tool_calls.append(ToolCall(
                name=func.get("name", ""),
                arguments=args,
                id=tc.get("id"),
                raw=tc,
            ))
        
        return ParsedResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            raw_response=response,
        )
```

#### Task 1.2: Implement `XMLToolParser`

**File:** `llmc_agent/format/parsers/xml.py`

```python
"""Parser for XML tool calls in content (Anthropic, Qwen, custom templates)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from llmc_agent.format.types import ParsedResponse, ToolCall

logger = logging.getLogger(__name__)


class XMLToolParser:
    """Parses XML tool calls from response content.
    
    Handles multiple XML formats:
    - Anthropic: <tool_use>
    - Qwen: <tools>
    - Generic: <function_call>, <tool_call>
    
    Priority 2 parser - used when native field is empty.
    """
    
    # Patterns to detect XML tool blocks (regex, format_name)
    PATTERNS = [
        (r"<tool_use>(.*?)</tool_use>", "anthropic"),
        (r"<tools>(.*?)</tools>", "qwen"),
        (r"<function_call>(.*?)</function_call>", "generic"),
        (r"<tool_call>(.*?)</tool_call>", "generic"),
    ]
    
    def can_parse(self, response: Any) -> bool:
        """Check for XML tool patterns in content."""
        content = self._extract_content(response)
        if not content:
            return False
        
        for pattern, _ in self.PATTERNS:
            if re.search(pattern, content, re.DOTALL | re.IGNORECASE):
                return True
        return False
    
    def parse(self, response: Any) -> ParsedResponse:
        """Extract tool calls from XML in content."""
        content = self._extract_content(response)
        tool_calls = []
        
        for pattern, format_name in self.PATTERNS:
            matches = re.finditer(pattern, content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                block_content = match.group(1).strip()
                tc = self._parse_block(block_content, format_name)
                if tc:
                    tool_calls.append(tc)
                    logger.debug(f"Parsed {format_name} tool call: {tc.name}")
        
        # Clean content of parsed tool blocks
        clean_content = content
        for pattern, _ in self.PATTERNS:
            clean_content = re.sub(pattern, "", clean_content, flags=re.DOTALL | re.IGNORECASE)
        clean_content = clean_content.strip()
        
        return ParsedResponse(
            content=clean_content,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            raw_response=response,
        )
    
    def _extract_content(self, response: Any) -> str:
        """Extract content string from various response formats."""
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            msg = response.get("message", response)
            return msg.get("content", "") or ""
        return getattr(response, "content", "") or ""
    
    def _parse_block(self, block: str, format_name: str) -> ToolCall | None:
        """Parse a single XML block to ToolCall."""
        # Try JSON first (common: <tools>{"name": "...", "arguments": {...}}</tools>)
        try:
            data = json.loads(block)
            name = data.get("name")
            args = data.get("arguments", data.get("parameters", {}))
            if name:
                return ToolCall(name=name, arguments=args, raw=block)
        except json.JSONDecodeError:
            pass
        
        # Try line-based parsing (name on first line, JSON on rest)
        lines = block.strip().split("\n")
        if len(lines) >= 1:
            # Check if first line is just the tool name
            first_line = lines[0].strip()
            if first_line and not first_line.startswith("{"):
                try:
                    rest = "\n".join(lines[1:]).strip()
                    args = json.loads(rest) if rest else {}
                    return ToolCall(name=first_line, arguments=args, raw=block)
                except json.JSONDecodeError:
                    pass
        
        logger.warning(f"Could not parse {format_name} block: {block[:100]}...")
        return None
```

#### Task 1.3: Implement `CompositeParser`

**File:** `llmc_agent/format/parsers/composite.py`

```python
"""Composite parser that tries multiple parsers in priority order."""

from __future__ import annotations

import json
import logging
from typing import Any

from llmc_agent.format.types import ParsedResponse, ToolCall

logger = logging.getLogger(__name__)


class CompositeParser:
    """Tries multiple parsers in priority order.
    
    Default parser that handles any response format by trying:
    1. OpenAI native (tool_calls field)
    2. XML in content
    3. JSON in content (fallback)
    """
    
    def __init__(self, parsers: list | None = None):
        if parsers is None:
            from llmc_agent.format.parsers.openai import OpenAINativeParser
            from llmc_agent.format.parsers.xml import XMLToolParser
            
            self.parsers = [
                OpenAINativeParser(),
                XMLToolParser(),
            ]
        else:
            self.parsers = parsers
    
    def can_parse(self, response: Any) -> bool:
        """Always returns True - we're the catch-all."""
        return True
    
    def parse(self, response: Any) -> ParsedResponse:
        """Try parsers in order, return first successful result."""
        content = self._extract_content(response)
        
        for parser in self.parsers:
            if parser.can_parse(response):
                result = parser.parse(response)
                if result.tool_calls:
                    logger.info(f"Parsed {len(result.tool_calls)} tool call(s) via {parser.__class__.__name__}")
                    return result
        
        # No tool calls found by any parser
        return ParsedResponse(
            content=content,
            tool_calls=[],
            finish_reason="stop",
            raw_response=response,
        )
    
    def _extract_content(self, response: Any) -> str:
        """Extract content from response."""
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            msg = response.get("message", response)
            return msg.get("content", "") or ""
        return getattr(response, "content", "") or ""
```

#### Task 1.4: Parser `__init__.py`

**File:** `llmc_agent/format/parsers/__init__.py`

```python
"""Tool call parsers for UTP."""

from llmc_agent.format.parsers.composite import CompositeParser
from llmc_agent.format.parsers.openai import OpenAINativeParser
from llmc_agent.format.parsers.xml import XMLToolParser

__all__ = ["CompositeParser", "OpenAINativeParser", "XMLToolParser"]
```

---

### Phase 2: Adapters (3 hours)

#### Task 2.1: Implement `OpenAIResultAdapter`

**File:** `llmc_agent/format/adapters/openai.py`

```python
"""OpenAI/Ollama format adapters."""

from __future__ import annotations

import json
from typing import Any

from llmc_agent.format.types import ToolCall, ToolResult


class OpenAIResultAdapter:
    """Formats tool results for OpenAI/Ollama conversation."""
    
    def format_result(self, call: ToolCall, result: ToolResult) -> dict[str, Any]:
        """Convert result to OpenAI-style tool message."""
        content = result.result if result.success else {"error": result.error}
        
        return {
            "role": "tool",
            "tool_call_id": call.id or "",
            "content": json.dumps(content) if not isinstance(content, str) else content,
        }


class OpenAIDefinitionAdapter:
    """Formats tool definitions for OpenAI/Ollama API."""
    
    def format_tools(self, tools: list) -> list[dict[str, Any]]:
        """Convert internal Tool objects to OpenAI format."""
        result = []
        for tool in tools:
            # Handle both Tool dataclass and dict
            if hasattr(tool, "to_ollama_format"):
                result.append(tool.to_ollama_format())
            elif hasattr(tool, "name"):
                result.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": getattr(tool, "description", ""),
                        "parameters": getattr(tool, "parameters", {}),
                    }
                })
        return result
```

#### Task 2.2: Stub Anthropic adapters

**File:** `llmc_agent/format/adapters/anthropic.py`

```python
"""Anthropic format adapters (stub for future implementation)."""

from __future__ import annotations

from typing import Any

from llmc_agent.format.types import ToolCall, ToolResult


class AnthropicResultAdapter:
    """Formats tool results for Anthropic conversation.
    
    TODO: Implement when adding Anthropic backend.
    """
    
    def format_result(self, call: ToolCall, result: ToolResult) -> dict[str, Any]:
        """Convert result to Anthropic XML format."""
        raise NotImplementedError("Anthropic adapter not yet implemented")


class AnthropicDefinitionAdapter:
    """Formats tool definitions for Anthropic API.
    
    TODO: Implement when adding Anthropic backend.
    """
    
    def format_tools(self, tools: list) -> str:
        """Convert internal Tool objects to Anthropic XML format."""
        raise NotImplementedError("Anthropic adapter not yet implemented")
```

#### Task 2.3: Adapters `__init__.py`

**File:** `llmc_agent/format/adapters/__init__.py`

```python
"""Tool format adapters for UTP."""

from llmc_agent.format.adapters.openai import OpenAIDefinitionAdapter, OpenAIResultAdapter

__all__ = ["OpenAIDefinitionAdapter", "OpenAIResultAdapter"]
```

---

### Phase 3: Negotiator (2 hours)

#### Task 3.1: Implement `FormatNegotiator`

**File:** `llmc_agent/format/negotiator.py`

```python
"""Format negotiation and factory for adapters/parsers."""

from __future__ import annotations

from typing import Any

from llmc_agent.format.types import ToolFormat
from llmc_agent.format.parsers import CompositeParser, OpenAINativeParser, XMLToolParser
from llmc_agent.format.adapters import OpenAIDefinitionAdapter, OpenAIResultAdapter


class FormatNegotiator:
    """Central factory for format adapters and parsers.
    
    Determines appropriate format based on:
    1. Explicit configuration (profile.tools.*)
    2. Provider defaults
    """
    
    PROVIDER_DEFAULTS = {
        "openai": ToolFormat.OPENAI,
        "anthropic": ToolFormat.ANTHROPIC,
        "ollama": ToolFormat.OLLAMA,
        "gemini": ToolFormat.OPENAI,
    }
    
    def __init__(self, config: dict | None = None):
        self.config = config or {}
        # Cache adapters/parsers per format
        self._parser_cache: dict[ToolFormat, Any] = {}
        self._def_adapter_cache: dict[ToolFormat, Any] = {}
        self._result_adapter_cache: dict[ToolFormat, Any] = {}
    
    def detect_format(self, provider: str, model: str = "") -> ToolFormat:
        """Determine tool format for provider/model combination."""
        # Check explicit config first
        if self.config.get("call_parser"):
            fmt = self.config["call_parser"]
            if fmt != "auto":
                return ToolFormat(fmt)
        
        # Provider defaults
        return self.PROVIDER_DEFAULTS.get(provider.lower(), ToolFormat.AUTO)
    
    def get_call_parser(self, format: ToolFormat | None = None):
        """Get parser for extracting tool calls."""
        format = format or ToolFormat.AUTO
        
        if format not in self._parser_cache:
            if format == ToolFormat.AUTO:
                self._parser_cache[format] = CompositeParser()
            elif format in (ToolFormat.OPENAI, ToolFormat.OLLAMA):
                self._parser_cache[format] = CompositeParser([
                    OpenAINativeParser(),
                    XMLToolParser(),
                ])
            elif format == ToolFormat.ANTHROPIC:
                self._parser_cache[format] = CompositeParser([
                    XMLToolParser(),
                    OpenAINativeParser(),
                ])
            else:
                self._parser_cache[format] = CompositeParser()
        
        return self._parser_cache[format]
    
    def get_definition_adapter(self, format: ToolFormat | None = None):
        """Get adapter for formatting tool definitions."""
        format = format or ToolFormat.OPENAI
        
        if format not in self._def_adapter_cache:
            # All formats use OpenAI adapter for now (Ollama is OpenAI-compatible)
            self._def_adapter_cache[format] = OpenAIDefinitionAdapter()
        
        return self._def_adapter_cache[format]
    
    def get_result_adapter(self, format: ToolFormat | None = None):
        """Get adapter for formatting tool results."""
        format = format or ToolFormat.OPENAI
        
        if format not in self._result_adapter_cache:
            self._result_adapter_cache[format] = OpenAIResultAdapter()
        
        return self._result_adapter_cache[format]
```

#### Task 3.2: Package `__init__.py`

**File:** `llmc_agent/format/__init__.py`

```python
"""Unified Tool Protocol (UTP) - Format translation layer.

This package provides format-agnostic tool calling by:
1. Parsing tool calls from any response format (native, XML, JSON)
2. Normalizing to internal ToolCall representation
3. Formatting results back to provider-expected format

Usage:
    from llmc_agent.format import FormatNegotiator, ToolCall
    
    negotiator = FormatNegotiator()
    parser = negotiator.get_call_parser()
    parsed = parser.parse(ollama_response)
    for tc in parsed.tool_calls:
        # tc is a normalized ToolCall
        result = execute_tool(tc)
"""

from llmc_agent.format.negotiator import FormatNegotiator
from llmc_agent.format.types import ParsedResponse, ToolCall, ToolFormat, ToolResult

__all__ = [
    "FormatNegotiator",
    "ParsedResponse",
    "ToolCall",
    "ToolFormat",
    "ToolResult",
]
```

---

### Phase 4: Integration (6 hours)

#### Task 4.1: Modify `agent.py`

**File:** `llmc_agent/agent.py`

**Changes to `ask_with_tools()` method (lines 193-364):**

```python
# ADD at top of file:
from llmc_agent.format import FormatNegotiator, ToolCall as UTPToolCall

# ADD in Agent.__init__():
    self.format_negotiator = FormatNegotiator()

# REPLACE the tool loop section (around lines 262-336):
    async def ask_with_tools(
        self,
        question: str,
        session: Session | None = None,
        max_tool_rounds: int = 5,
    ) -> AgentResponse:
        """Ask with tool support (Walk/Run phases)."""
        from llmc_agent.tools import detect_intent_tier

        # ... (keep existing setup code through line 271)

        # Get parser for this provider
        parser = self.format_negotiator.get_call_parser()
        result_adapter = self.format_negotiator.get_result_adapter()

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

            # === NEW: Use UTP parser ===
            parsed = parser.parse(response.raw_response)
            
            if not parsed.tool_calls:
                # No tool calls, we're done
                final_content = parsed.content or response.content
                break

            # Execute tool calls
            for tc in parsed.tool_calls:
                tool = self.tools.get_tool(tc.name)
                if not tool:
                    # Unknown tool - inform model
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id or "",
                        "content": json.dumps({"error": f"Tool '{tc.name}' not found"})
                    })
                    continue

                # Check tier
                if not self.tools.is_tool_available(tc.name):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id or "",
                        "content": json.dumps({
                            "error": f"Tool '{tc.name}' not available at tier {self.tools.current_tier.name}"
                        })
                    })
                    continue

                # Execute tool
                try:
                    if asyncio.iscoroutinefunction(tool.function):
                        result = await tool.function(**tc.arguments)
                    else:
                        result = tool.function(**tc.arguments)

                    tool_call = ToolCall(
                        name=tc.name,
                        arguments=tc.arguments,
                        result=result,
                    )
                    all_tool_calls.append(tool_call)

                    # Add assistant message with tool call
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tc.id or f"call_{round_num}_{tc.name}",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}
                        }],
                    })
                    
                    # Add tool result
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id or f"call_{round_num}_{tc.name}",
                        "content": json.dumps(result),
                    })

                except Exception as e:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id or "",
                        "content": json.dumps({"error": str(e)}),
                    })
        else:
            # Max rounds reached
            final_content = parsed.content if "parsed" in dir() else "Max tool rounds reached."

        # ... (keep existing session update and return)
```

#### Task 4.2: Modify `ollama.py` to expose raw response

**File:** `llmc_agent/backends/ollama.py`

**Changes to `GenerateResponse` (in `base.py` or inline):**

```python
# ADD to GenerateResponse dataclass:
    raw_response: Any = None  # Full API response for parser access
```

**Changes to `generate_with_tools()` (line 161-168):**

```python
        return GenerateResponse(
            content=content,
            tokens_prompt=data.get("prompt_eval_count", 0),
            tokens_completion=data.get("eval_count", 0),
            model=data.get("model", request.model),
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            raw_response=data,  # ADD THIS LINE
        )
```

---

### Phase 5: Configuration (2 hours)

#### Task 5.1: Add config schema

**File:** `llmc_agent/config.py`

**Add to profile loading:**

```python
@dataclass
class ToolsConfig:
    """Tool calling format configuration."""
    definition_format: str = "openai"
    call_parser: str = "auto"
    result_format: str = "openai"


@dataclass
class ProfileConfig:
    # ... existing fields ...
    tools: ToolsConfig = field(default_factory=ToolsConfig)
```

#### Task 5.2: Document config in `llmc.toml`

```toml
[profiles.boxxie-tools]
provider = "ollama"
model = "qwen3-next-80b-tools"
url = "http://athena:11434"

# Tool calling format (optional - defaults shown)
[profiles.boxxie-tools.tools]
definition_format = "openai"  # How to send tool definitions
call_parser = "auto"          # "auto" | "openai" | "anthropic_xml" | "qwen_xml"
result_format = "openai"      # How to format tool results
```

---

### Phase 6: Testing (4 hours)

#### Task 6.1: Unit tests for parsers

**File:** `tests/agent/format/test_parsers.py`

```python
"""Unit tests for UTP parsers."""

import pytest
from llmc_agent.format.parsers import CompositeParser, OpenAINativeParser, XMLToolParser


class TestOpenAINativeParser:
    def test_can_parse_with_tool_calls(self):
        response = {"message": {"tool_calls": [{"function": {"name": "test"}}]}}
        parser = OpenAINativeParser()
        assert parser.can_parse(response) is True
    
    def test_can_parse_without_tool_calls(self):
        response = {"message": {"content": "Hello"}}
        parser = OpenAINativeParser()
        assert parser.can_parse(response) is False
    
    def test_parse_extracts_tool_call(self):
        response = {
            "message": {
                "tool_calls": [{
                    "id": "call_123",
                    "function": {
                        "name": "search_code",
                        "arguments": '{"query": "test"}'
                    }
                }]
            }
        }
        parser = OpenAINativeParser()
        parsed = parser.parse(response)
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].name == "search_code"
        assert parsed.tool_calls[0].arguments == {"query": "test"}


class TestXMLToolParser:
    def test_can_parse_qwen_format(self):
        response = {"message": {"content": '<tools>{"name": "test"}</tools>'}}
        parser = XMLToolParser()
        assert parser.can_parse(response) is True
    
    def test_parse_qwen_format(self):
        response = {
            "message": {
                "content": 'I will search.\n\n<tools>\n{"name": "search_code", "arguments": {"query": "auth"}}\n</tools>'
            }
        }
        parser = XMLToolParser()
        parsed = parser.parse(response)
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].name == "search_code"
        assert parsed.tool_calls[0].arguments == {"query": "auth"}
        assert "I will search." in parsed.content
    
    def test_parse_anthropic_format(self):
        response = {"message": {"content": '<tool_use>{"name": "read_file", "arguments": {"path": "foo.py"}}</tool_use>'}}
        parser = XMLToolParser()
        parsed = parser.parse(response)
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].name == "read_file"


class TestCompositeParser:
    def test_tries_native_first(self):
        """Native parser should be tried before XML."""
        response = {
            "message": {
                "tool_calls": [{"function": {"name": "native_tool"}}],
                "content": '<tools>{"name": "xml_tool"}</tools>'
            }
        }
        parser = CompositeParser()
        parsed = parser.parse(response)
        # Should find native tool first and return
        assert any(tc.name == "native_tool" for tc in parsed.tool_calls)
    
    def test_falls_back_to_xml(self):
        """Should use XML parser when native is empty."""
        response = {"message": {"content": '<tools>{"name": "xml_only"}</tools>'}}
        parser = CompositeParser()
        parsed = parser.parse(response)
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].name == "xml_only"
    
    def test_handles_malformed_gracefully(self):
        """Should not crash on malformed input."""
        response = {"message": {"content": "<tools>broken json</tools>"}}
        parser = CompositeParser()
        parsed = parser.parse(response)  # Should not raise
        assert parsed.tool_calls == []
```

#### Task 6.2: Integration test with Boxxie

**File:** `tests/agent/test_boxxie_integration.py`

```python
"""Integration test for Boxxie tool calling."""

import pytest
from unittest.mock import AsyncMock, patch

from llmc_agent.agent import Agent
from llmc_agent.config import load_config


@pytest.mark.integration
@pytest.mark.asyncio
async def test_boxxie_xml_tool_call():
    """Test that XML tool calls from Boxxie are parsed and executed."""
    # Mock Ollama response with XML tool call
    mock_response = {
        "message": {
            "content": 'I will search for that.\n\n<tools>\n{"name": "search_code", "arguments": {"query": "authentication"}}\n</tools>',
            "tool_calls": None,  # No native tool calls
        },
        "done": True,
        "eval_count": 50,
        "prompt_eval_count": 100,
    }
    
    config = load_config()
    agent = Agent(config)
    
    with patch.object(agent.ollama, "generate_with_tools") as mock_gen:
        # First call returns XML tool call, second returns final answer
        mock_gen.side_effect = [
            AsyncMock(return_value=mock_response)(),
            AsyncMock(return_value={
                "message": {"content": "Found 3 results in auth.py", "tool_calls": None},
                "done": True,
            })(),
        ]
        
        # This should parse the XML and execute the tool
        response = await agent.ask_with_tools("Search for authentication code")
        
        # Verify tool was called
        assert len(response.tool_calls) >= 1
        assert response.tool_calls[0].name == "search_code"
```

---

## 5. Validation Checklist

### 5.1 Pre-Implementation
- [ ] HLD reviewed and understood
- [ ] Existing `llmc_agent/` code reviewed
- [ ] Test environment ready (Boxxie on athena)

### 5.2 Post-Implementation
- [ ] All unit tests pass (`pytest tests/agent/format/ -v`)
- [ ] Integration test passes with Boxxie
- [ ] No regression in existing tool calling (if any worked before)
- [ ] `bx "search for auth code"` executes tool and returns results
- [ ] Config documentation updated

### 5.3 UAT Sign-Off
- [ ] UAT-C1: Boxxie executes tool calls ✅
- [ ] UAT-C2: Results injected into conversation ✅
- [ ] UAT-C4: Tier enforcement works ✅
- [ ] UAT-I1: XML tool calls parsed correctly ✅

---

## 6. Effort Summary

| Phase | Tasks | Estimate |
|-------|-------|----------|
| Phase 0: Foundation | Types, protocols | 4 hours |
| Phase 1: Parsers | OpenAI, XML, Composite | 6 hours |
| Phase 2: Adapters | OpenAI result/def adapters | 3 hours |
| Phase 3: Negotiator | Factory class | 2 hours |
| Phase 4: Integration | Modify agent.py, ollama.py | 6 hours |
| Phase 5: Configuration | Config schema, docs | 2 hours |
| Phase 6: Testing | Unit + integration tests | 4 hours |
| **Total** | | **27 hours** |

---

## 7. References

- `DOCS/planning/HLD_Unified_Tool_Protocol.md` - Architecture design
- `DOCS/planning/UAT_Unified_Tool_Protocol.md` - Acceptance testing
- `llmc_agent/tools.py` - Existing tier system
- `llmc_agent/agent.py` - Current agent implementation
- `.gemini/turnovers/TURNOVER_Boxxie_StrixHalo_Vulkan_Setup.md` - Problem context
