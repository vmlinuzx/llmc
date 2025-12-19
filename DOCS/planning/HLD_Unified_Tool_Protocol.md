# High-Level Design: Unified Tool Protocol (UTP)

**Version:** 1.0  
**Author:** Antigravity (with Dave)  
**Date:** 2025-12-18  
**Status:** Draft – Architectural Review  
**Related:** `SDD_Tool_Envelope_v1.2.md`, `llmc_agent/tools.py`, `llmc_agent/agent.py`

---

## Abstract

This document presents a unified architecture for LLM tool calling that reconciles three historically divergent concerns:

1. **Tool Format Translation** – Converting between provider-specific wire formats (OpenAI JSON, Anthropic XML, Ollama native)
2. **Progressive Disclosure** – Tiered capability exposure based on intent detection and trust level
3. **Tool Envelope (TE)** – Response formatting and token-efficient output structuring

The key insight is that these three concerns operate at different layers of abstraction and should be composed, not conflated. We propose the **Unified Tool Protocol (UTP)** as the internal representation that all external formats translate to and from.

---

## 1. Problem Statement

### 1.1 The Format Fragmentation Problem

The LLM ecosystem has converged on tool calling as the primary mechanism for agent capability, but diverged on implementation:

| Provider | Definition Format | Invocation Format | Result Format |
|----------|-------------------|-------------------|---------------|
| **OpenAI** | JSON Schema in `tools` array | `tool_calls` field with `function.name`, `function.arguments` | `role: tool` message with `tool_call_id` |
| **Anthropic** | XML in system prompt or `tools` array | `<tool_use>` blocks in content with `<thinking>` separation | `<tool_result>` blocks in next user message |
| **Ollama** | OpenAI-compatible JSON | OpenAI-compatible `tool_calls` (if model supports) OR XML in content | OpenAI-compatible `role: tool` |
| **Qwen/Custom** | Template-dependent | Often XML in content (`<tools>`, `<function_call>`) | Template-dependent |

**The core tension:** Models are trained on massive corpora of API interactions. Qwen3-Next-80B has seen millions of OpenAI-format tool calls AND Anthropic-format XML. The model's "native" format depends on:
- Which template was applied during fine-tuning
- Which system prompt patterns activate which training
- Runtime template configuration (modelfile)

### 1.2 The Progressive Disclosure Impedance

LLMC already has a sophisticated progressive disclosure system (Tool Tiers: CRAWL → WALK → RUN). But this operates on **internal tool representations**, not on wire formats:

```
Current Architecture:
  
  User Question → Intent Detection → Tier Unlock → Available Tools
                                                        ↓
                                              to_ollama_format() ← OpenAI JSON only!
                                                        ↓
                                              Ollama API (expects tool_calls response)
                                                        ↓
                                              ??? (breaks if model outputs XML)
```

The tier system works perfectly. The problem is the **format boundary** between:
- What we send to the model (tool definitions)
- What the model sends back (tool invocations)
- What we inject into the conversation (tool results)

### 1.3 The Tool Envelope Orthogonality

Tool Envelope (TE) solves a different problem: **output formatting and token efficiency**. TE intercepts shell commands and returns MPD-formatted responses with breadcrumbs.

```
TE Architecture:
  
  LLM runs: te grep "pattern"
       ↓
  TE intercepts, runs rg internally
       ↓
  TE returns: # TE_BEGIN_META → ranked results → # TE: more available
```

This is **orthogonal** to tool calling format. TE operates on **tool output**, not tool invocation. A tool can be:
- Called via OpenAI format → returns TE-formatted output
- Called via Anthropic XML → returns TE-formatted output
- Called via raw shell → returns TE-formatted output

The formats don't conflict; they compose.

---

## 2. Theoretical Framework

### 2.1 Tool Calling as a Protocol, Not a Format

Tool calling is a **multi-turn protocol** with distinct phases:

```
Phase 1: Definition Disclosure
  System: "You have access to these tools: [...]"
  
Phase 2: Intent Expression  
  Model: "I need to search the codebase for X"
  
Phase 3: Invocation Request
  Model: [tool_call(search_code, {query: "X"})]
                     ↑
            This is what varies by format
            
Phase 4: Execution
  Runtime: execute(search_code, {query: "X"}) → result
  
Phase 5: Result Injection
  System: [tool_result(id, result)]
  
Phase 6: Continuation
  Model: "Based on the search results, I see that..."
```

**Key insight:** Only Phases 1, 3, and 5 touch wire format. The rest is internal.

### 2.2 The Adapter Pattern at Both Boundaries

We need format translation at two boundaries:

```
┌───────────────────────────────────────────────────────────────────┐
│                                                                    │
│  Internal Tool Representation (UTP)                                │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Tool:                                                      │   │
│  │    name: str                                                │   │
│  │    description: str                                         │   │
│  │    parameters: JSONSchema                                   │   │
│  │    tier: ToolTier                                          │   │
│  │    requires_confirmation: bool                             │   │
│  └────────────────────────────────────────────────────────────┘   │
│                           ↓                                        │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  ToolDefinitionAdapter (Outbound)                          │   │
│  │    • to_openai_format(tools) → [{"type": "function", ...}] │   │
│  │    • to_anthropic_format(tools) → XML in system prompt     │   │
│  │    • to_ollama_format(tools) → OpenAI-compatible           │   │
│  └────────────────────────────────────────────────────────────┘   │
│                           ↓                                        │
│                    Provider API                                    │
│                           ↓                                        │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Model Response (varies by provider/model)                  │   │
│  │    • OpenAI: response.tool_calls = [...]                   │   │
│  │    • Anthropic: <tool_use> in content                      │   │
│  │    • Qwen: <tools> in content                              │   │
│  │    • Mixed: some in tool_calls, some in content            │   │
│  └────────────────────────────────────────────────────────────┘   │
│                           ↓                                        │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  ToolCallParser (Inbound)                                   │   │
│  │    • parse_openai(response) → [ToolCall(...)]              │   │
│  │    • parse_anthropic_xml(content) → [ToolCall(...)]        │   │
│  │    • parse_qwen_xml(content) → [ToolCall(...)]             │   │
│  │    • parse_auto(response, provider) → [ToolCall(...)]      │   │
│  └────────────────────────────────────────────────────────────┘   │
│                           ↓                                        │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Internal ToolCall (UTP)                                    │   │
│  │    name: str                                                │   │
│  │    arguments: dict[str, Any]                               │   │
│  │    id: str | None  # For result correlation                 │   │
│  └────────────────────────────────────────────────────────────┘   │
│                           ↓                                        │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  ToolRegistry (Tier Check + Execution)                      │   │
│  │    • is_tool_available(name) → bool                        │   │
│  │    • execute(tool_call) → result                           │   │
│  └────────────────────────────────────────────────────────────┘   │
│                           ↓                                        │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  ToolResultAdapter (Outbound)                               │   │
│  │    • to_openai_message(id, result) → {"role": "tool", ...} │   │
│  │    • to_anthropic_message(id, result) → <tool_result>      │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                    │
└───────────────────────────────────────────────────────────────────┘
```

### 2.3 The Parsing Hierarchy

Not all tool call formats are equally reliable. We propose a **parsing hierarchy** with fallbacks:

```
Priority 1: Native API Fields
  response.tool_calls exists and is populated
  → Use directly (highest confidence)
  
Priority 2: Structured XML Blocks
  response.content contains <tool_use>, <tools>, or <function_call> blocks
  → Parse XML, extract name/arguments (medium confidence)
  
Priority 3: JSON in Content
  response.content contains JSON that matches tool call schema
  → Parse JSON, validate against known tools (lower confidence)
  
Priority 4: Heuristic Detection
  response.content contains patterns like "I'll use the X tool..."
  → Extract intent, prompt for confirmation (lowest confidence)
```

**Why the hierarchy matters:** A model might output BOTH `tool_calls` AND mention tools in content. The native field takes precedence. A model might output malformed XML but valid JSON inside it. We should try multiple parsers.

### 2.4 The Relationship to Training Data

Models like Qwen3-Next-80B are trained on:
- OpenAI API logs (massive volume, function calling format)
- Anthropic API logs (XML tool_use format)
- Open-source chat datasets (various formats)
- Code repositories showing API usage patterns

**Key insight:** The model "knows" multiple formats. The format it outputs depends on:

1. **System prompt activation:** "Use the following tools..." vs "<tools>" in prompt
2. **Template override:** Modelfile TEMPLATE directive
3. **In-context examples:** Tool usage in conversation history
4. **Token probability:** What's most likely given context

A well-designed system should:
- Send definitions in the format the model expects (template-dependent)
- Parse responses in ANY format the model might output
- Normalize to internal representation before execution

---

## 3. Architecture

### 3.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           llmc_agent                                     │
│                                                                          │
│  ┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐   │
│  │   Agent     │────→│   ToolRegistry   │────→│   Tool Execution    │   │
│  │             │     │  (Tier System)   │     │   (TE Integration)  │   │
│  └──────┬──────┘     └──────────────────┘     └─────────────────────┘   │
│         │                                                                │
│         │            ┌──────────────────────────────────────────────┐   │
│         │            │         format/ (NEW)                         │   │
│         │            │                                               │   │
│         │            │  ┌────────────────────────────────────────┐  │   │
│         └───────────→│  │  FormatNegotiator                      │  │   │
│                      │  │    • detect_format(provider, model)    │  │   │
│                      │  │    • get_definition_adapter(format)    │  │   │
│                      │  │    • get_call_parser(format)           │  │   │
│                      │  │    • get_result_adapter(format)        │  │   │
│                      │  └────────────────────────────────────────┘  │   │
│                      │                                               │   │
│                      │  ┌────────────────────────────────────────┐  │   │
│                      │  │  ToolDefinitionAdapter (Protocol)       │  │   │
│                      │  │    .format_tools(tools) → provider fmt  │  │   │
│                      │  │                                         │  │   │
│                      │  │  Implementations:                       │  │   │
│                      │  │    • OpenAIDefinitionAdapter            │  │   │
│                      │  │    • AnthropicDefinitionAdapter         │  │   │
│                      │  │    • OllamaDefinitionAdapter            │  │   │
│                      │  └────────────────────────────────────────┘  │   │
│                      │                                               │   │
│                      │  ┌────────────────────────────────────────┐  │   │
│                      │  │  ToolCallParser (Protocol)              │  │   │
│                      │  │    .parse(response) → list[ToolCall]    │  │   │
│                      │  │    .can_parse(response) → bool          │  │   │
│                      │  │                                         │  │   │
│                      │  │  Implementations:                       │  │   │
│                      │  │    • OpenAINativeParser (tool_calls)    │  │   │
│                      │  │    • AnthropicXMLParser (<tool_use>)    │  │   │
│                      │  │    • QwenXMLParser (<tools>)            │  │   │
│                      │  │    • JSONContentParser (fallback)       │  │   │
│                      │  │    • CompositeParser (tries all)        │  │   │
│                      │  └────────────────────────────────────────┘  │   │
│                      │                                               │   │
│                      │  ┌────────────────────────────────────────┐  │   │
│                      │  │  ToolResultAdapter (Protocol)           │  │   │
│                      │  │    .format_result(call, result) → msg   │  │   │
│                      │  │                                         │  │   │
│                      │  │  Implementations:                       │  │   │
│                      │  │    • OpenAIResultAdapter                │  │   │
│                      │  │    • AnthropicResultAdapter             │  │   │
│                      │  └────────────────────────────────────────┘  │   │
│                      │                                               │   │
│                      └──────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    backends/                                      │    │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐ │    │
│  │  │ OllamaBackend  │  │ OpenAIBackend  │  │ AnthropicBackend   │ │    │
│  │  │               ←──format module───→                         │ │    │
│  │  └────────────────┘  └────────────────┘  └────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Integration with Progressive Disclosure

Progressive disclosure remains **unchanged** at the tier level. The format layer sits **between** the tier system and the wire:

```
Current Flow:
  [User Question] → [Intent Detection] → [Tier Unlock] → [Tools at Tier]
                                                               ↓
                                                    [to_ollama_format()]  ← REPLACE THIS
                                                               ↓
                                                       [Ollama API]
                                                               ↓
                                                    [response.tool_calls]  ← AND THIS
                                                               ↓
                                                       [Execute + Loop]

New Flow:
  [User Question] → [Intent Detection] → [Tier Unlock] → [Tools at Tier]
                                                               ↓
                                                    [FormatNegotiator.get_definition_adapter()]
                                                               ↓
                                                    [DefinitionAdapter.format_tools()]
                                                               ↓
                                                       [Backend API]
                                                               ↓
                                                    [FormatNegotiator.get_call_parser()]
                                                               ↓
                                                    [CallParser.parse(response)]
                                                               ↓
                                                    [Internal ToolCall List]
                                                               ↓
                                                    [Tier Check: is_tool_available()]
                                                               ↓
                                                       [Execute + Loop]
```

**Critical point:** The tier system never sees wire formats. It operates entirely on internal `Tool` and `ToolCall` objects.

### 3.3 Integration with Tool Envelope

TE operates at the **tool output** level, not the invocation level:

```
Tool Invocation (UTP/format layer)     Tool Output (TE layer)
──────────────────────────────────     ──────────────────────────
ToolCall(                              # TE_BEGIN_META
  name="search_code",           →      {"v":1,"cmd":"search","matches":47}
  arguments={"query":"auth"}           # TE_END_META
)                                      
                                       tools/auth/handler.py:15: def auth()
                                       tools/auth/service.py:89: auth.validate()
                                       
                                       # TE: 42 more in tools/auth/
```

**Composition, not conflict:** The format adapters handle how tools are called. TE handles how tool results are formatted. These are independent concerns that compose cleanly.

### 3.4 Configuration Model

```toml
# llmc.toml

[profiles.boxxie]
provider = "ollama"
model = "qwen3-next-80b-tools"
url = "http://athena:11434"

# Tool calling format configuration
[profiles.boxxie.tools]
definition_format = "openai"      # How to send tool definitions
call_parser = "auto"              # How to parse tool calls ("auto", "openai", "anthropic_xml", "qwen_xml")
result_format = "openai"          # How to format tool results

[profiles.claude-agent]
provider = "anthropic"
model = "claude-sonnet-4-20250514"

[profiles.claude-agent.tools]
definition_format = "anthropic"
call_parser = "anthropic_xml"
result_format = "anthropic"
```

**Format auto-detection:**
- If `call_parser = "auto"`, try parsers in priority order
- If provider is known (anthropic, openai), use provider's parser first
- Fall back to content parsing if native field is empty

---

## 4. Detailed Design

### 4.1 Internal Representations (UTP)

```python
# llmc_agent/format/types.py

from dataclasses import dataclass, field
from typing import Any, Protocol
from enum import Enum


class ToolFormat(Enum):
    """Supported tool calling formats."""
    OPENAI = "openai"           # OpenAI-style JSON schema
    ANTHROPIC = "anthropic"     # Anthropic XML format
    OLLAMA = "ollama"           # Ollama (OpenAI-compatible)
    AUTO = "auto"               # Auto-detect


@dataclass
class ToolCall:
    """Internal representation of a tool call (UTP).
    
    This is the unified format that all parsers produce
    and all executors consume.
    """
    name: str
    arguments: dict[str, Any]
    id: str | None = None       # For result correlation
    raw: Any = None             # Original format (for debugging)


@dataclass
class ToolResult:
    """Internal representation of a tool result (UTP)."""
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
    content: str                         # Text content (may be empty)
    tool_calls: list[ToolCall]           # Parsed tool calls (may be empty)
    finish_reason: str                   # "stop", "tool_calls", "length"
    raw_response: Any                    # Original response object
```

### 4.2 Protocol Definitions

```python
# llmc_agent/format/protocols.py

from typing import Protocol, runtime_checkable
from llmc_agent.format.types import ToolCall, ToolResult, ParsedResponse


@runtime_checkable
class ToolDefinitionAdapter(Protocol):
    """Converts internal tool definitions to provider format."""
    
    def format_tools(self, tools: list[Tool]) -> Any:
        """Convert tools to provider-specific format.
        
        Returns:
            Format depends on provider:
            - OpenAI/Ollama: list[dict] for `tools` param
            - Anthropic: str for system prompt injection
        """
        ...
    
    def format_system_prompt(self, base_prompt: str, tools: list[Tool]) -> str:
        """Optionally modify system prompt for tool awareness.
        
        Some formats (Anthropic) may inject tool info into system prompt.
        Others (OpenAI) leave it unchanged.
        """
        ...


@runtime_checkable
class ToolCallParser(Protocol):
    """Extracts tool calls from model responses."""
    
    def can_parse(self, response: Any) -> bool:
        """Check if this parser can handle the response."""
        ...
    
    def parse(self, response: Any) -> ParsedResponse:
        """Parse response and extract tool calls.
        
        Must handle:
        - Native API fields (response.tool_calls)
        - XML in content (<tool_use>, <tools>, etc.)
        - JSON in content
        - Mixed formats
        
        Returns ParsedResponse with extracted tool_calls.
        """
        ...


@runtime_checkable  
class ToolResultAdapter(Protocol):
    """Converts tool results to provider message format."""
    
    def format_result(self, call: ToolCall, result: ToolResult) -> dict[str, Any]:
        """Convert result to provider-specific message format.
        
        Returns:
            Message dict suitable for appending to conversation.
        """
        ...
```

### 4.3 Parser Implementations

```python
# llmc_agent/format/parsers/openai.py

import json
from llmc_agent.format.types import ToolCall, ParsedResponse


class OpenAINativeParser:
    """Parses OpenAI/Ollama native tool_calls field."""
    
    def can_parse(self, response: Any) -> bool:
        """Check for tool_calls in response."""
        if hasattr(response, 'tool_calls') and response.tool_calls:
            return True
        if isinstance(response, dict):
            msg = response.get('message', response)
            return bool(msg.get('tool_calls'))
        return False
    
    def parse(self, response: Any) -> ParsedResponse:
        """Extract tool calls from native field."""
        # Handle both object and dict responses
        if isinstance(response, dict):
            msg = response.get('message', response)
            tool_calls_raw = msg.get('tool_calls', [])
            content = msg.get('content', '')
        else:
            tool_calls_raw = getattr(response, 'tool_calls', []) or []
            content = getattr(response, 'content', '') or ''
        
        tool_calls = []
        for tc in tool_calls_raw:
            func = tc.get('function', tc)
            args = func.get('arguments', {})
            if isinstance(args, str):
                args = json.loads(args)
            
            tool_calls.append(ToolCall(
                name=func.get('name'),
                arguments=args,
                id=tc.get('id'),
                raw=tc,
            ))
        
        return ParsedResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason='tool_calls' if tool_calls else 'stop',
            raw_response=response,
        )
```

```python
# llmc_agent/format/parsers/xml.py

import re
import json
from xml.etree import ElementTree as ET
from llmc_agent.format.types import ToolCall, ParsedResponse


class XMLToolParser:
    """Parses XML tool calls from content.
    
    Handles multiple XML formats:
    - Anthropic: <tool_use>
    - Qwen: <tools>
    - Generic: <function_call>, <tool_call>
    """
    
    # Patterns to detect XML tool blocks
    PATTERNS = [
        (r'<tool_use>(.*?)</tool_use>', 'anthropic'),
        (r'<tools>(.*?)</tools>', 'qwen'),
        (r'<function_call>(.*?)</function_call>', 'generic'),
        (r'<tool_call>(.*?)</tool_call>', 'generic'),
    ]
    
    def can_parse(self, response: Any) -> bool:
        """Check for XML tool patterns in content."""
        content = self._get_content(response)
        if not content:
            return False
        
        for pattern, _ in self.PATTERNS:
            if re.search(pattern, content, re.DOTALL):
                return True
        return False
    
    def parse(self, response: Any) -> ParsedResponse:
        """Extract tool calls from XML in content."""
        content = self._get_content(response)
        tool_calls = []
        
        for pattern, format_type in self.PATTERNS:
            matches = re.finditer(pattern, content, re.DOTALL)
            for match in matches:
                xml_content = match.group(1)
                try:
                    tc = self._parse_xml_block(xml_content, format_type)
                    if tc:
                        tool_calls.append(tc)
                except Exception:
                    # Try JSON fallback inside XML
                    tc = self._try_json_in_block(xml_content)
                    if tc:
                        tool_calls.append(tc)
        
        # Clean content of parsed tool blocks
        clean_content = content
        for pattern, _ in self.PATTERNS:
            clean_content = re.sub(pattern, '', clean_content, flags=re.DOTALL)
        clean_content = clean_content.strip()
        
        return ParsedResponse(
            content=clean_content,
            tool_calls=tool_calls,
            finish_reason='tool_calls' if tool_calls else 'stop',
            raw_response=response,
        )
    
    def _get_content(self, response: Any) -> str:
        """Extract content string from response."""
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            return response.get('message', {}).get('content', '') or response.get('content', '')
        return getattr(response, 'content', '') or ''
    
    def _parse_xml_block(self, xml_content: str, format_type: str) -> ToolCall | None:
        """Parse a single XML block."""
        # Try to parse as JSON first (common pattern)
        try:
            data = json.loads(xml_content.strip())
            return ToolCall(
                name=data.get('name'),
                arguments=data.get('arguments', data.get('parameters', {})),
                raw=xml_content,
            )
        except json.JSONDecodeError:
            pass
        
        # Fall back to XML parsing
        try:
            root = ET.fromstring(f'<root>{xml_content}</root>')
            name = None
            args = {}
            
            for child in root:
                if child.tag == 'name':
                    name = child.text
                elif child.tag in ('arguments', 'parameters'):
                    try:
                        args = json.loads(child.text or '{}')
                    except:
                        args = {child.tag: child.text}
                else:
                    args[child.tag] = child.text
            
            if name:
                return ToolCall(name=name, arguments=args, raw=xml_content)
        except ET.ParseError:
            pass
        
        return None
    
    def _try_json_in_block(self, content: str) -> ToolCall | None:
        """Try to extract JSON from a block that failed XML parsing."""
        # Look for JSON object pattern
        match = re.search(r'\{[^{}]*\}', content)
        if match:
            try:
                data = json.loads(match.group())
                if 'name' in data:
                    return ToolCall(
                        name=data['name'],
                        arguments=data.get('arguments', {}),
                        raw=content,
                    )
            except json.JSONDecodeError:
                pass
        return None
```

```python
# llmc_agent/format/parsers/composite.py

from llmc_agent.format.types import ParsedResponse


class CompositeParser:
    """Tries multiple parsers in priority order.
    
    This is the default parser that handles any response format.
    """
    
    def __init__(self, parsers: list = None):
        if parsers is None:
            from llmc_agent.format.parsers.openai import OpenAINativeParser
            from llmc_agent.format.parsers.xml import XMLToolParser
            
            self.parsers = [
                OpenAINativeParser(),  # Priority 1: Native API field
                XMLToolParser(),       # Priority 2: XML in content
            ]
        else:
            self.parsers = parsers
    
    def can_parse(self, response: Any) -> bool:
        """Always returns True - we're the catch-all."""
        return True
    
    def parse(self, response: Any) -> ParsedResponse:
        """Try parsers in order, merge results."""
        all_tool_calls = []
        content = ''
        
        for parser in self.parsers:
            if parser.can_parse(response):
                result = parser.parse(response)
                all_tool_calls.extend(result.tool_calls)
                if not content and result.content:
                    content = result.content
        
        # Deduplicate by tool name + arguments
        seen = set()
        unique_calls = []
        for tc in all_tool_calls:
            key = (tc.name, json.dumps(tc.arguments, sort_keys=True))
            if key not in seen:
                seen.add(key)
                unique_calls.append(tc)
        
        return ParsedResponse(
            content=content,
            tool_calls=unique_calls,
            finish_reason='tool_calls' if unique_calls else 'stop',
            raw_response=response,
        )
```

### 4.4 Format Negotiator

```python
# llmc_agent/format/negotiator.py

from llmc_agent.format.types import ToolFormat
from llmc_agent.format.protocols import (
    ToolDefinitionAdapter,
    ToolCallParser,
    ToolResultAdapter,
)


class FormatNegotiator:
    """Central factory for format adapters and parsers.
    
    Determines appropriate format based on:
    1. Explicit configuration (profile.tools.*)
    2. Provider defaults
    3. Model-specific overrides
    """
    
    # Provider defaults
    PROVIDER_DEFAULTS = {
        'openai': ToolFormat.OPENAI,
        'anthropic': ToolFormat.ANTHROPIC,
        'ollama': ToolFormat.OLLAMA,
        'gemini': ToolFormat.OPENAI,  # Gemini uses OpenAI-compatible
    }
    
    # Models that need special handling
    MODEL_OVERRIDES = {
        'qwen': ToolFormat.OLLAMA,      # Qwen via Ollama
        'llama': ToolFormat.OLLAMA,     # Llama via Ollama
        'claude': ToolFormat.ANTHROPIC,
        'gpt-': ToolFormat.OPENAI,
    }
    
    def __init__(self, config: dict = None):
        self.config = config or {}
    
    def detect_format(self, provider: str, model: str) -> ToolFormat:
        """Determine tool format for provider/model combination."""
        # Check explicit configuration first
        if self.config.get('definition_format'):
            return ToolFormat(self.config['definition_format'])
        
        # Check model-specific overrides
        model_lower = model.lower()
        for pattern, fmt in self.MODEL_OVERRIDES.items():
            if pattern in model_lower:
                return fmt
        
        # Fall back to provider defaults
        return self.PROVIDER_DEFAULTS.get(provider, ToolFormat.AUTO)
    
    def get_definition_adapter(self, format: ToolFormat) -> ToolDefinitionAdapter:
        """Get adapter for formatting tool definitions."""
        from llmc_agent.format.adapters.openai import OpenAIDefinitionAdapter
        from llmc_agent.format.adapters.anthropic import AnthropicDefinitionAdapter
        
        if format in (ToolFormat.OPENAI, ToolFormat.OLLAMA):
            return OpenAIDefinitionAdapter()
        elif format == ToolFormat.ANTHROPIC:
            return AnthropicDefinitionAdapter()
        else:
            return OpenAIDefinitionAdapter()  # Default
    
    def get_call_parser(self, format: ToolFormat) -> ToolCallParser:
        """Get parser for extracting tool calls."""
        from llmc_agent.format.parsers.openai import OpenAINativeParser
        from llmc_agent.format.parsers.xml import XMLToolParser
        from llmc_agent.format.parsers.composite import CompositeParser
        
        if format == ToolFormat.AUTO:
            return CompositeParser()  # Try everything
        elif format in (ToolFormat.OPENAI, ToolFormat.OLLAMA):
            return CompositeParser([OpenAINativeParser(), XMLToolParser()])
        elif format == ToolFormat.ANTHROPIC:
            return CompositeParser([XMLToolParser(), OpenAINativeParser()])
        else:
            return CompositeParser()
    
    def get_result_adapter(self, format: ToolFormat) -> ToolResultAdapter:
        """Get adapter for formatting tool results."""
        from llmc_agent.format.adapters.openai import OpenAIResultAdapter
        from llmc_agent.format.adapters.anthropic import AnthropicResultAdapter
        
        if format in (ToolFormat.OPENAI, ToolFormat.OLLAMA):
            return OpenAIResultAdapter()
        elif format == ToolFormat.ANTHROPIC:
            return AnthropicResultAdapter()
        else:
            return OpenAIResultAdapter()
```

---

## 5. Failure Modes and Mitigations

### 5.1 Malformed Tool Calls

**Scenario:** Model outputs malformed JSON or XML in tool call.

**Mitigation:**
1. CompositeParser tries multiple extraction strategies
2. Partial parsing: extract what we can, report errors for rest
3. Validation against known tool registry before execution
4. Graceful degradation: treat as content if unparseable

```python
def parse_with_fallback(self, response) -> ParsedResponse:
    """Parse with graceful degradation."""
    try:
        return self.primary_parser.parse(response)
    except Exception as e:
        logger.warning(f"Primary parser failed: {e}")
        # Fall back to just extracting content
        return ParsedResponse(
            content=self._extract_content(response),
            tool_calls=[],
            finish_reason='stop',
            raw_response=response,
        )
```

### 5.2 Hallucinated Tool Names

**Scenario:** Model calls a tool that doesn't exist.

**Mitigation:**
1. Validate against ToolRegistry before execution
2. Return informative error message to model
3. Log for analysis (Coach telemetry)

```python
def execute_tool_call(self, call: ToolCall) -> ToolResult:
    tool = self.registry.get_tool(call.name)
    if tool is None:
        return ToolResult(
            call_id=call.id,
            tool_name=call.name,
            result=None,
            error=f"Tool '{call.name}' does not exist. Available: {self.registry.list_tools()}"
        )
    # ... execute
```

### 5.3 Infinite Tool Loops

**Scenario:** Model keeps calling tools without making progress.

**Mitigation:**
1. `max_tool_rounds` limit (existing)
2. Detection of repeated identical calls
3. Token budget enforcement
4. Manual intervention hook

```python
async def ask_with_tools(self, question: str, max_rounds: int = 5):
    seen_calls: set[tuple] = set()
    
    for round in range(max_rounds):
        response = await self.generate()
        
        for call in response.tool_calls:
            call_key = (call.name, json.dumps(call.arguments, sort_keys=True))
            if call_key in seen_calls:
                # Repeated call - model is stuck
                return self._force_completion(response)
            seen_calls.add(call_key)
```

### 5.4 Cross-Format Leakage

**Scenario:** Model trained on Anthropic format outputs `<tool_use>` even when we're in OpenAI mode.

**Mitigation:**
1. CompositeParser handles this automatically
2. XML extracted from content even if native field is empty
3. Log format mismatches for prompt tuning

### 5.5 Tier Escalation Attacks

**Scenario:** Model attempts to invoke a Tier 2 (RUN) tool when only Tier 1 (WALK) is unlocked.

**Mitigation:**
1. Tier check happens AFTER parsing, on internal ToolCall
2. Execution blocked, informative error returned to model
3. This is **defense in depth** - parsing and authorization are separate

```python
for call in parsed.tool_calls:
    if not self.registry.is_tool_available(call.name):
        # Tier violation
        results.append(ToolResult(
            call_id=call.id,
            tool_name=call.name,
            result=None,
            error=f"Tool '{call.name}' is not available at current tier ({self.registry.current_tier.name})"
        ))
        continue
```

---

## 6. Security Considerations

### 6.1 Argument Injection

Tool arguments are model-generated. They MUST be validated:

```python
@dataclass
class Tool:
    # ...
    parameter_validator: Callable[[dict], dict] | None = None
    
    def validate_arguments(self, args: dict) -> dict:
        """Validate and sanitize tool arguments."""
        # Type coercion per schema
        validated = {}
        for name, schema in self.parameters.get('properties', {}).items():
            if name in args:
                validated[name] = self._coerce_type(args[name], schema['type'])
        
        # Optional custom validator
        if self.parameter_validator:
            validated = self.parameter_validator(validated)
        
        return validated
```

### 6.2 Path Traversal in File Tools

File-related tools already have `allowed_roots` validation. The format layer does NOT bypass this:

```
Format Layer: Parse tool call → ToolCall(name="read_file", arguments={"path": "../../../etc/passwd"})
                                                  ↓
Tier Check: is_tool_available("read_file") → True (WALK tier)
                                                  ↓
Execution: read_file(path="../../../etc/passwd", allowed_roots=["."])
                                                  ↓
Validation: PathSecurityError("Path escapes repository boundary")
```

The format layer is **format translation only**. Security is enforced at execution.

### 6.3 Capability Leakage via Format

**Concern:** Could a clever model use format switching to bypass tier restrictions?

**Analysis:** No. The tier check operates on **internal ToolCall objects**, not wire format. Whether the model says `{"name": "write_file"}` or `<tool_use><name>write_file</name>` is irrelevant - both get normalized to `ToolCall(name="write_file")` and then checked against the tier system.

---

## 7. Performance Considerations

### 7.1 Parsing Overhead

XML parsing is slower than JSON. But:
- Parsing happens once per response, not per token
- Response parsing is I/O-bound (waiting for LLM), not CPU-bound
- Order of magnitude: <1ms for typical responses

**Mitigation:** Use `can_parse()` to short-circuit inapplicable parsers.

### 7.2 Token Efficiency

Different formats have different token costs:

| Format | Definition Overhead | Call Overhead | Result Overhead |
|--------|---------------------|---------------|-----------------|
| OpenAI | ~50 tokens/tool | ~20 tokens/call | ~15 tokens/result |
| Anthropic | ~70 tokens/tool | ~30 tokens/call | ~20 tokens/result |
| Raw JSON | ~40 tokens/tool | ~15 tokens/call | ~10 tokens/result |

**Recommendation:** Use OpenAI format for Ollama (native, lowest overhead). Reserve Anthropic format for actual Anthropic API where it's expected.

### 7.3 Caching

Format negotiation can be cached per-conversation:

```python
class FormatNegotiator:
    def __init__(self):
        self._adapter_cache: dict[ToolFormat, ToolDefinitionAdapter] = {}
    
    def get_definition_adapter(self, format: ToolFormat) -> ToolDefinitionAdapter:
        if format not in self._adapter_cache:
            self._adapter_cache[format] = self._create_adapter(format)
        return self._adapter_cache[format]
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

**Parser tests:**
```python
def test_openai_native_parser():
    response = {"message": {"tool_calls": [{"function": {"name": "search", "arguments": "{}"}}]}}
    parsed = OpenAINativeParser().parse(response)
    assert len(parsed.tool_calls) == 1
    assert parsed.tool_calls[0].name == "search"

def test_xml_parser_anthropic():
    content = '<tool_use>{"name": "search", "arguments": {"query": "test"}}</tool_use>'
    parsed = XMLToolParser().parse(content)
    assert parsed.tool_calls[0].arguments["query"] == "test"

def test_composite_parser_mixed():
    # Response with both native and XML
    response = {
        "message": {
            "tool_calls": [{"function": {"name": "tool1", "arguments": "{}"}}],
            "content": "<tools>{\"name\": \"tool2\"}</tools>"
        }
    }
    parsed = CompositeParser().parse(response)
    assert len(parsed.tool_calls) == 2
```

**Adapter tests:**
```python
def test_openai_definition_adapter():
    tool = Tool(name="search", description="Search code", ...)
    adapter = OpenAIDefinitionAdapter()
    formatted = adapter.format_tools([tool])
    assert formatted[0]["type"] == "function"
    assert formatted[0]["function"]["name"] == "search"
```

### 8.2 Integration Tests

**End-to-end with Boxxie:**
```python
async def test_boxxie_tool_calling():
    """Integration test: Boxxie calls a tool and receives result."""
    config = load_config(profile="boxxie")
    agent = Agent(config)
    
    response = await agent.ask_with_tools("Search for authentication code")
    
    # Should have called search_code tool
    assert any(tc.name == "search_code" for tc in response.tool_calls)
    # Should have received and processed results
    assert "authentication" in response.content.lower() or len(response.tool_calls) > 0
```

### 8.3 Fuzz Testing

```python
def test_malformed_xml_graceful():
    """Parser should not crash on malformed input."""
    malformed_inputs = [
        "<tools>not json</tools>",
        "<tool_use><name>test</broken xml",
        '{"name": "test", unclosed',
        "",
        None,
    ]
    parser = CompositeParser()
    for input in malformed_inputs:
        # Should not raise
        result = parser.parse(input)
        assert result is not None
```

---

## 9. Implementation Phases

### Phase 0: Foundation (4-6 hours)
- [ ] Create `llmc_agent/format/` package structure
- [ ] Implement `types.py` with UTP dataclasses
- [ ] Implement `protocols.py` with Protocol definitions
- [ ] Basic unit tests for types

### Phase 1: Parsers (6-8 hours)
- [ ] `OpenAINativeParser` (current behavior, extracted)
- [ ] `XMLToolParser` (new: Anthropic/Qwen XML)
- [ ] `CompositeParser` (priority chain)
- [ ] Comprehensive parser tests

### Phase 2: Adapters (4-6 hours)
- [ ] `OpenAIDefinitionAdapter` & `OpenAIResultAdapter`
- [ ] `AnthropicDefinitionAdapter` & `AnthropicResultAdapter` (if needed)
- [ ] Adapter tests

### Phase 3: Integration (6-8 hours)
- [ ] `FormatNegotiator` with config support
- [ ] Modify `Agent.ask_with_tools()` to use format layer
- [ ] Modify `OllamaBackend.generate_with_tools()` to return raw response
- [ ] Integration tests with mock Ollama

### Phase 4: Boxxie Validation (4-6 hours)
- [ ] Test with actual `qwen3-next-80b-tools` model
- [ ] Verify tool calls are executed
- [ ] Verify results are fed back correctly
- [ ] End-to-end agentic workflow test

### Phase 5: Configuration & Polish (2-4 hours)
- [ ] Add `[profile.tools]` config section support
- [ ] Update `llmc.toml` schema documentation
- [ ] Add telemetry for format detection/parsing
- [ ] Update CHANGELOG

**Total: 26-38 hours**

---

## 10. Success Criteria

1. **Boxxie Unblocked:** `bx` successfully executes tool calls from Qwen3-Next-80B
2. **Format Agnostic:** Same tools work with OpenAI, Anthropic, and Ollama backends
3. **Progressive Disclosure Intact:** Tier system unchanged, operates on internal types
4. **TE Composable:** Tool Envelope output formatting still works via TE
5. **No Regression:** Existing Claude/Gemini MCP tool calling unaffected
6. **Measurable:** Telemetry tracks format detection and parsing success rate

---

## 11. Future Considerations

### 11.1 Streaming Tool Calls

Some providers support streaming tool calls (partial arguments as they're generated). The current architecture supports this:

```python
async def parse_streaming(self, stream: AsyncIterator[str]) -> AsyncIterator[ToolCall]:
    buffer = ""
    async for chunk in stream:
        buffer += chunk
        # Try to parse complete tool calls from buffer
        if complete_call := self._try_extract(buffer):
            yield complete_call
            buffer = buffer[complete_call.raw_end:]
```

### 11.2 Model-Specific Tuning

Different models have different tool calling behaviors:
- GPT-4: Reliable native format, rarely outputs XML
- Claude: Reliable XML, uses thinking separation
- Qwen: Depends heavily on template/modelfile
- Llama 3.1+: Supports native, but templates vary

Coach could track success rates per model×format and auto-tune.

### 11.3 Tool Call Validation Pre-Flight

Before executing, we could "dry run" tool calls:
```python
def preflight_check(self, call: ToolCall) -> list[str]:
    """Return warnings/errors without executing."""
    issues = []
    if not self.registry.get_tool(call.name):
        issues.append(f"Tool {call.name} not found")
    if not self.registry.is_tool_available(call.name):
        issues.append(f"Tool {call.name} not available at tier")
    # Check argument types, required fields, etc.
    return issues
```

---

## 12. References

1. **OpenAI Function Calling:** https://platform.openai.com/docs/guides/function-calling
2. **Anthropic Tool Use:** https://docs.anthropic.com/en/docs/build-with-claude/tool-use
3. **Ollama Tool Support:** https://ollama.com/blog/tool-support
4. **LLMC Tool Envelope SDD:** `DOCS/legacy/SDD_Tool_Envelope_v1.2.md`
5. **LLMC Agent Tools:** `llmc_agent/tools.py`

---

*This HLD represents the architectural foundation for unified tool calling in LLMC. It separates format concerns from capability concerns, enabling Boxxie and other local models to participate in the agentic ecosystem without sacrificing the progressive disclosure and security guarantees already built.*
