# LLMC Documentation Plan
**Comprehensive HOWTO Documentation for All Major Systems**

---

## 📚 **Documentation Structure**

All HOWTOs will live in `DOCS/HOWTO/` with this structure:
```
DOCS/
├── HOWTO/
│   ├── 01_RAG_CORE/
│   │   ├── indexing.md
│   │   ├── embedding.md
│   │   ├── search.md
│   │   └── graph.md
│   ├── 02_ENRICHMENT/
│   │   ├── overview.md
│   │   ├── router.md
│   │   ├── backends.md
│   │   └── path_weights.md
│   ├── 03_MAASL/
│   │   ├── overview.md
│   │   ├── locks.md
│   │   ├── db_guard.md
│   │   └── merge_engine.md
│   ├── 04_MCP/
│   │   ├── server.md
│   │   ├── code_execution.md
│   │   └── daemon.md
│   ├── 05_SERVICE/
│   │   ├── daemon.md
│   │   └── monitoring.md
│   ├── 06_CONFIG/
│   │   └── llmc_toml.md
│   └── 07_TESTING/
│       └── roswaal.md
└── README.md (Main documentation index)
```

---

## 🎯 **Major Systems Breakdown**

### 1. **RAG Core System** (`DOCS/HOWTO/01_RAG_CORE/`)

#### 1.1 **Indexing** (`indexing.md`)
**Purpose:** How to index a codebase for semantic search

**Topics:**
- Initial index creation (`llmc-cli index`)
- Incremental updates (`llmc-cli sync`)
- Schema detection (Python, TypeScript, JavaScript)
- Exclude patterns & filtering
- Index health (`llmc-cli doctor`)

**Key Files:**
- `tools/rag/indexer.py`
- `tools/rag/schema.py`
- `tools/rag/database.py`

**User Journey:**
```bash
# First time
llmc-cli init
llmc-cli index

# Daily usage
llmc-cli sync  # Auto-detects changes
llmc-cli doctor  # Check health
```

---

#### 1.2 **Embedding** (`embedding.md`)
**Purpose:** How to generate and configure embeddings

**Topics:**
- Embedding providers (Ollama, remote APIs)
- Model selection (nomic-embed-text, jina, etc.)
- Route configuration (code vs docs)
- Dimension management
- Performance tuning

**Key Files:**
- `tools/rag/embeddings.py`
- `tools/rag/embedding_providers.py`

**Configuration:**
```toml
[embeddings.profiles.code]
provider = "ollama"
model = "nomic-embed-text"
dimension = 768
```

---

#### 1.3 **Search** (`search.md`)
**Purpose:** How to perform semantic search across code

**Topics:**
- Basic search (`llmc-cli search "query"`)
- FTS vs vector search
- Reranking weights
- Graph-enhanced search (1-hop expansion)
- Result filtering

**Key Files:**
- `tools/rag/search.py`
- `tools/rag/rerank.py`
- `tools/rag/graph_stitch.py`

**Examples:**
```bash
# Semantic search
llmc-cli search "database connection pooling"

# Graph navigation
llmc-cli nav where-used DatabasePool
llmc-cli nav lineage handle_request
```

---

#### 1.4 **Graph Building** (`graph.md`)
**Purpose:** How schema graphs are built and enriched

**Topics:**
- AST extraction (entities, relations)
- Polyglot support (Python, TS, JS)
- Enrichment integration
- Graph persistence (`.llmc/rag_graph.json`)
- Troubleshooting

**Key Files:**
- `tools/rag/schema.py`
- `tools/rag_nav/tool_handlers.py`

---

### 2. **Enrichment System** (`DOCS/HOWTO/02_ENRICHMENT/`)

#### 2.1 **Overview** (`overview.md`)
**Purpose:** High-level enrichment architecture

**Topics:**
- What is enrichment? (AI summaries, tags, usage guides)
- Pipeline stages: Select → Route → Execute → Persist
- Batch vs interactive modes
- Failure handling & cooldowns

**Diagrams:**
```
Pending Spans → Router → Chain Selection → Backend Cascade → DB Write
                    ↓
              (7b → 14b → 70b fallback)
```

---

#### 2.2 **Router** (`router.md`)
**Purpose:** How enrichment routing works

**Topics:**
- Chain selection logic
- Tier routing (7b, 14b, 70b)
- Slice classification (code vs docs)
- Route configuration in `llmc.toml`

**Key Files:**
- `tools/rag/enrichment_router.py`
- `tools/rag/config_enrichment.py`

**Configuration:**
```toml
[[enrichment.chain]]
name = "athena"
provider = "ollama"
model = "qwen2.5:7b-instruct"
routing_tier = "7b"
```

---

#### 2.3 **Backends** (`backends.md`)
**Purpose:** How to configure LLM backends

**Topics:**
- OllamaBackend (local)
- Remote providers (Gemini, Anthropic, OpenAI, Groq)
- BackendAdapter protocol
- Cascade fallback logic
- Reliability middleware (rate limiting, retries)

**Key Files:**
- `tools/rag/enrichment_adapters/ollama.py`
- `tools/rag/enrichment_backends.py`
- `tools/rag/enrichment_reliability.py`

**Examples:**
```toml
# Local Ollama
[[enrichment.chain]]
provider = "ollama"
url = "http://192.168.5.20:11434"

# Remote Gemini
[[enrichment.chain]]
provider = "gemini"
model = "gemini-1.5-flash"
```

---

#### 2.4 **Path Weights & Code-First** (`path_weights.md`)
**Purpose:** How to prioritize enrichment work

**Topics:**
- Path weight configuration (1-10 scale)
- Code-first detection (directories with lots of imports)
- Skipping vendor/test code
- Custom weight patterns

**Configuration:**
```toml
[enrichment.path_weights]
"src/**" = 1        # High priority
"tests/**" = 6      # Low priority
"vendor/**" = 10    # Back of the line
```

---

### 3. **MAASL (Multi-Agent Anti-Stomp)** (`DOCS/HOWTO/03_MAASL/`)

#### 3.1 **Overview** (`overview.md`)
**Purpose:** What MAASL is and why it exists

**Topics:**
- The "stomp" problem (concurrent edits)
- Resource classes (CRIT_DB, FILE, MERGE_META)
- Lock-based coordination
- Policy-driven timeouts

**Key Concepts:**
```python
# Before MAASL: Race conditions
agent1.write(file)  # Stomps agent2
agent2.write(file)

# After MAASL: Safe coordination
with maasl.stomp_guard([file_resource], ...):
    agent1.write(file)  # Others wait
```

**Key Files:**
- `llmc_mcp/maasl.py`
- `llmc_mcp/locks.py`

---

#### 3.2 **Lock Management** (`locks.md`)
**Purpose:** How MAASL locks work

**Topics:**
- Lock acquisition flow
- Fencing tokens
- Lease TTLs
- Deadlock prevention (sorted lock order)
- Timeout policies (interactive vs batch)

**Key Files:**
- `llmc_mcp/locks.py`
- `llmc_mcp/telemetry.py`

**Example:**
```python
from llmc_mcp.maasl import get_maasl, ResourceDescriptor

maasl = get_maasl()
resource = ResourceDescriptor(
    resource_class="FILE",
    identifier="src/main.py"
)

with maasl.stomp_guard([resource], intent="refactor", mode="interactive"):
    # Safe to modify - lock held
    edit_file("src/main.py")
    # Lock released on exit
```

---

#### 3.3 **Database Transaction Guard** (`db_guard.md`)
**Purpose:** How to safely write to databases

**Topics:**
- `DbTransactionManager` usage
- BEGIN IMMEDIATE semantics
- MAASL lock integration
- Retry logic for SQLITE_BUSY
- Transaction scope (lock held through commit)

**Key Files:**
- `llmc_mcp/db_guard.py`

**Example:**
```python
from llmc_mcp.db_guard import get_db_transaction_manager

mgr = get_db_transaction_manager(db_conn, db_name="rag")

with mgr.write_transaction(agent_id="agent1") as conn:
    conn.execute("INSERT INTO spans ...")
    conn.execute("INSERT INTO enrichments ...")
    # Auto-commit on success, rollback on error
```

---

#### 3.4 **Merge Engine** (`merge_engine.md`)
**Purpose:** Conflict-free graph merges

**Topics:**
- Last-Write-Wins (LWW) semantics
- Deterministic merge order
- Conflict logging
- MAASL protection during merges

**Key Files:**
- `llmc_mcp/merge.py`

---

### 4. **MCP (Model Context Protocol)** (`DOCS/HOWTO/04_MCP/`)

#### 4.1 **MCP Server** (`server.md`)
**Purpose:** How to run the MCP server

**Topics:**
- stdio transport (Claude Desktop)
- HTTP/daemon transport (external systems)
- Tool registration
- Resource management

**Key Files:**
- `llmc_mcp/mcp_server.py`
- `llmc_mcp/bootloader.py`

**Usage:**
```bash
# stdio (Claude Desktop)
python3 llmc_mcp/mcp_server.py

# Daemon mode
llmc-mcp start
llmc-mcp status
```

---

#### 4.2 **Code Execution Mode** (`code_execution.md`)
**Purpose:** Bootstrap tools + Python execution pattern

**Topics:**
- Why code execution? (98% token reduction)
- Stub generation
- `execute_code` tool
- Sandbox safety

**Configuration:**
```toml
[mcp.code_execution]
enabled = true
stubs_dir = ".llmc/stubs"
bootstrap_tools = ["list_dir", "read_file", "execute_code"]
```

---

#### 4.3 **Daemon Management** (`daemon.md`)
**Purpose:** Running MCP as a persistent service

**Topics:**
- systemd integration
- TCP/HTTP transport
- Multi-client support
- Log rotation

**Commands:**
```bash
llmc-mcp start
llmc-mcp stop
llmc-mcp restart
llmc-mcp logs -f
```

---

### 5. **RAG Service Daemon** (`DOCS/HOWTO/05_SERVICE/`)

#### 5.1 **Daemon Management** (`daemon.md`)
**Purpose:** Running long-lived RAG enrichment

**Topics:**
- Service lifecycle (start/stop/restart)
- Repository registration
- Automatic sync/enrich/embed cycles
- Idle loop throttling
- Failure tracking

**Key Files:**
- `tools/rag/service.py`
- `tools/rag/service_daemon.py`

**Commands:**
```bash
# Repository management
llmc-rag repo add /path/to/repo
llmc-rag repo list
llmc-rag repo remove /path/to/repo

# Service control
llmc-rag start --interval 180
llmc-rag stop
llmc-rag status
llmc-rag logs -f
```

---

#### 5.2 **Monitoring** (`monitoring.md`)
**Purpose:** Observing service health

**Topics:**
- Log inspection
- Failure database
- Quality metrics
- Vacuum schedules
- Log rotation

**Key Files:**
- `scripts/llmc_log_manager.py`
- `tools/rag/quality.py`
- `tools/rag/doctor.py`

---

### 6. **Configuration System** (`DOCS/HOWTO/06_CONFIG/`)

#### 6.1 **llmc.toml Reference** (`llmc_toml.md`)
**Purpose:** Complete configuration reference

**Sections:**
1. **Embeddings** - Provider, models, routes
2. **Enrichment** - Chains, backends, path weights
3. **Indexing** - Exclude patterns, file filters
4. **Logging** - Rotation, retention
5. **MCP** - Code execution, auth, tools
6. **Daemon** - Nice level, idle backoff
7. **Profiles** - Daily, yolo, custom

**Examples for each section.**

---

### 7. **Testing Infrastructure** (`DOCS/HOWTO/07_TESTING/`)

#### 7.1 **Roswaal - Autonomous Testing** (`roswaal.md`)
**Purpose:** How to use the testing agent

**Topics:**
- Engaging Roswaal
- Report interpretation
- Priority bug triage
- Continuous validation

**Key Files:**
- `tools/roswaal_ruthless_testing_agent.sh`

**Usage:**
```bash
# Full test run
./tools/roswaal_ruthless_testing_agent.sh

# Reports saved to:
tests/REPORTS/ruthless_testing_report_<timestamp>.md
```

---

## 📝 **Documentation Standards**

Each HOWTO document should follow this template:

```markdown
# [System Name] - [Brief Description]

## Overview
- What is this system?
- Why does it exist?
- When should you use it?

## Quick Start
- 30-second getting started example
- Most common use case

## Core Concepts
- Key abstractions
- Mental models
- Terminology

## Configuration
- Relevant llmc.toml sections
- Environment variables
- Defaults

## Common Tasks
### Task 1: [Name]
**Goal:** [What you want to achieve]
**Steps:**
1. Step 1
2. Step 2
3. ...

**Example:**
```bash
# commands
```

### Task 2: [Name]
...

## Troubleshooting
### Issue: [Common Problem]
**Symptoms:** ...
**Cause:** ...
**Fix:** ...

## Related Systems
- Links to related HOWTOs
- Integration points

## References
- Source files
- SDD documents
- Tests
```

---

## 🎯 **Implementation Priority**

### Phase 1: Core Workflows (Week 1)
1. ✅ **RAG Indexing** - Most used system
2. ✅ **Enrichment Overview** - Complex, needs docs
3. ✅ **Service Daemon** - Daily operations
4. ✅ **llmc.toml Reference** - Central config

### Phase 2: Advanced Features (Week 2)
5. ✅ **MAASL Overview** - New, complex
6. ✅ **MCP Server** - External integrations
7. ✅ **Router & Backends** - Power users
8. ✅ **Path Weights** - Optimization

### Phase 3: Deep Dives (Week 3)
9. ✅ **Database Guard** - Advanced MAASL
10. ✅ **Merge Engine** - Advanced MAASL
11. ✅ **Code Execution Mode** - Advanced MCP
12. ✅ **Roswaal Testing** - CI/CD

---

## 🛠️ **Tools for Documentation**

### Automated Helpers
- **Extract CLI help:** `llmc-cli --help` → markdown
- **Extract config schema:** Parse `llmc.toml` comments
- **Generate file trees:** `tree` command for directory structure
- **Code examples:** Pull from tests

### Validation
- **Link checker:** Ensure all internal links work
- **Example runner:** Execute all code examples in CI
- **Config validator:** Test all TOML snippets

---

## 📊 **Success Metrics**

**Good Documentation Should:**
1. ✅ Answer "How do I...?" in < 2 minutes
2. ✅ New users can complete first index in < 10 minutes
3. ✅ Zero "undocumented feature" bug reports
4. ✅ Contributors can add features without asking for help

---

## 🚀 **Next Steps**

1. **Create directory structure:**
   ```bash
   mkdir -p DOCS/HOWTO/{01_RAG_CORE,02_ENRICHMENT,03_MAASL,04_MCP,05_SERVICE,06_CONFIG,07_TESTING}
   ```

2. **Start with Phase 1 docs** (most urgent)

3. **Generate from existing content:**
   - Mine SDDs for "how to" content
   - Extract examples from tests
   - Pull config snippets from llmc.toml

4. **Get user feedback:**
   - What's confusing?
   - What's missing?
   - What docs would save the most time?

---

**Ready to start? Pick a system and I'll create the first HOWTO!**
