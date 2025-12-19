# SDD: Onboarding Polish (Roadmap 2.5)

**Date:** 2025-12-19  
**Author:** Dave + Antigravity  
**Status:** Ready for Implementation  
**Priority:** P2  
**Effort:** 6-8 hours  
**Assignee:** Jules  

---

## 1. Executive Summary

Improve the repository onboarding experience by automating validation, integrating with `rag doctor`, and checking embedding model availability upfront.

**Current Pain Points:**
- Users run `llmc repo register .` but don't know if it worked
- No automatic health check after registration
- Embedding model issues only discovered during enrichment (too late)

---

## 2. Tasks Overview

| Task | Description | Effort |
|------|-------------|--------|
| 1 | Auto-run validation after `repo add` | 2h |
| 2 | Integration with `rag doctor` | 2h |
| 3 | Embedding model availability check | 2h |

---

## 3. Task 1: Auto-Run Validation After `repo add`

### Goal
After `llmc repo register`, automatically run validation and report status.

### Current Behavior
```bash
$ llmc repo register .
Repository registered: /home/user/myrepo
# User has no idea if it's working
```

### New Behavior
```bash
$ llmc repo register .
Repository registered: /home/user/myrepo

Validating setup...
  ✓ .llmc/ directory created
  ✓ Config written to .llmc/config.toml
  ✓ Embedding model available (nomic-embed-text)
  ✓ Ollama reachable at localhost:11434
  ✓ Initial scan: 847 files, 12,453 spans

Ready! Run 'llmc rag enrich' to add AI summaries.
```

### Implementation

**File:** `llmc/commands/repo.py`

```python
@app.command()
def register(
    path: str = typer.Argument(".", help="Path to repository"),
    skip_validation: bool = typer.Option(False, help="Skip post-registration validation"),
):
    """Register a repository with LLMC."""
    repo_path = Path(path).resolve()
    
    # Existing registration logic...
    _do_register(repo_path)
    
    console.print(f"Repository registered: {repo_path}")
    
    if not skip_validation:
        console.print("\n[bold]Validating setup...[/bold]")
        _run_post_registration_validation(repo_path)


def _run_post_registration_validation(repo_path: Path) -> bool:
    """Run validation checks after registration."""
    from llmc.rag.doctor import run_rag_doctor
    from llmc.rag.embeddings import check_embedding_model
    
    all_passed = True
    
    # Check 1: .llmc directory exists
    llmc_dir = repo_path / ".llmc"
    if llmc_dir.exists():
        console.print("  [green]✓[/green] .llmc/ directory created")
    else:
        console.print("  [red]✗[/red] .llmc/ directory missing")
        all_passed = False
    
    # Check 2: Config file exists
    config_file = llmc_dir / "config.toml"
    if config_file.exists():
        console.print("  [green]✓[/green] Config written to .llmc/config.toml")
    else:
        console.print("  [red]✗[/red] Config file missing")
        all_passed = False
    
    # Check 3: Embedding model available
    model_status = check_embedding_model()
    if model_status.available:
        console.print(f"  [green]✓[/green] Embedding model available ({model_status.model})")
    else:
        console.print(f"  [yellow]![/yellow] Embedding model not available: {model_status.error}")
        console.print("    Run: ollama pull nomic-embed-text")
    
    # Check 4: Ollama reachable
    ollama_status = check_ollama_connection()
    if ollama_status.reachable:
        console.print(f"  [green]✓[/green] Ollama reachable at {ollama_status.url}")
    else:
        console.print(f"  [yellow]![/yellow] Ollama not reachable: {ollama_status.error}")
    
    # Check 5: Initial scan stats
    doctor_report = run_rag_doctor(repo_path)
    files = doctor_report.get("files", 0)
    spans = doctor_report.get("spans", 0)
    console.print(f"  [green]✓[/green] Initial scan: {files:,} files, {spans:,} spans")
    
    if all_passed:
        console.print("\n[green]Ready![/green] Run 'llmc rag enrich' to add AI summaries.")
    else:
        console.print("\n[yellow]Some checks failed.[/yellow] Run 'llmc rag doctor' for details.")
    
    return all_passed
```

### Acceptance Criteria
- [ ] Validation runs automatically after `repo register`
- [ ] `--skip-validation` flag bypasses checks
- [ ] Clear ✓/✗ indicators for each check
- [ ] Actionable next-step suggestions

---

## 4. Task 2: Integration with `rag doctor`

### Goal
Make `rag doctor` the single source of truth for repository health.

### Current State
`llmc rag doctor` exists but is not integrated with onboarding.

### Enhancement

**File:** `llmc/rag/doctor.py`

Add new checks:

```python
def run_rag_doctor(repo_root: Path) -> dict:
    """Run comprehensive health checks on RAG setup."""
    report = {
        "status": "OK",
        "checks": [],
        "warnings": [],
        "errors": [],
    }
    
    # Existing checks...
    
    # NEW: Check embedding model
    model_check = _check_embedding_model()
    report["checks"].append(model_check)
    if not model_check["passed"]:
        report["warnings"].append(model_check["message"])
    
    # NEW: Check Ollama connection
    ollama_check = _check_ollama()
    report["checks"].append(ollama_check)
    if not ollama_check["passed"]:
        report["warnings"].append(ollama_check["message"])
    
    # NEW: Check for stale index
    staleness_check = _check_index_staleness(repo_root)
    report["checks"].append(staleness_check)
    if staleness_check["stale_files"] > 0:
        report["status"] = "STALE"
        report["warnings"].append(f"{staleness_check['stale_files']} files need re-indexing")
    
    return report


def _check_embedding_model() -> dict:
    """Check if embedding model is available."""
    from llmc.rag.embeddings import get_default_embedder
    
    try:
        embedder = get_default_embedder()
        # Quick smoke test
        embedder.embed(["test"])
        return {"name": "embedding_model", "passed": True, "model": embedder.model_name}
    except Exception as e:
        return {"name": "embedding_model", "passed": False, "message": str(e)}


def _check_ollama() -> dict:
    """Check Ollama connectivity."""
    import httpx
    
    try:
        resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            return {"name": "ollama", "passed": True, "models": len(models)}
    except Exception as e:
        return {"name": "ollama", "passed": False, "message": str(e)}
    
    return {"name": "ollama", "passed": False, "message": "Unexpected response"}
```

### Acceptance Criteria
- [ ] `rag doctor` checks embedding model availability
- [ ] `rag doctor` checks Ollama connectivity
- [ ] `rag doctor` reports stale file count
- [ ] JSON output includes all checks

---

## 5. Task 3: Embedding Model Availability Check

### Goal
Check embedding model availability upfront, before any operations that need it.

### Implementation

**File:** `llmc/rag/embeddings/check.py` (new)

```python
from dataclasses import dataclass
import httpx

@dataclass
class ModelStatus:
    available: bool
    model: str
    error: str | None = None

def check_embedding_model(model: str = None) -> ModelStatus:
    """Check if the configured embedding model is available.
    
    Args:
        model: Model name to check, or None for default
        
    Returns:
        ModelStatus with availability info
    """
    from llmc.config import get_llmc_config
    
    config = get_llmc_config()
    model = model or config.get("embedding_model", "nomic-embed-text")
    
    # Check Ollama first
    try:
        resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code != 200:
            return ModelStatus(available=False, model=model, error="Ollama not responding")
        
        available_models = [m["name"] for m in resp.json().get("models", [])]
        
        # Check exact match or prefix match (e.g., "nomic-embed-text" matches "nomic-embed-text:latest")
        for available in available_models:
            if available == model or available.startswith(f"{model}:"):
                return ModelStatus(available=True, model=available)
        
        return ModelStatus(
            available=False, 
            model=model, 
            error=f"Model '{model}' not found. Run: ollama pull {model}"
        )
        
    except httpx.ConnectError:
        return ModelStatus(available=False, model=model, error="Cannot connect to Ollama at localhost:11434")
    except Exception as e:
        return ModelStatus(available=False, model=model, error=str(e))


def require_embedding_model(model: str = None) -> str:
    """Ensure embedding model is available, or raise helpful error.
    
    Returns:
        The available model name
        
    Raises:
        RuntimeError: If model is not available
    """
    status = check_embedding_model(model)
    
    if status.available:
        return status.model
    
    raise RuntimeError(
        f"Embedding model not available: {status.error}\n"
        f"To fix:\n"
        f"  1. Start Ollama: ollama serve\n"
        f"  2. Pull model: ollama pull {status.model}\n"
    )
```

### Usage in Enrichment Pipeline

**File:** `llmc/rag/enrichment/pipeline.py`

```python
from llmc.rag.embeddings.check import require_embedding_model

async def run_enrichment(repo_root: Path):
    """Run enrichment pipeline."""
    # Check model availability FIRST
    model = require_embedding_model()
    console.print(f"Using embedding model: {model}")
    
    # ... rest of enrichment
```

### Acceptance Criteria
- [ ] `check_embedding_model()` returns status without side effects
- [ ] `require_embedding_model()` raises helpful error if unavailable
- [ ] Enrichment pipeline checks model before starting
- [ ] Error message includes fix instructions

---

## 6. Testing

```bash
# Task 1 - validation after register
llmc repo register /tmp/test-repo
# Should show validation output

# Task 2 - rag doctor enhancements
llmc rag doctor
# Should show embedding/ollama checks

# Task 3 - embedding check
python -c "from llmc.rag.embeddings.check import check_embedding_model; print(check_embedding_model())"
```

---

## 7. Files Created/Modified

| File | Change |
|------|--------|
| `llmc/commands/repo.py` | Add post-registration validation |
| `llmc/rag/doctor.py` | Add embedding/ollama checks |
| `llmc/rag/embeddings/check.py` | New model availability checker |
| `llmc/rag/enrichment/pipeline.py` | Use `require_embedding_model()` |
| `tests/rag/test_onboarding.py` | New tests |

---

## 8. Notes for Jules

1. **Start with Task 3** - the embedding check is used by Tasks 1 and 2
2. **Don't break existing behavior** - `repo register` should still work without Ollama
3. **Warnings vs Errors** - Ollama issues should be warnings, not hard failures
4. **Test without Ollama** - ensure graceful degradation when Ollama is unavailable
