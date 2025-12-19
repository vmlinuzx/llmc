# SDD: RMTA Phase 2+ (Roadmap 2.4)

**Date:** 2025-12-19  
**Author:** Dave + Antigravity  
**Status:** Ready for Implementation  
**Priority:** P2  
**Effort:** 16-24 hours (across phases)  
**Assignee:** Jules  

---

## 1. Executive Summary

Extend the Ruthless MCP Testing Apparatus (RMTA) from its current shell harness (Phase 1) to a full automated orchestrator with CI integration.

**Current State:** Phase 1 complete - shell harness exists at `tests/ruthless/`  
**Goal:** Automated orchestrator with quality gates and regression detection

---

## 2. Phases Overview

| Phase | Description | Effort | Status |
|-------|-------------|--------|--------|
| 1 | Shell harness | 4h | ✅ DONE |
| 2 | Automated orchestrator | 8h | 🟡 TODO |
| 3 | CI integration with quality gates | 4h | 🟡 TODO |
| 4 | Historical tracking and regression detection | 8h | 🟡 TODO |

---

## 3. Phase 2: Automated Orchestrator

### Goal
Create `llmc test-mcp --mode ruthless` command that runs comprehensive MCP tool testing.

### Implementation

**File:** `llmc/commands/test_mcp.py` (new)

```python
import typer
from pathlib import Path
from llmc.te.runner import TERunner

app = typer.Typer()

@app.command()
def test_mcp(
    mode: str = typer.Option("quick", help="Test mode: quick, standard, ruthless"),
    tools: list[str] = typer.Option(None, help="Specific tools to test"),
    output: Path = typer.Option(None, help="Output report path"),
    fail_fast: bool = typer.Option(False, help="Stop on first failure"),
):
    """Run MCP tool tests.
    
    Modes:
        quick    - Smoke tests only (~30s)
        standard - Core functionality (~2min)  
        ruthless - Edge cases, security, performance (~10min)
    """
    runner = RMTARunner(mode=mode, tools=tools, fail_fast=fail_fast)
    report = runner.run()
    
    if output:
        report.save(output)
    
    report.print_summary()
    raise typer.Exit(0 if report.passed else 1)
```

**File:** `llmc/rmta/runner.py` (new)

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class RMTARunner:
    mode: Literal["quick", "standard", "ruthless"]
    tools: list[str] | None = None
    fail_fast: bool = False
    
    def run(self) -> RMTAReport:
        """Execute test suite based on mode."""
        test_cases = self._discover_tests()
        results = []
        
        for test in test_cases:
            result = self._run_test(test)
            results.append(result)
            
            if self.fail_fast and not result.passed:
                break
        
        return RMTAReport(results=results)
    
    def _discover_tests(self) -> list[TestCase]:
        """Discover tests based on mode and tool filter."""
        base_dir = Path(__file__).parent.parent.parent / "tests" / "ruthless"
        
        if self.mode == "quick":
            pattern = "*_smoke.py"
        elif self.mode == "standard":
            pattern = "test_*.py"
        else:  # ruthless
            pattern = "**/*.py"
        
        tests = list(base_dir.glob(pattern))
        
        if self.tools:
            tests = [t for t in tests if any(tool in t.name for tool in self.tools)]
        
        return [TestCase(path=t) for t in tests]
```

### Acceptance Criteria
- [ ] `llmc test-mcp` command exists
- [ ] `--mode quick|standard|ruthless` works
- [ ] `--tools` filter works
- [ ] `--fail-fast` stops on first failure
- [ ] JSON report output with `--output`

---

## 4. Phase 3: CI Integration

### Goal
Add GitHub Actions workflow with quality gates.

**File:** `.github/workflows/mcp-tests.yml`

```yaml
name: MCP Tool Tests

on:
  push:
    paths:
      - 'llmc_mcp/**'
      - 'tests/ruthless/**'
  pull_request:
    paths:
      - 'llmc_mcp/**'

jobs:
  quick-smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e .[dev]
      - run: llmc test-mcp --mode quick
      
  standard-tests:
    runs-on: ubuntu-latest
    needs: quick-smoke
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e .[dev]
      - run: llmc test-mcp --mode standard --output report.json
      - uses: actions/upload-artifact@v4
        with:
          name: mcp-test-report
          path: report.json

  ruthless-weekly:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e .[dev]
      - run: llmc test-mcp --mode ruthless --output ruthless-report.json
```

### Quality Gates

```yaml
# In standard-tests job
- name: Check pass rate
  run: |
    PASS_RATE=$(jq '.pass_rate' report.json)
    if (( $(echo "$PASS_RATE < 0.95" | bc -l) )); then
      echo "Pass rate $PASS_RATE below 95% threshold"
      exit 1
    fi
```

### Acceptance Criteria
- [ ] CI runs on MCP file changes
- [ ] Quick smoke tests gate PRs
- [ ] Standard tests run on merge
- [ ] Ruthless tests run weekly
- [ ] 95% pass rate quality gate

---

## 5. Phase 4: Historical Tracking

### Goal
Track test results over time to detect regressions.

**File:** `llmc/rmta/history.py`

```python
import sqlite3
from datetime import datetime
from pathlib import Path

class RMTAHistory:
    """Track RMTA test results over time."""
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path.home() / ".local/share/llmc/rmta_history.db"
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_runs (
                id INTEGER PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                mode TEXT,
                total_tests INTEGER,
                passed INTEGER,
                failed INTEGER,
                pass_rate REAL,
                commit_sha TEXT,
                branch TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY,
                run_id INTEGER REFERENCES test_runs(id),
                test_name TEXT,
                tool TEXT,
                passed BOOLEAN,
                duration_ms INTEGER,
                error_message TEXT
            )
        """)
        conn.commit()
    
    def record_run(self, report: RMTAReport, commit_sha: str, branch: str):
        """Record a test run."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            INSERT INTO test_runs (mode, total_tests, passed, failed, pass_rate, commit_sha, branch)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (report.mode, report.total, report.passed, report.failed, report.pass_rate, commit_sha, branch))
        
        run_id = cursor.lastrowid
        for result in report.results:
            conn.execute("""
                INSERT INTO test_results (run_id, test_name, tool, passed, duration_ms, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (run_id, result.name, result.tool, result.passed, result.duration_ms, result.error))
        
        conn.commit()
    
    def detect_regressions(self, current: RMTAReport, window: int = 5) -> list[str]:
        """Detect tests that started failing recently."""
        conn = sqlite3.connect(self.db_path)
        
        regressions = []
        for result in current.results:
            if result.passed:
                continue
            
            # Check if this test passed in recent runs
            recent = conn.execute("""
                SELECT passed FROM test_results tr
                JOIN test_runs run ON tr.run_id = run.id
                WHERE tr.test_name = ?
                ORDER BY run.timestamp DESC
                LIMIT ?
            """, (result.name, window)).fetchall()
            
            if recent and all(r[0] for r in recent):
                regressions.append(result.name)
        
        return regressions
```

### Acceptance Criteria
- [ ] Test results stored in SQLite
- [ ] `detect_regressions()` identifies new failures
- [ ] CLI flag `--check-regressions` warns on new failures
- [ ] Historical trends visible via `llmc test-mcp --history`

---

## 6. Testing

```bash
# Phase 2 tests
pytest tests/rmta/test_runner.py -v

# Phase 3 - verify workflow syntax
yamllint .github/workflows/mcp-tests.yml

# Phase 4 tests
pytest tests/rmta/test_history.py -v
```

---

## 7. Files Created/Modified

| File | Change |
|------|--------|
| `llmc/commands/test_mcp.py` | New CLI command |
| `llmc/rmta/runner.py` | Test runner |
| `llmc/rmta/history.py` | Historical tracking |
| `.github/workflows/mcp-tests.yml` | CI workflow |
| `tests/rmta/test_runner.py` | Runner tests |
| `tests/rmta/test_history.py` | History tests |

---

## 8. Notes for Jules

1. **Start with Phase 2** - the orchestrator is the foundation
2. **Existing tests are in `tests/ruthless/`** - use those as the test corpus
3. **Don't reinvent pytest** - use subprocess to run existing tests
4. **Phase 3 can be a separate PR** after Phase 2 is merged
