---
description: Validate and update LLMC documentation against the Diátaxis architecture spec
---

# Documentation Validation Workflow

This workflow validates all documentation under `DOCS/` against the project's documentation architecture defined in `DOCS/planning/SDD_Documentation_Architecture_2.0.md`.

## Reference Spec

Before starting, read and understand:
- `DOCS/planning/SDD_Documentation_Architecture_2.0.md` (Diátaxis architecture)
- `DOCS/index.md` (master entry point)

## Scope

**In Scope:**
- `DOCS/getting-started/`
- `DOCS/user-guide/`
- `DOCS/operations/`
- `DOCS/architecture/`
- `DOCS/reference/`
- `DOCS/development/`

**Out of Scope:**
- `DOCS/planning/` (active SDDs, roadmap - these are "living" docs)
- `DOCS/legacy/` (archived, don't touch)
- `DOCS/research/` (exploratory, don't touch)

---

## Phase 1: Discovery

For each markdown file in scope:

```bash
find DOCS/getting-started DOCS/user-guide DOCS/operations DOCS/architecture DOCS/reference DOCS/development -name "*.md" -type f 2>/dev/null
```

Record the full list of documents to validate.

---

## Phase 2: Validation Checklist

For **each document**, validate against these criteria:

### A. Structural Validation
- [ ] Follows Diátaxis classification (Tutorial / HowTo / Reference / Explanation)
- [ ] Located in correct directory per the architecture spec
- [ ] Has proper frontmatter or title (`# Title` as first line)
- [ ] Has an entry in the parent `index.md` (if applicable)

### B. Link Validation
- [ ] All internal markdown links resolve to existing files
- [ ] All anchor links (`#section`) reference valid headings
- [ ] No links to moved/renamed files

### C. CLI/Code Currency
- [ ] CLI commands match current `--help` output
- [ ] File paths reference files that exist in the codebase
- [ ] Code examples use current API patterns

To verify CLI commands:
```bash
# Example verification
llmc-cli <command> --help
python3 -m llmc.rag.cli <command> --help
```

### D. Content Currency
- [ ] No references to deprecated features
- [ ] Config examples match current `llmc.toml` schema
- [ ] Module paths reflect current package structure (e.g., `llmc.rag` not `tools.rag`)

---

## Phase 3: Conservative Corrections

**ALLOWED without approval:**
- Fix broken internal links to known-correct destinations
- Update CLI command examples if the new command is clearly correct
- Fix obvious typos or grammar errors
- Update file paths that have moved to known locations
- Update module paths (`tools.rag.cli` → `llmc.rag.cli`)

**NOT ALLOWED without approval:**
- Rewriting sections for style or clarity
- Adding new content
- Removing content (even if seemingly outdated)
- Changing document location/structure
- Deleting files

If unsure, **flag for human review** instead of making the change.

---

## Phase 4: Reporting

Create or update `DOCS/.validation-report.md` with:

```markdown
# Documentation Validation Report

**Generated:** YYYY-MM-DD
**Validator:** [Agent Name]

## Summary

| Status | Count |
|--------|-------|
| ✅ CURRENT | X |
| ⚠️ NEEDS_UPDATE | Y |
| 🔴 CRITICAL | Z |

## Document Status

### ✅ Current Documents
- `path/to/doc.md` — No issues

### ⚠️ Documents Needing Updates
- `path/to/doc.md`
  - Issue: [description]
  - Fix Applied: [description] OR Flagged for review

### 🔴 Critical Issues
- `path/to/doc.md`
  - Issue: [description of major problem]
  - Action Required: [what human needs to do]

## Changes Made This Run
1. `file.md`: [what was changed]
2. ...

## Flagged for Human Review
1. `file.md`: [why this needs human attention]
2. ...
```

---

## Phase 5: Create Pull Request (MANDATORY)

**NEVER commit directly to main.** Always create a PR for review.

If changes were made:

```bash
# 1. Create a feature branch
git checkout -b doc-validation-$(date +%Y%m%d)

# 2. Stage and commit changes
git add DOCS/
git commit -m "docs: validation pass - update stale links and CLI examples

- Fixed X broken internal links
- Updated Y CLI command examples
- Flagged Z items for human review

See DOCS/.validation-report.md for details"

# 3. Push and create PR
git push -u origin doc-validation-$(date +%Y%m%d)
gh pr create --title "docs: validation pass $(date +%Y-%m-%d)" \
  --body "Automated documentation validation run.

## Changes
- See commit message for summary
- See \`DOCS/.validation-report.md\` for full report

## Review Notes
Review the changes and merge if acceptable."
```

**This is not optional.** Jules must create a PR. Dave will review and merge.

---

## Exit Criteria

- [ ] All in-scope documents validated
- [ ] Validation report generated at `DOCS/.validation-report.md`
- [ ] Conservative fixes applied where safe
- [ ] Items needing human judgment flagged clearly
- [ ] Changes committed (but not pushed)
