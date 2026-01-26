# RLM API Reference

## 💻 CLI Commands

### `llmc rlm query`

Execute an RLM analysis session.

```bash
llmc rlm query [OPTIONS] TASK
```

**Arguments:**
- `TASK`: The natural language query or instruction (Required).

**Options:**
- `--file, -f PATH`: Load a specific file as initial context.
- `--budget, -b FLOAT`: Max budget in USD (default: $1.00).
- `--model, -m NAME`: Override the root reasoning model.
- `--verbose, -v`: Show internal thought process and tool outputs.
- `--profile NAME`: Load a specific configuration profile (e.g., 'restricted').

---

## 🐍 Python API

### `llmc.rlm.session.RLMSession`

The main entry point for programmatic use.

```python
class RLMSession:
    def __init__(self, config: RLMConfig):
        ...

    async def run(self, task: str, max_turns: int = 10) -> RLMResult:
        """Execute the analysis loop."""
```

### `llmc.rlm.session.RLMResult`

Structured result object.

```python
@dataclass
class RLMResult:
    success: bool
    answer: str          # The final text response
    session_id: str      # Unique ID for tracing
    history: List[Message]
    budget_summary: Dict[str, float]
    error: Optional[str] = None
```

### `llmc.rlm.config.RLMConfig`

Configuration object.

```python
@dataclass
class RLMConfig:
    enabled: bool = True
    root_model: str = "..."
    max_session_budget_usd: float = 1.0
    trace_enabled: bool = True
    ...
```

---

## 🔌 MCP Tool Interface

### `rlm_query`

Exposes RLM analysis to MCP clients (Claude Desktop, etc.).

**Input Schema:**

| Field | Type | Description | Required |
| :--- | :--- | :--- | :--- |
| `task` | string | Analysis instructions | Yes |
| `path` | string | File path to analyze (Mutual exclusive with context) | No* |
| `context` | string | Raw text context (Mutual exclusive with path) | No* |
| `budget_usd` | number | Per-call budget cap (default 1.0) | No |
| `max_turns` | integer | Max reasoning steps (default 5) | No |

*\* Exactly one of `path` or `context` must be provided.*

**Output Schema:**

```json
{
  "data": {
    "answer": "The bug is in line 42...",
    "session_id": "sess_123",
    "budget_summary": {"total_cost_usd": 0.05}
  },
  "meta": {
    "source": {"type": "path", "path": "src/main.py"},
    "model_used": "ollama/qwen2.5"
  }
}
```

**Error Codes:**
- `invalid_args`: Bad schema or missing fields.
- `path_denied`: Access to file blocked by security policy.
- `file_too_large`: File exceeds `max_bytes` limit.
- `budget_exceeded`: Analysis stopped due to cost/token limits.
- `timeout`: Session took too long.
