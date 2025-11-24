# Ship-Worthy Refactor: Production Deployment Readiness Plan

## Objective

Make the LLMC repository production-ready so users can:
- Clone from GitHub
- Configure via `llmc.toml` without touching code
- Deploy without encountering hardcoded paths, IPs, or system-specific assumptions

This plan builds on the completed path refactoring work and addresses remaining deployment blockers.

---

## User Review Required

> [!IMPORTANT]
> **Configuration Breaking Changes**
> The `llmc.toml` file currently contains your personal LLM server IP (`192.168.5.20`) and hostname (`athena`). These will need to be replaced with example values, and we'll create a `llmc.toml.example` template for new users.

> [!CAUTION]
> **Test Portability Issues**
> Found hardcoded paths in `tests/test_analyzer.py` that write to `/home/vmlinux/src/llmc/tests/ruthless_test_analysis.json`. Need dynamic path resolution so users can run your test suite without modifications.

---

## Proposed Changes

### Configuration Files

#### [MODIFY] [llmc.toml](file:///home/vmlinux/src/llmc/llmc.toml)

**Current issues:**
- Hardcoded IP: `192.168.5.20` (Dave's local LLM server)
- Hardcoded hostname: `athena` (Dave's machine name)

**Action:**
- Replace with localhost/example values
- Add clear comments explaining configuration options

#### [NEW] [llmc.toml.example](file:///home/vmlinux/src/llmc/llmc.toml.example)

**Purpose:**
- Template for new users
- Documents all available options
- Shows multiple backend examples: local Ollama, remote Ollama, cloud APIs
- Users copy to `llmc.toml` and customize

---

### Scripts & Enrichment

#### [MODIFY] [scripts/qwen_enrich_batch.py](file:///home/vmlinux/src/llmc/scripts/qwen_enrich_batch.py)

**Current issues:**
- Localhost fallback at line 333: `os.environ.get("OLLAMA_URL", "http://localhost:11434")`
- Default model fallback at line 644: `os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")`
- `ATHENA_OLLAMA_URL` environment variable references (line 112)

**Action:**
- **Remove ALL hardcoded localhost fallbacks** - fail explicitly with helpful error if config missing
- Remove `ATHENA_OLLAMA_URL` environment variable logic (Dave-specific)
- Ensure all LLM endpoints come from `llmc.toml` enrichment chains
- Add validation that prints helpful error: "No enrichment chain configured. Please configure [enrichment.chain] in llmc.toml"

---

### Tests (For Contributors & Quality Signal)

#### [MODIFY] [tests/test_analyzer.py](file:///home/vmlinux/src/llmc/tests/test_analyzer.py)

**Current issue:**
- Lines 137, 140: Hardcoded output path `/home/vmlinux/src/llmc/tests/ruthless_test_analysis.json`

**Action:**
- Use dynamic path resolution: `Path(__file__).parent / "ruthless_test_analysis.json"`
- Ensures users/contributors can run test suite anywhere

#### [MODIFY] Test fixtures using `athena` hostname

**Files:**
- `tests/test_enrichment_adapters.py`
- `tests/test_enrichment_cascade_builder.py`
- `tests/test_enrichment_config.py`

**Action:**
- Keep `athena` in test fixtures - it's a valid test hostname
- Add comment explaining it's a test value, not a requirement
- Tests should pass with any valid LLM endpoint configured

---

### Documentation

#### [NEW] [DOCS/DEPLOYMENT.md](file:///home/vmlinux/src/llmc/DOCS/DEPLOYMENT.md)

**Contents:**
- **Prerequisites section**: Python version, system requirements, optional dependencies
- **Quick start guide**: Clone, setup venv, install, configure
- **Configuration guide**: 
  - How to set up `llmc.toml` from example
  - Explanation of enrichment chains
  - Local vs remote LLM configuration
  - Environment variable options (minimal, config-first approach)
- **Common deployment issues**: Missing config, LLM connection failures, permission errors
- **Docker considerations** (if applicable)

#### [MODIFY] [README.md](file:///home/vmlinux/src/llmc/README.md)

**Current state:** Good, but assumes user knows about paths and configuration

**Action:**
- Add "Getting Started" section at top
- Link to `DEPLOYMENT.md` for detailed setup
- Add "Configuration" section explaining `llmc.toml`
- Add troubleshooting section

---

### Repository Structure

#### [MODIFY] [.gitignore](file:///home/vmlinux/src/llmc/.gitignore)

**Additions needed:**
- `llmc.toml` (user-specific config, shouldn't leak to other users)
- Ensure `llmc.toml.example` is NOT ignored

> [!NOTE]
> **Tests Ship But Are Optional**
> The `tests/` directory provides quality signal and enables contributors to verify changes. However, tests need to be portable (no hardcoded `/home/vmlinux` paths). The `patches/` directory is dev-only and can have whatever.

> [!WARNING]
> **Existing vs New Users**
> Your current `llmc.toml` with personal settings should be preserved locally. We'll add `llmc.toml` to `.gitignore` AFTER creating `llmc.toml.example`, so your config stays private but new users get a clean template.

---

## Verification Plan

### Code Audit

#### 1. Grep for Hardcoded Values in Production Code
```bash
cd /home/vmlinux/src/llmc
# Should return no results in production code:
grep -r "192.168" --include="*.py" scripts/ tools/ llmcwrapper/
grep -r "/home/vmlinux" --include="*.py" scripts/ tools/ llmcwrapper/ tests/
grep -r "athena" --include="*.py" --include="*.toml" scripts/ tools/ llmcwrapper/ | grep -v "example"
```
**Expected:** Zero matches in production code. Tests can use `athena` as test hostname but shouldn't have `/home/vmlinux` hardcoded paths.

#### 2. Test Suite Portability
```bash
cd /home/vmlinux/src/llmc
source .venv/bin/activate
# Run a few critical tests to verify no path issues:
pytest tests/test_analyzer.py -v
pytest tests/test_enrichment_adapters.py -v
```
**Expected:** Tests run successfully without errors about missing `/home/vmlinux` paths

### Manual Verification

#### 4. Fresh Clone Simulation

Create a test environment simulating a new user:

```bash
# In a temp directory as a different user or VM
cd /tmp
git clone /home/vmlinux/src/llmc test-llmc-fresh
cd test-llmc-fresh
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[rag]"
```

**Then test configuration:**
```bash
# Should exist as template:
ls llmc.toml.example

# Should fail with helpful error (no config yet):
llmc-rag-daemon config

# Copy and configure:
cp llmc.toml.example llmc.toml
# Edit llmc.toml with local settings
# Verify it works:
llmc-rag-daemon config --json
```

**Expected results:**
- No errors about missing hardcoded paths
- Clear error messages when config is missing
- System works after copying example config

#### 5. Enrichment Configuration Validation

Test that enrichment requires explicit config:

```bash
cd /home/vmlinux/src/llmc
# Temporarily rename llmc.toml
mv llmc.toml llmc.toml.backup

# Try to run enrichment - should fail with clear message
scripts/qwen_enrich_batch.py --repo . --dry-run-plan

# Restore config
mv llmc.toml.backup llmc.toml
```

**Expected:** Clear error message explaining missing enrichment chain configuration, NOT a localhost fallback.

---

## Questions for Dave

1. **llmc.toml strategy:** Should we:
   - A) Keep your `llmc.toml` in repo but add `llmc.toml.example` for new users?
   - B) Move your config to `llmc.toml.local` (gitignored) and make `llmc.toml` the example?
   - C) Rename your `llmc.toml` to something else, create example as `llmc.toml`, you maintain local override?

2. **Dave-specific env vars:** Safe to remove `ATHENA_OLLAMA_URL` references entirely from production code (`scripts/`, `tools/`)?

3. **Priority:** Which blockers are most critical:
   - Configuration examples?
   - Hardcoded localhost fallback removal?
   - Deployment documentation?
   - All of the above?
