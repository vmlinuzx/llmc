# REQUIREMENTS: Daemon Operations

**SDD Source:** DOCS/planning/SDD_Documentation_Architecture_2.0.md → Phase 3.2
**Target Document:** DOCS/operations/daemon.md
**Audience:** System operators, DevOps engineers, and power users running LLMC in a persistent state.

---

## Objective

This document explains how to manage the LLMC RAG daemon, which provides persistent indexing and search capabilities. It covers lifecycle management, configuration, monitoring, and troubleshooting.

---

## Acceptance Criteria

### AC-1: Daemon Lifecycle
**Location:** DOCS/operations/daemon.md, section "Daemon Management"

- Explain how to start the daemon (`llmc-rag-daemon start`)
- Explain how to stop the daemon (`llmc-rag-daemon stop`)
- Explain how to check status (`llmc-rag-daemon status`)
- Mention foreground mode if applicable (or how to debug startup)

### AC-2: Configuration
**Location:** DOCS/operations/daemon.md, section "Configuration"

- Detail the `[daemon]` section of `llmc.toml`
- Explain key settings: port, host, worker count, log level
- Provide a standard example configuration snippet

### AC-3: Logging & Observability
**Location:** DOCS/operations/daemon.md, section "Logging & Monitoring"

- Define where logs are stored (default locations for Linux/Mac)
- Explain how to change log locations
- Mention how to tail logs for troubleshooting
- Explain health check endpoints or commands

### AC-4: Service Integration (Optional/Advanced)
**Location:** DOCS/operations/daemon.md, section "Service Integration"

- Provide a basic systemd unit file example for Linux
- Provide a basic launchd plist example for macOS (if known/standard)
- Explain why running as a system service is beneficial (auto-restart, boot time start)

---

## Style Requirements

- Voice: Technical, instructional, direct
- Tense: Present
- Terminology:
    - **Daemon:** The background process (`llmc-rag-daemon`)
    - **Service:** The system-level service wrapper (systemd/launchd)
    - **RAG:** Retrieval-Augmented Generation (context for why the daemon exists)
- Max section length: Keep instructions concise

---

## Out of Scope

- ❌ Detailed internal architecture of the daemon (belongs in `architecture/`)
- ❌ Client-side API usage (belongs in `reference/`)
- ❌ Deep debugging of the RAG engine itself (belongs in `troubleshooting.md`)

---

## Verification

B-Team must verify:
1. All AC sections exist with required content
2. Commands are accurate based on current CLI (`llmc-rag-daemon`)
3. Configuration examples match `llmc.toml` schema
4. Systemd/launchd examples are syntactically correct

---

**END OF REQUIREMENTS**