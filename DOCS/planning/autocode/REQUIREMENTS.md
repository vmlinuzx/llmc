# REQUIREMENTS: Installation Guide

**SDD Source:** DOCS/planning/SDD_Documentation_Architecture_2.0.md → Phase 2.1
**Target Document:** DOCS/getting-started/installation.md
**Audience:** End users, Developers, System Administrators

---

## Objective

Provide clear, step-by-step instructions for installing LLMC on supported systems. This guide covers the automatic installation script, manual pip installation, and developer setup, ensuring users can get the CLI running quickly.

---

## Acceptance Criteria

### AC-1: System Requirements

**Location:** DOCS/getting-started/installation.md, "Prerequisites" section

- **OS:** Linux (primary), macOS (supported). Windows (WSL2 recommended).
- **Python:** 3.10+ recommended (Project supports >=3.9).
- **Tools:** Git, pip, venv (recommended).
- **Hardware:** Minimal requirements (disk space for RAG index).

### AC-2: Quick Install (Recommended)

**Location:** DOCS/getting-started/installation.md, "Quick Install" section

- Provide the one-line `curl` installation command from `README.md`.
- Briefly explain what the script does (installs dependencies, sets up environment).

### AC-3: Manual Installation (Pip)

**Location:** DOCS/getting-started/installation.md, "Manual Installation" section

- Document installation via `pip` using the git repository URL (since PyPI status is unconfirmed/repo-based).
- Explain the `[rag,tui,agent]` extras and what they enable.
- **Critical:** Advise using a virtual environment.

### AC-4: Developer Installation

**Location:** DOCS/getting-started/installation.md, "Developer Setup" section

- Steps to clone the repository.
- Steps to install in editable mode (`pip install -e .`).
- Installing dev dependencies (if any specific ones are highlighted, otherwise standard extras).

### AC-5: Verification

**Location:** DOCS/getting-started/installation.md, "Verify Installation" section

- Command: `llmc-cli --version`.
- Expected output example.
- Command: `llmc-cli doctor` or similar simple check if available (using `repo register` or `help` as basic smoke test).

### AC-6: Troubleshooting

**Location:** DOCS/getting-started/installation.md, "Troubleshooting" section

- **PATH issues:** "command not found" -> adding `~/.local/bin` to PATH.
- **Permission errors:** avoiding `sudo` with pip, using venv.
- **Dependency conflicts:** standard advice.

---

## Style Requirements

- **Voice:** Direct, instructional.
- **Tense:** Imperative ("Run this command", "Install Python").
- **Terminology:**
  - "LLMC": The project/system.
  - "llmc-cli": The main command-line tool.
  - "RAG": Retrieval-Augmented Generation (context).
- **Formatting:** All commands in code blocks. Shell prompts (`$`) used to distinguish user input.

---

## Out of Scope

- ❌ Detailed configuration (covered in Configuration Guide).
- ❌ Usage tutorials (covered in User Guide).
- ❌ Deep architectural details.

---

## Verification

B-Team must verify:
1. The `curl` command matches the repository source.
2. The `pip` install command correctly targets the git repo and extras.
3. System requirements align with `pyproject.toml`.
4. No generic "Insert text here" placeholders.

---

**END OF REQUIREMENTS**
