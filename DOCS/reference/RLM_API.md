# RLM API Reference

## 💻 CLI Commands

### `llmc-cli rlm query`

Execute an RLM analysis session.

```bash
llmc-cli rlm query [OPTIONS] TASK
```

**Arguments:**
- `TASK`: The natural language query or instruction (Required).

**Options:**
- `--file, -f PATH`: Load a specific file as initial context.
- `--context, -c PATH`: Load raw context from a file.
- `--budget, -b FLOAT`: Max budget in USD (default: .00).
- `--model, -m NAME`: Override the root reasoning model.
- `--trace`: Show execution trace (JSON events).
- `--json`: Output result as JSON.

---

## 🐍 Python API

### `llmc.rlm.session.RLMSession`

The main entry point for programmatic use.

```python
class RLMSession:
    def __init__(self, config: RLMConfig):
        ...

    async def run(self, task: str, max_turns: int = 20) -> RLMResult:
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
    trace: Optional[List[Dict]] = None
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
    # ... and many more (see llmc/rlm/config.py)
```

---

## 🔌 MCP Tool Interface

### `rlm_query`

Exposes RLM analysis to MCP clients (Claude Desktop, etc.).

**Input Schema:**

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `task` | string | Analysis instructions | Yes | - |
| `path` | string | File path to analyze (Mutual exclusive with context) | No* | - |
| `context` | string | Raw text context (Mutual exclusive with path) | No* | - |
| `budget_usd` | number | Per-call budget cap | No | 1.0 |
| `max_turns` | integer | Max reasoning steps | No | 20 |
| `model` | string | Override root model (if allowed by policy) | No | - |
| `max_bytes` | integer | Max bytes to read from file | No | Configured Limit |
| `timeout_s` | number | Session timeout in seconds | No | 300 |
| `language` | string | Language hint for context | No | - |

*` Exactly one of `path` or `context` must be provided.*

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
    "model_used": "ollama/qwen2.5",
    "trace_included": false
  }
}
```

**Error Codes:**
- `invalid_args`: Bad schema or missing fields.
- `path_denied`: Access to file blocked by security policy.
- `file_too_large`: File exceeds `max_bytes` limit.
- `egress_denied`: Model override or network access blocked.
- `timeout`: Session took too long.
- `internal_error`: Unexpected exception.
