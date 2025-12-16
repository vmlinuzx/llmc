# REQUIREMENTS: Quickstart Guide

**SDD Source:** DOCS/planning/SDD_Documentation_Architecture_2.0.md → Phase 2.2
**Target Document:** DOCS/getting-started/quickstart.md
**Audience:** New users who have just installed LLMC.

---

## Objective

Create a concise, 5-minute tutorial that guides a new user from their first interaction with the CLI to a successful semantic search. The goal is instant gratification and verification that the system works.

---

## Acceptance Criteria

### AC-1: Prerequisites Check

**Location:** Top of file

[Specific content requirements:]
- Briefly mention that LLMC must be installed.
- Link to `installation.md` for those who haven't installed it.
- Verify installation with `llmc-cli --version`.

### AC-2: Initialize a Repository

**Location:** Section "Step 1: Add a Repository"

[Specific content requirements:]
- Command: `llmc-cli repo add <path>` (use current directory `.` or a safe example).
- Explain briefly what this does (registers the directory for tracking).
- Sample output block showing success message.

### AC-3: Create the Index

**Location:** Section "Step 2: Index Your Code"

[Specific content requirements:]
- Command: `llmc-cli index`
- Explain that this parses code and generates embeddings.
- Note that the first run might take a moment depending on repo size.
- Sample output block showing progress/completion.

### AC-4: Execute First Search

**Location:** Section "Step 3: Search"

[Specific content requirements:]
- Command: `llmc-cli search "query"`
- Provide a generic query likely to work in most repos (e.g., "how do I configure this" or similar, or just "file handling").
- Explain the output structure (file path, relevance score, snippet).
- Sample output block showing a realistic result.

### AC-5: What's Next

**Location:** Bottom of file

[Specific content requirements:]
- Link to `../user-guide/cli-reference.md` (CLI Reference).
- Link to `../user-guide/configuration.md` (Configuration).
- Link to `concepts.md` (Core Concepts).

---

## Style Requirements

- Voice: Direct, instructional, encouraging.
- Tense: Imperative ("Run this command", "Type this").
- Terminology: Use "Repository" for the code being indexed, "Index" for the database of embeddings.
- Length: Keep it under 500 words. Speed is key.

---

## Out of Scope

- ❌ configuring `llmc.toml` (defaults should work).
- ❌ explaining RAG architecture in depth.
- ❌ troubleshooting complex errors.

---

## Verification

B-Team must verify:
1. All commands are copy-pasteable.
2. Output examples look realistic.
3. Links to other docs use relative paths correctly.

---

**END OF REQUIREMENTS**
