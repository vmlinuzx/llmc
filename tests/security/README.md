# Security Testing Directory

This directory contains **security-focused tests and audit reports** for LLMC.

## 🎯 Purpose

While `tests/` contains functional tests, `tests/security/` contains:
- **Security audit reports** - Vulnerability assessments
- **Penetration tests** - Attack simulation results  
- **Exploit POCs** - Proof-of-concept code (for testing only!)
- **Security test cases** - Tests for security vulnerabilities

## 📁 Structure

```
tests/security/
├── REPORTS/              # Security audit reports
│   ├── *_security_audit.md
│   ├── *_pentest_report.md
│   └── *_threat_model.md
├── exploits/             # POC exploits (testing only)
│   └── *.py
├── test_auth.py          # Authentication tests
├── test_injection.py     # Injection attack tests
├── test_path_traversal.py # Path traversal tests
├── test_secrets.py       # Secrets exposure tests
└── README.md             # This file
```

## 🚀 Running Security Tests

### Quick Start

```bash
# Run the security testing agent
./tools/ren_ruthless_security_agent.sh "Audit the docgen feature"

# Run security test suite
pytest tests/security/ -v

# Run specific vulnerability tests
pytest tests/security/test_path_traversal.py -v
```

### Security Agent

The security agent (Ren the Penetration Testing Demon) focuses on:
- ✅ Attack surface analysis
- ✅ Threat modeling
- ✅ Malicious input testing
- ✅ Secrets scanning
- ✅ Dependency CVE checks
- ✅ Code injection probes
- ✅ Resource exhaustion tests

**vs. Functional agent** which focuses on:
- Correctness, performance, edge cases

## 📋 Security Test Types

### 1. Input Validation Tests
Test **malicious** inputs (not just invalid):
```python
# test_path_traversal.py
def test_blocks_directory_traversal():
    with pytest.raises(ValueError):
        process_file("../../../../etc/passwd")
```

### 2. Injection Tests
```python
# test_injection.py
def test_blocks_command_injection():
    malicious = "; rm -rf /"
    with pytest.raises(ValueError):
        execute_script(malicious)
```

### 3. Resource Limit Tests
```python
# test_resource_limits.py
def test_rejects_huge_files():
    huge_content = "x" * (100 * 1024 * 1024)  # 100MB
    with pytest.raises(ValueError, match="too large"):
        process_content(huge_content)
```

### 4. Secrets Exposure Tests
```python
# test_secrets.py
def test_no_secrets_in_logs(caplog):
    authenticate(user="test", password="secret123")
    assert "secret123" not in caplog.text
```

## 🔒 Security Tools

### Automated Scanners

```bash
# Secrets scanning
detect-secrets scan --all-files

# SAST (Static Application Security Testing)
bandit -r llmc/ -ll

# Dependency vulnerabilities
pip-audit

# All-in-one check
./tools/ren_ruthless_security_agent.sh
```

### Manual Code Review

```bash
# Find dangerous patterns
rg "subprocess.*shell\s*=\s*True" --type py
rg "\beval\(" --type py
rg "\bexec\(" --type py
rg "pickle\.loads" --type py

# Find potential secrets
rg -i "(password|secret|api[_-]?key|token)\s*=\s*['\"]" --type py
```

## ⚠️ Important Security Notes

### DO:
- ✅ Write POC exploits in `exploits/` for testing
- ✅ Test malicious inputs in safe environment
- ✅ Document vulnerabilities in `REPORTS/`
- ✅ Keep security tests up to date

### DON'T:
- ❌ Commit real credentials or secrets
- ❌ Run untrusted POC code without review
- ❌ Assume tests cover all attack vectors
- ❌ Ignore security test failures

## 🎯 What Makes a Good Security Test?

**Functional Test:**
```python
def test_accepts_valid_path():
    result = process_file("valid/path.py")
    assert result is not None
```

**Security Test:**
```python
def test_rejects_malicious_path():
    """Prevent path traversal attack."""
    malicious_paths = [
        "../../../../etc/passwd",
        "../../../root/.ssh/id_rsa",
        "/dev/zero",
    ]
    for path in malicious_paths:
        with pytest.raises(ValueError, match="path.*invalid"):
            process_file(path)
```

**Key Differences:**
- Security tests use **adversarial** inputs
- Security tests check **what's blocked**, not what's allowed
- Security tests think like **attackers**, not users

## 📊 Security Audit Reports

Reports in `REPORTS/` follow this format:

```markdown
# Security Audit - <Feature>

## Executive Summary
- Overall Risk: Critical/High/Medium/Low
- Vulnerabilities Found: X critical, Y high, Z medium

## Threat Model
- Attack surface
- Trust boundaries
- Adversaries

## Vulnerabilities
### VULN-001: Path Traversal
- Severity: High
- POC: <reproduction steps>
- Fix: <remediation>

## Recommendations
- P0: Must fix before production
- P1: Fix soon
- P2: Consider
```

## 🔄 Integration with CI/CD

```yaml
# .github/workflows/security.yml
security-scan:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    - name: Security Tests
      run: pytest tests/security/ -v
    - name: Secrets Scan
      run: detect-secrets scan
    - name: Dependency Audit
      run: pip-audit
```

## 📚 Learning Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)

---

**Remember:** Security is a process, not a checkbox. Keep testing! 🔒
