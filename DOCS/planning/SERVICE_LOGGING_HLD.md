# RAG Service Logging Specification - HLD

## Problem Statement

The LLMC RAG service has **exceptional** operational logging that provides real-time visibility into:
- Enrichment progress (`[rag-enrich] Enriched span 10/50`)
- Performance metrics (`(3.67s)`)
- Routing decisions (`via tier 7b` vs `via tier 14b`)
- Full traceability (`[chain=athena, backend=athena-14b, url=http://192.168.5.20:11434]`)
- Quality metrics (`✅ llmc: Quality 99.6%`)
- Visual hierarchy (emojis: ✅, 🤖, 📊, 🔄)

**The Challenge:** Previous refactor attempts to make this a "proper Linux service" lost the soul of these logs. The user wants to:
1. Keep every bit of this beautiful logging
2. Make it work as a systemd service
3. Eventually feed this same log stream into a TUI screen
4. Maintain the operational zen of watching the system work

## Design Goals

### 1. **Preserve the Soul**
- Every log line format stays exactly as-is
- All emojis, metrics, and structure preserved
- No loss of information or readability

### 2. **Dual Output Modes**
- **Console Mode**: Rich, colorized output for interactive use
- **Service Mode**: Same content, journald-compatible, structured metadata

### 3. **Future TUI Integration**
- Log format designed to be parseable for TUI rendering
- Structured enough to extract metrics programmatically
- Human-readable enough to display as-is

### 4. **Production Ready**
- Works with systemd/journald
- Supports log levels (INFO, WARN, ERROR)
- Includes structured metadata for filtering
- Maintains performance (no blocking I/O)

## Architecture

### Core Components

#### 1. **Unified Logger (`tools/rag/logging.py`)**
```
RAGLogger
├── Console Handler (rich formatting, colors, emojis)
├── Journald Handler (structured fields, no ANSI codes)
└── TUI Handler (future: structured events for TUI)
```

**Key Features:**
- Single logging call produces output for all handlers
- Automatic detection of environment (TTY vs systemd)
- Structured metadata attached to every log line
- Zero performance overhead when handlers disabled

#### 2. **Log Message Format**

**Current Format (Preserved):**
```
[rag-enrich] Enriched span 10/50 for tools/rag/planner.py
Stored enrichment 20: tools/rag/planner.py:157-160 (3.67s) via tier 7b (qwen2.5:7b-instruct) [chain=athena, backend=athena, url=http://192.168.5.20:11434]
✅ llmc: Quality 99.6% (3385 enrichments, issues: 12 placeholder) [v1-cjk-aware]
```

**Structured Metadata (Added Invisibly):**
```python
{
    "component": "rag-enrich",
    "action": "enriched_span",
    "span_number": 10,
    "span_total": 50,
    "file_path": "tools/rag/planner.py",
    "duration_sec": 3.67,
    "tier": "7b",
    "model": "qwen2.5:7b-instruct",
    "chain": "athena",
    "backend": "athena",
    "url": "http://192.168.5.20:11434"
}
```

#### 3. **Service Integration**

**systemd Unit File:**
```ini
[Unit]
Description=LLMC RAG Service
After=network.target

[Service]
Type=simple
ExecStart=/home/vmlinux/src/llmc/scripts/llmc-rag-service start --interval 180
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Viewing Logs:**
```bash
# Real-time, formatted output (just like console)
journalctl -fu llmc-rag-service

# Filter by component
journalctl -u llmc-rag-service COMPONENT=rag-enrich

# Filter by tier
journalctl -u llmc-rag-service TIER=14b

# Performance analysis
journalctl -u llmc-rag-service -o json | jq '.DURATION_SEC'
```

### Implementation Strategy

#### Phase 1: Create Logger Module
**File:** `tools/rag/logging.py`

**Features:**
- `RAGLogger` class with methods for each log type
- Auto-detection of output mode (TTY vs journal)
- Emoji/color stripping for journal mode
- Structured field extraction

**Example Usage:**
```python
from tools.rag.logging import get_rag_logger

logger = get_rag_logger()

# Enrichment progress
logger.enrich_progress(
    span_num=10,
    span_total=50,
    file_path="tools/rag/planner.py"
)
# Output: [rag-enrich] Enriched span 10/50 for tools/rag/planner.py
# Metadata: COMPONENT=rag-enrich SPAN_NUM=10 SPAN_TOTAL=50 FILE_PATH=tools/rag/planner.py

# Enrichment stored
logger.enrich_stored(
    enrichment_id=20,
    file_path="tools/rag/planner.py",
    lines=(157, 160),
    duration=3.67,
    tier="7b",
    model="qwen2.5:7b-instruct",
    chain="athena",
    backend="athena",
    url="http://192.168.5.20:11434"
)
# Output: Stored enrichment 20: tools/rag/planner.py:157-160 (3.67s) via tier 7b (qwen2.5:7b-instruct) [chain=athena, backend=athena, url=http://192.168.5.20:11434]
# Metadata: ENRICHMENT_ID=20 DURATION_SEC=3.67 TIER=7b MODEL=qwen2.5:7b-instruct ...
```

#### Phase 2: Update Service Runner
**File:** `tools/rag/service.py`

**Changes:**
- Replace `print()` calls with `logger.*()` calls
- Add structured metadata to all log lines
- Preserve exact output format

#### Phase 3: Update Enrichment Scripts
**Files:** `scripts/qwen_enrich_batch.py`, `tools/rag/runner.py`

**Changes:**
- Import and use `RAGLogger`
- Replace print statements
- Add metadata extraction

#### Phase 4: Systemd Integration
**New Files:**
- `systemd/llmc-rag.service` - systemd unit file
- `scripts/install-service.sh` - installation helper

**Features:**
- Automatic service installation
- Log viewing helpers
- Service management commands

#### Phase 5: TUI Preparation (Future)
**Design Considerations:**
- Logger can emit structured events to a queue
- TUI subscribes to event queue
- Real-time updates without polling logs
- Same beautiful formatting in TUI panels

## Log Categories

### 1. **Progress Logs**
```
[rag-enrich] Enriched span 10/50 for tools/rag/planner.py
[rag-runner] Syncing 10 paths
```
**Metadata:** `COMPONENT`, `ACTION`, `PROGRESS`, `FILE_PATH`

### 2. **Performance Logs**
```
Stored enrichment 20: tools/rag/planner.py:157-160 (3.67s) via tier 7b
```
**Metadata:** `DURATION_SEC`, `TIER`, `MODEL`, `BACKEND`

### 3. **Quality Logs**
```
✅ llmc: Quality 99.6% (3385 enrichments, issues: 12 placeholder)
```
**Metadata:** `QUALITY_SCORE`, `TOTAL_ENRICHMENTS`, `ISSUE_COUNT`, `ISSUE_TYPE`

### 4. **Status Logs**
```
✅ Enriched pending spans with real LLM summaries
🔄 Processing llmc...
💤 Sleeping 180s until next cycle...
```
**Metadata:** `STATUS`, `COMPONENT`, `ACTION`

### 5. **Error Logs**
```
⚠️  Enrichment failed: Connection timeout
```
**Metadata:** `ERROR_TYPE`, `ERROR_MESSAGE`, `COMPONENT`

## Benefits

### For Development
- **Same beautiful console output** you love
- **No changes** to how you run the service locally
- **Enhanced debugging** with structured metadata

### For Production
- **Proper systemd integration** with automatic restarts
- **Queryable logs** via journalctl filters
- **Performance analysis** via structured fields
- **No log file management** (journald handles rotation)

### For Future TUI
- **Event-driven architecture** ready for TUI subscription
- **Structured data** for metrics panels
- **Same formatting** for log viewer panel
- **Real-time updates** without log parsing

## Migration Path

### Step 1: Create Logger (No Breaking Changes)
- Add `tools/rag/logging.py`
- Logger defaults to console mode
- Existing code continues to work

### Step 2: Gradual Migration
- Update one component at a time
- Test output matches exactly
- Add structured metadata

### Step 3: Service Integration
- Add systemd unit file
- Test with `systemctl start llmc-rag`
- Verify journald output

### Step 4: Documentation
- Update README with service commands
- Add log filtering examples
- Document structured fields

## Example: Before & After

### Before (Current)
```python
print(f"[rag-enrich] Enriched span {i}/{total} for {file_path}")
print(f"Stored enrichment {id}: {file_path}:{start}-{end} ({duration:.2f}s) via tier {tier} ({model}) [chain={chain}, backend={backend}, url={url}]")
```

### After (With Logger)
```python
logger.enrich_progress(span_num=i, span_total=total, file_path=file_path)
logger.enrich_stored(
    enrichment_id=id,
    file_path=file_path,
    lines=(start, end),
    duration=duration,
    tier=tier,
    model=model,
    chain=chain,
    backend=backend,
    url=url
)
```

**Console Output:** *Identical to before*
**Journald Output:** *Same text + structured metadata*
**TUI Output:** *Structured event for rendering*

## Success Criteria

1. ✅ **Zero visual changes** to console output
2. ✅ **All emojis and formatting** preserved
3. ✅ **Works as systemd service** with proper lifecycle
4. ✅ **Queryable via journalctl** with structured fields
5. ✅ **Ready for TUI integration** with event architecture
6. ✅ **No performance regression** in logging path
7. ✅ **Maintains operational zen** of watching logs

## Questions for Review

1. **Logging Module Location:** Is `tools/rag/logging.py` the right place, or should it be `tools/logging.py` for broader use?

2. **Structured Field Names:** Should we use `UPPER_CASE` (journald convention) or `snake_case` (Python convention)?

3. **Color in Console:** Should we add ANSI color codes for different log levels/components in console mode?

4. **TUI Timeline:** Is TUI integration planned for this release, or can it wait for a future iteration?

5. **Backward Compatibility:** Should we keep `print()` fallbacks for environments without the logger, or require migration?
