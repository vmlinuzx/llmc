# LLMC Security Audit Report

**Date:** 2025-12-14  
**Auditor:** Antigravity  
**Scope:** Full codebase `/home/vmlinux/src/llmc`

---

## 🔴 CRITICAL ISSUES

### 1. DeepSeek API Key in Git History (FIXED)

**Location:** `tools/deepseek_agent.sh` (commit `43d17e3`)  
**Status:** ✅ FIXED in commit `168730f`  
**Impact:** API key exposed in local git history  
**Risk:** Medium (not pushed to GitHub)

**Remediation:**
- [x] Key removed from current file, uses env var
- [ ] **ROTATE THE KEY** on DeepSeek dashboard
- [ ] Consider rebasing to remove from history before push

---

## 🟡 MODERATE ISSUES

### 2. Code Execution via `exec()` in MCP

**Location:** `llmc_mcp/tools/code_exec.py:291`  
**Mitigation:** ✅ Isolation check exists (`require_isolation()`)

```python
exec(compiled, namespace)
```

**Status:** ACCEPTABLE — Protected by isolation detection that blocks execution unless running in Docker/K8s/nsjail.

**Recommendation:** Ensure `mcp.code_execution.enabled = false` in production configs (currently is).

---

### 3. Hardcoded Internal IPs in Config

**Locations:**
- `llmc.toml:218,302` — `100.64.0.6:11434` (Tailscale IP)
- `config/medical_defaults.toml:23` — `athena:11434`
- Various test files

**Impact:** Low — Internal network IPs, not secrets  
**Recommendation:** Move to env vars or `.env.local` for portability

---

### 4. SQL Statement Construction with f-strings

**Locations:**
- `tools/rag/db_fts.py:75` — `f"PRAGMA table_info({table})"`
- `tools/rag/database.py:187` — `f"ALTER TABLE {table} ADD COLUMN..."`
- `scripts/migrate_add_enrichment_metrics.py:58`

**Impact:** Low — Table/column names are not user input  
**Recommendation:** Use constants or validate against allowlist

---

## 🟢 NO ISSUES FOUND

| Check | Result |
|-------|--------|
| `.env` files in repo | ✅ None found |
| Private keys (`.pem`, `.key`) | ✅ None found |
| Unsafe YAML loading | ✅ None found |
| Pickle deserialization | ✅ None found |
| AWS/GCP credentials | ✅ None (example key in test fixture only) |
| GitHub tokens | ✅ None found |
| `.gitignore` coverage | ✅ Covers `.env*`, tokens |

---

## 📋 CONFIGURATION REVIEW

### Positive Security Controls

1. **MCP Code Execution** — Defaults to disabled:
   ```toml
   [mcp.code_execution]
   enabled = false  # Disabled by default
   ```

2. **Isolation Detection** — `llmc_mcp/isolation.py` blocks dangerous tools on bare metal

3. **Tool Allowlist** — `run_cmd` has command allowlist:
   ```toml
   run_cmd_allowlist = ["bash", "sh", "rg", "grep", ...]
   ```

4. **Filesystem Roots** — MCP tools restricted to specific paths:
   ```toml
   allowed_roots = ["/home/vmlinux/src"]
   ```

---

## 📝 RECOMMENDATIONS

### Immediate (Do Now)

1. **ROTATE DEEPSEEK API KEY** — Even though it wasn't pushed, the key is in local git history

### Before Push

2. **Rebase to remove key from history:**
   ```bash
   git rebase -i HEAD~12  # Find commit 43d17e3 and edit it
   ```
   Or use `git-filter-repo` to scrub the key

### Nice to Have

3. Move internal IPs to environment variables
4. Add pre-commit hook for secret scanning:
   ```bash
   pip install detect-secrets
   detect-secrets scan > .secrets.baseline
   ```

---

## ✅ AUDIT SUMMARY

| Category | Status |
|----------|--------|
| Hardcoded Secrets | ⚠️ 1 found (fixed) |
| Code Injection | ✅ Protected |
| SQL Injection | ✅ Low risk |
| Deserialization | ✅ Clean |
| File Permissions | ✅ Clean |
| Network Exposure | ⚠️ Internal IPs exposed (low risk) |

**Overall:** 🟡 **PASS with remediation required** — Rotate the DeepSeek key.

---

**END OF REPORT**
