# SDD – LLMC Tool Envelope (TE)

Version: 1.2  
Owner: Dave (LLMC)  
Status: Draft – ready for implementation  
Doc: `SDD_Tool_Envelope_v1.2.md`

---

## 1. Philosophy

### 1.1 The Core Insight

LLMs are alien intelligences trained on billions of shell interactions. They already know `grep`, `cat`, `find`. That knowledge is free—baked into the weights.

Current tool integration approaches fight this:
- Function schemas that duplicate what the model already knows
- 30K token system prompts teaching "use this RAG tool instead of grep"
- Wrapper libraries that create new APIs the model must learn per-session

**TE takes the opposite approach:** Keep the shell interface the model already knows. Make the *responses* smarter.

The LLM runs `te grep database_connection`. It gets back enriched, ranked, progressively-disclosed output. No new tools to learn. No prompt bloat. The response stream *is* the teaching.

### 1.2 Minimal Progressive Disclosure (MPD)

Heavy prompting poisons the model's natural capabilities. The more you instruct, the more you overwrite emergent behavior with your assumptions.

**MPD Principle:** Give the LLM just enough signal to activate relevant training, then get out of the way.

```
VERBOSE (wrong)                   MINIMAL (right)
─────────────────────────────────────────────────────────────────
"here are 5 commands you          {"matches": 847, "truncated": true,
could run next, copy paste         "handle": "res_01HYY..."}
these exact strings..."           

Treats LLM as:                    Treats LLM as:
- dumb executor                   - alien that knows Unix
- needs hand-holding              - infers from signals
- deterministic machine           - generalizes from training

Cost: 200 tokens of bloat         Cost: 30 tokens
```

The alien sees `"truncated": true, "handle": "..."` and its weights light up with every pagination pattern it's ever seen. It doesn't need explicit instructions.

### 1.3 Prompt Toxicity

Every token of instruction risks overwriting behavior that would have emerged naturally. Bad models fail on minimal prompts—that's useful signal. Good models exceed your imagination when you stop constraining them.

TE is a **fitness test**, not a training framework.

---

## 2. Purpose and Scope

### 2.1 Problem

1. **Abyss output** – Tools produce huge outputs. LLMs dutifully consume everything, fill context windows, and become useless.

2. **Prompt bloat** – Teaching LLMs about better tools requires massive system prompts (AGENTS.md, CONTRACTS.md, etc.).

### 2.2 Solution

**TE is a shell-level middleware that:**
- Intercepts standard commands (`grep`, `cat`, `find`, etc.)
- Returns enriched, ranked, progressively-disclosed output
- Uses the response stream to signal capabilities without input token cost
- Gathers telemetry for continuous improvement

**TE is NOT:**
- A safety sandbox
- A tool wrapper framework
- A prompt engineering system
- A semantic cache

### 2.3 Scope

**In scope:**
- `llmc/te/` package
- `te` CLI entrypoint
- MPD meta headers and streaming breadcrumbs
- Content-type sniffing (Phase 0)
- Agent-aware output budgets
- Handle-based result storage (in-memory)
- Telemetry for Coach
- Coach as bandit optimizer

**Out of scope:**
- Router integration (TE stays prompt-light)
- Semantic caching (if LLM asks 3x, find a better LLM)
- Per-command wrapper SDDs
- Multi-user/multi-tenant

---

## 3. Architecture

### 3.1 Data Flow

```
LLM / Agent
  ↓  (tool: run_shell("te grep ..."))
Shell
  ↓
te CLI (llmc.te.cli)
  ↓
TE Core (config → sniffer → handler → formatter)
  ↓
Underlying tool (rg, cat, etc.)
  ↓
Ranked, breadcrumbed output stream
  ↓
LLM receives MPD response, infers next action
```

### 3.2 Components

**C1 – CLI (`llmc.te.cli`)**
- Parses `te <subcommand> [options] [args...]`
- Loads config from `llmc.toml`
- Reads identity envs (`TE_AGENT_ID`, `TE_SESSION_ID`)
- Builds `TeContext`, dispatches to handler

**C2 – Config (`llmc.te.config`)**
- Typed config from `[tool_envelope]` section
- Agent budget lookup
- Per-subcommand thresholds

**C3 – Sniffer (`llmc.te.sniffer`)**
- 50-line content-type classifier
- Extension map + log regex + JSON heuristic
- Falls back to "text" gracefully

**C4 – Handlers (`llmc.te.handlers`)**
- Per-subcommand logic (grep, cat, find, etc.)
- Applies workspace rules
- Calls underlying tool
- Ranks results
- Produces streaming breadcrumbs

**C5 – Formatter (`llmc.te.formatter`)**
- Builds MPD meta header
- Interleaves breadcrumbs into output stream
- Respects agent output budget

**C6 – Handle Store (`llmc.te.store`)**
- In-memory dict for session
- `store(result) -> handle_id`
- `load(handle_id) -> result | None`
- No persistence, no TTL, no eviction—dies with session

**C7 – Telemetry (`llmc.te.telemetry`)**
- JSONL event log
- Captures: command, output size, truncation, handle usage, next action (when detectable)
- Feeds Coach

**C8 – Coach (`llmc.te.coach`)**
- Bandit optimizer over output strategies
- A/B tests: preview size, breadcrumb density, meta verbosity
- Scores by LLM's next action
- Run manually, not automated

---

## 4. Detailed Design

### 4.1 MPD Meta Header

Minimal JSON between markers:

```
# TE_BEGIN_META
{"v":1,"cmd":"grep","matches":847,"files":37,"truncated":true,"handle":"res_01H..."}
# TE_END_META
```

**Required fields:**
- `v`: schema version (integer)
- `cmd`: subcommand name
- `matches` / `lines` / `size`: result magnitude (command-specific)

**Optional fields:**
- `truncated`: boolean
- `handle`: handle ID if stored
- `hot_zone`: where results concentrate (e.g., "tools/rag/ (73%)")
- `content_type`: from sniffer
- `error`: error code if failed

**Forbidden:**
- `next_moves`, `suggestions`, `hints` arrays
- Anything that hand-holds the LLM

One exception: `"hint": "rag search available"` for capabilities the LLM literally cannot infer from training (novel TE features).

### 4.2 Streaming Breadcrumbs

Output is ranked by relevance. Breadcrumbs appear inline as separators:

```
# TE_BEGIN_META
{"v":1,"cmd":"grep","matches":847,"hot_zone":"tools/rag/ (73%)","handle":"res_01H..."}
# TE_END_META

tools/rag/database.py:15: def database_connection():  # definition
tools/rag/database.py:89: database_connection.execute(  # hot usage
tools/rag/service.py:23: from .database import database_connection

# TE: 612 more in tools/rag/, 235 elsewhere

tests/test_database.py:7: mock_database_connection = ...

# TE: remaining 230 are test fixtures
```

**Breadcrumb rules:**
- Appear after ranked sections, not at arbitrary truncation points
- Describe what's omitted, not what to do about it
- Use `# TE:` prefix for easy parsing
- LLM can bail at any breadcrumb—output position = relevance signal

### 4.3 Content Sniffer (Phase 0)

```python
# llmc/te/sniffer.py
import re
from pathlib import Path

EXTENSION_MAP = {
    '.py': 'code/python', '.js': 'code/javascript', '.ts': 'code/typescript',
    '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml', '.toml': 'toml',
    '.md': 'markdown', '.log': 'log', '.csv': 'tabular', '.sql': 'code/sql',
}

LOG_PATTERN = re.compile(
    r'^\d{4}[-/]\d{2}[-/]\d{2}|'
    r'^\[?(ERROR|WARN|INFO|DEBUG)\]?|'
    r'^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}'
)

def sniff(path: str, sample: str = None) -> str:
    ext = Path(path).suffix.lower()
    if ext in EXTENSION_MAP:
        return EXTENSION_MAP[ext]
    if sample:
        lines = sample.split('\n')[:5]
        if sum(1 for l in lines if LOG_PATTERN.match(l)) >= 2:
            return 'log'
        stripped = sample.strip()
        if stripped.startswith(('{', '[')) and stripped.endswith(('}', ']')):
            return 'json'
    return 'text'
```

Future: RAG enrichment adds `content_type` field, sniffer only handles un-indexed files.

### 4.4 Agent Output Budgets

```python
AGENT_BUDGETS = {
    'gemini-shell': 900_000,
    'claude-dc': 180_000,
    'qwen-local': 28_000,
    'human-cli': 50_000,
    'unknown': 16_000,
}

def get_output_budget(agent_id: str) -> int:
    return AGENT_BUDGETS.get(agent_id, AGENT_BUDGETS['unknown'])
```

TE auto-tunes output size to caller's context window. Gemini gets more preview. Local Qwen gets aggressive truncation.

### 4.5 Handle Store

```python
# llmc/te/store.py
from dataclasses import dataclass
from typing import Any
import uuid

@dataclass
class StoredResult:
    data: Any
    cmd: str
    created: float

STORE: dict[str, StoredResult] = {}

def store(result: Any, cmd: str) -> str:
    handle = f"res_{uuid.uuid4().hex[:12]}"
    STORE[handle] = StoredResult(data=result, cmd=cmd, created=time.time())
    return handle

def load(handle: str) -> Any | None:
    entry = STORE.get(handle)
    return entry.data if entry else None
```

No TTL. No eviction. No persistence. Session dies, handles die. Add complexity when actually needed.

### 4.6 Telemetry

```python
@dataclass
class TeEvent:
    timestamp: str
    agent_id: str
    session_id: str
    cmd: str
    mode: str  # enriched | raw | error
    input_size: int  # bytes of underlying output
    output_size: int  # bytes after TE processing
    truncated: bool
    handle_created: bool
    latency_ms: int
    error: str | None
```

Written to `.llmc/te_telemetry.jsonl`. Coach consumes this.

### 4.7 Coach (Bandit Optimizer)

**Strategies per command:**
```python
@dataclass
class GrepStrategy:
    preview_count: int      # matches to show before first breadcrumb
    show_hot_zone: bool     # include concentration info in meta
    breadcrumb_density: str # "high" | "medium" | "low"
```

**Selection:**
```python
def select_strategy(cmd: str) -> Strategy:
    if random() < 0.2:  # explore
        return random.choice(STRATEGIES[cmd])
    return best_strategy(cmd)  # exploit
```

**Scoring (requires next-action capture):**

| LLM's Next Action | Score |
|-------------------|-------|
| Proceeds to actual task | +2 |
| Uses handle for more | +1 |
| Re-runs similar query | -1 |
| Asks user for help | -2 |

Coach runs manually: `te coach report`. Shows which strategies win.

---

## 5. Config

```toml
[tool_envelope]
enabled = true

[tool_envelope.workspace]
root = "/home/vmlinux/src/llmc"
respect_gitignore = true
allow_outside_root = false

[tool_envelope.telemetry]
enabled = true
path = ".llmc/te_telemetry.jsonl"

[tool_envelope.grep]
preview_matches = 10
max_output_chars = 20000
timeout_ms = 5000

[tool_envelope.cat]
preview_lines = 50
max_output_chars = 30000

[tool_envelope.agent_budgets]
gemini-shell = 900000
claude-dc = 180000
qwen-local = 28000
human-cli = 50000
default = 16000
```

---

## 6. CLI Interface

```bash
te grep "pattern" [path]     # enriched grep
te cat <file>                # enriched cat  
te find <path> -name "*.py"  # enriched find

te -i grep "pattern"         # raw bypass, no enrichment
te -i cat <file>             # raw bypass

te --handle res_01H... [--chunk N]  # retrieve stored result

te coach report              # show strategy performance
```

`-i` is the escape hatch. Free market—if LLMs abuse it, that's signal.

---

## 7. Error Handling

**Underlying tool errors:**

```
# TE_BEGIN_META
{"v":1,"cmd":"grep","error":"invalid_pattern"}
# TE_END_META

[TE] invalid regex pattern
```

**TE internal errors (for agents):**

```
# TE_BEGIN_META
{"v":1,"cmd":"grep","error":"internal"}
# TE_END_META

[TE] internal error, operator intervention required
```

**TE internal errors (for humans):**

Fall back to raw execution, print warning.

---

## 8. Phasing

### Phase 0 – Skeleton
- `llmc/te/` package structure
- CLI with `grep` handler
- MPD meta header
- Streaming breadcrumbs (basic ranking)
- 50-line sniffer
- Agent budget awareness
- JSONL telemetry
- `-i` raw bypass
- In-memory handle store

### Phase 1 – More Handlers
- `te cat` with content-type-aware preview
- `te find` with result ranking
- Handle chunk retrieval (`--handle`, `--chunk`)

### Phase 2 – Coach
- Strategy definitions per command
- Bandit selection (epsilon-greedy)
- Next-action scoring (heuristic)
- `te coach report` CLI

### Phase 3 – RAG Integration
- `te rag search` as first-class subcommand
- Sniffer delegates to RAG enrichment for indexed files
- Coach learns when RAG beats grep

---

## 9. Testing

**Unit:**
- Sniffer: extension map, log detection, JSON detection, fallback
- Config: loading, agent budget lookup
- Meta header: field presence per mode
- Store: store/load/miss

**Integration:**
- Temp workspace with seeded files
- `te grep` small result → full output
- `te grep` large result → truncation + handle
- `te -i grep` → raw passthrough
- `te --handle` → retrieval
- Error paths: bad regex, permission denied

**Telemetry:**
- Events written for every invocation
- Fields populated correctly

---

## 10. What TE Is Not

- **Not a sandbox.** It's a sharp knife. Commit often.
- **Not a prompt framework.** Zero system prompt contribution.
- **Not a semantic cache.** If LLM repeats itself, refresh the session.
- **Not a router.** TE doesn't decide which model to use.
- **Not a nanny.** GenX engineering—free market for LLMs.

---

## 11. Success Criteria

1. **Context protection:** LLMs stop filling windows with log files
2. **Zero prompt tax:** No AGENTS.md additions required for TE
3. **Emergent behavior:** Good models figure out handles without instruction
4. **Measurable improvement:** Coach shows strategy convergence
5. **Operator sanity:** Dave stops losing sessions to abyss output
