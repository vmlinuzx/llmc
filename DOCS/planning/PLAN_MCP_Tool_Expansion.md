# Implementation Plan: MCP Tool Expansion - rag_plan

**Feature:** Add `rag_plan` observability tool  
**Branch:** `feature/mcp-daemon-architecture` (piggyback on current work)  
**Effort:** 30 minutes  
**Status:** 🚀 Ready to implement

---

## Objective

Add `rag_plan` MCP tool to show heuristic retrieval planning without executing the search.

---

## Tool Specification

**Name:** `rag_plan`  
**Category:** Observability  
**Purpose:** Explain how LLMC would route and execute a RAG query

**Input Schema:**
```json
{
  "query": "string (required) - The query to analyze",
  "detail_level": "summary | full (optional, default: summary)"
}
```

**Output Schema:**
```json
{
  "query": "original query",
  "route_type": "code | docs | both | erp",
  "routing_confidence": 0.0-1.0,
  "search_strategy": "semantic | keyword | hybrid",
  "estimated_chunks": 5,
  "filters": {
    "content_type": ["code"],
    "scope": "repo"
  },
  "explanation": "Human-readable routing rationale",
  "heuristics_used": ["code_patterns", "keywords", "context"]
}
```

---

## Implementation Tasks

### Task 1: Add Tool Definition
**File:** `llmc_mcp/server.py`  
**Location:** Add to `TOOLS` list

```python
Tool(
    name="rag_plan",
    description="Analyze query routing and retrieval plan without executing search. Shows how LLMC would handle the query.",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Query to analyze",
            },
            "detail_level": {
                "type": "string",
                "enum": ["summary", "full"],
                "description": "Level of detail in response",
                "default": "summary",
            },
        },
        "required": ["query"],
    },
),
```

### Task 2: Add Handler
**File:** `llmc_mcp/server.py`  
**Location:** In `_init_classic_mode()` tool_handlers dict

```python
"rag_plan": self._handle_rag_plan,
```

### Task 3: Implement Handler Method
**File:** `llmc_mcp/server.py`  
**Location:** New method after other RAG handlers

```python
async def _handle_rag_plan(self, args: dict) -> list[TextContent]:
    """RAG query planning - show routing without execution."""
    import json
    from pathlib import Path
    
    query = args.get("query", "")
    detail_level = args.get("detail_level", "summary")
    
    if not query:
        return [TextContent(type="text", text='{"error": "query is required"}')]
    
    # Find LLMC root
    llmc_root = (
        Path(self.config.tools.allowed_roots[0])
        if self.config.tools.allowed_roots
        else Path(".")
    )
    
    # Use routing logic to analyze query
    from tools.rag.enrichment_router import EnrichmentRouter
    
    try:
        router = EnrichmentRouter(llmc_root)
        decision = router.route_query(query)
        
        # Build plan response
        plan = {
            "query": query,
            "route_type": decision.route_type,
            "routing_confidence": getattr(decision, 'confidence', 0.8),
            "search_strategy": "hybrid",  # Default strategy
            "estimated_chunks": self.config.rag.top_k,
            "filters": {
                "scope": decision.scope if hasattr(decision, 'scope') else "repo",
            },
            "explanation": f"Query classified as '{decision.route_type}' based on content analysis",
        }
        
        if detail_level == "full":
            plan["heuristics_used"] = [
                "pattern_matching",
                "keyword_analysis", 
                "query_structure"
            ]
            plan["backend_chain"] = [spec.name for spec in decision.backend_specs]
        
        return [TextContent(type="text", text=json.dumps(plan, indent=2))]
        
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
```

### Task 4: Update Code Execution Stubs (if needed)
**Note:** Stubs are auto-generated from TOOLS list, so this happens automatically

---

## Testing

**Manual Test:**
```bash
# Via MCP Inspector or client
{
  "method": "tools/call",
  "params": {
    "name": "rag_plan",
    "arguments": {
      "query": "how does authentication work",
      "detail_level": "full"
    }
  }
}
```

**Expected Response:**
```json
{
  "query": "how does authentication work",
  "route_type": "code",
  "routing_confidence": 0.85,
  "search_strategy": "hybrid",
  "estimated_chunks": 5,
  "filters": {"scope": "repo"},
  "explanation": "Query classified as 'code' based on content analysis",
  "heuristics_used": ["pattern_matching", "keyword_analysis", "query_structure"],
  "backend_chain": ["local-7b", "qwen-14b-fallback"]
}
```

---

## Acceptance Criteria

- [ ] Tool appears in `list_tools` response
- [ ] Handler returns valid JSON
- [ ] Works with both "summary" and "full" detail levels
- [ ] Error handling for missing query
- [ ] Routing logic reused (no duplication)

---

## Timeline

- **Task 1:** 5 minutes (add tool definition)
- **Task 2:** 2 minutes (add handler registration)
- **Task 3:** 20 minutes (implement handler)
- **Task 4:** Auto-generated during next stub regeneration
- **Testing:** 3 minutes

**Total:** ~30 minutes

---

## Commit Message

```
feat(mcp): add rag_plan observability tool

Adds new MCP tool for query routing analysis:
- Shows how LLMC would route a query without executing
- Provides routing confidence and strategy
- Supports summary and full detail levels
- Useful for debugging RAG routing decisions
```
