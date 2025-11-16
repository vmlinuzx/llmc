# SDD (Implementation) – LLMC-6 Repo Cleanup & Layout

## TL;DR

This document describes the **concrete implementation steps** for the LLMC-6 repo cleanup:

- Add a `legacy/` directory and move backup files there.
- Add or update repo-level docs (`README.md`, SDDs, and prompts).
- Leave all runtime packages (`tools/*`) in place to avoid import breakage.

This is deliberately small-scope so it can be applied just before a release.

---

## Scope

In scope:

- Directory creation (`legacy/`).
- Moving unreferenced backup artifacts into `legacy/`.
- Creating documentation files under `DOCS/design/` and at the repo root.

Out of scope (for this iteration):

- Renaming any Python packages or modules.
- Changing imports in existing code.
- Large-scale script refactors.

---

## Target layout (post-implementation)

See the main SDD for the conceptual layout. After this implementation:

```text
./
├─ .github/
├─ AGENTS.md
├─ CONTRACTS.md
├─ DOCS/
│  ├─ design/
│  │  ├─ SDD_LLMC6_Repo_Structure.md
│  │  ├─ SDD_Impl_LLMC6_Repo_Structure.md
│  │  └─ (existing SDDs…)
│  ├─ LLMC_RAG_Background_Services_System_Overview.md
│  └─ (existing docs…)
├─ legacy/
│  ├─ README.md
│  └─ tools_rag_service.py.backup
├─ scripts/
├─ tests/
├─ tools/
│  ├─ rag/
│  ├─ rag_daemon/
│  └─ rag_repo/
├─ llmc.toml
├─ pyproject.toml
└─ README.md
```

---

## Implementation steps

These steps assume you are on a feature branch (e.g., `feat/llmc6-repo-cleanup`).

1. **Create `legacy/` directory**

   - Add `legacy/` at the repo root.
   - Add `legacy/README.md` explaining that:
     - The folder is for deprecated/backup code only.
     - Nothing should import from `legacy/` in production paths.

2. **Move backup artifacts**

   - Move `tools/rag/service.py.backup` → `legacy/tools_rag_service.py.backup`.
   - Confirm there are **no imports or references** to `service.py.backup`:
     - e.g., `rg "service.py.backup" -n` from repo root.
   - If any references exist, either:
     - update them to use the live `tools.rag.service` implementation, or
     - postpone the move and document the dependency.

3. **Add repo-level README**

   - Create `README.md` at the repo root (if missing).
   - Include:
     - Short TL;DR of what LLMC-6 is and does.
     - A high-level repo map (1–2 levels).
     - A simple mermaid diagram of how daemon, repo tool, and RAG core interact.
     - Pointers to key docs under `DOCS/`.

4. **Add SDDs for repo structure**

   - `DOCS/design/SDD_LLMC6_Repo_Structure.md` – conceptual SDD.
   - `DOCS/design/SDD_Impl_LLMC6_Repo_Structure.md` – this implementation plan.

5. **Add agent prompt for implementation**

   - Create `DOCS/AgentPrompt_LLMC6_Repo_Cleanup.md` with a ready-to-paste prompt
     that:
     - Describes the cleanup goal.
     - Asks the agent to follow **best GitHub practices**:
       - feature branch
       - small commits
       - clear commit messages
       - running tests before pushes
       - PR with checklist.

---

## Testing & validation

After implementing the cleanup:

1. **Lint for invalid imports**

   - Run a fast grep to ensure nothing references `legacy/` as a module path.
   - Confirm `tools.rag.service` is the only `service.py` used at runtime.

2. **Run tests**

   ```bash
   pytest tests -q
   ```

   - All existing tests should still pass.
   - No new tests are required for moving the backup file.

3. **Smoke test with your wrapper/TUI**

   - From your usual LLMC environment, run a smoke test:
     - Start the daemon as you normally do.
     - Trigger a simple RAG operation via your TUI or wrapper.
   - Confirm logs and behavior look unchanged.

---

## Rollout plan

1. Implement the cleanup on a feature branch.
2. Open a PR with:
   - Summary of changes.
   - Confirmation that tests pass.
   - Short diff of new/removed files and where the backup went.
3. Merge after a quick review (even if self-review), before your “go live” deadline.

If something goes sideways, you can revert the PR or reset to a pre-cleanup tag.

---

## Follow-ups (post-release)

Once LLMC-6 is live and stable:

- Revisit the idea of:
  - A dedicated `llmc_core/` package.
  - Normalized CLI entrypoints and packaging.
- Expand documentation for:
  - Deployment patterns (tmux/systemd, k8s, etc.).
  - Integration with LLMC TUIs and adapters.
