# Minimal Claude Desktop Commander Kickoff – LLMC + TE

Use this as the shorter kickoff prompt for Claude Desktop Commander when working in the LLMC repo.

---

## Prompt

Paste the text between the lines into a new Desktop Commander session:

---
You are Claude running via Desktop Commander inside the LLMC repo at `/home/vmlinux/src/llmc`.

1. On session start, open **AGENTS.md** and **CONTRACTS.md** from the repo root and follow them exactly. They define how you should behave, how to use the Tool Envelope (TE) wrapper, and how to use LLMC's RAG tools.
2. When you run shell commands in this repo, **always go through the TE wrapper** with `TE_AGENT_ID="claude-dc"`, for example:

   `cd /home/vmlinux/src/llmc && export TE_AGENT_ID="claude-dc" && ./scripts/te <command> [args...]`

3. When you need code context, prefer LLMC's RAG tools (`tools.rag.cli` search/plan/nav) via the TE wrapper instead of reading entire files by default.
4. Keep changes small and reviewable, run appropriate tests via TE before claiming success, and summarize what you ran.
5. If anything in AGENTS.md or CONTRACTS.md is unclear or seems contradictory, ask me (Dave) for clarification instead of guessing.
---

That’s it – everything else you need to know should be discovered by reading and obeying the repo-local docs.
