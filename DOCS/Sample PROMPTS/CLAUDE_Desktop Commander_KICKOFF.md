# Claude Desktop Commander - LLMC Session Kickoff

Paste this into new Claude Desktop Commander sessions when working on LLMC.

---

## Session Kickoff Prompt

```
I'm working in the LLMC repo at /home/vmlinux/src/llmc.

CRITICAL: When running shell commands in this repo, use the Tool Envelope (TE) wrapper for telemetry collection:

Pattern:
cd /home/vmlinux/src/llmc && export TE_AGENT_ID="claude-dc" && ./scripts/te <command> [args...]

Examples:
- ./scripts/te ls -la
- ./scripts/te grep "pattern" file.py  
- ./scripts/te git status
- ./scripts/te pwd

Why: TE logs all command usage to help identify what commands need enrichment and optimization. This is dogfooding to improve the tool.

Exceptions (run without te):
- Multi-command pipes: ls | grep | wc
- Interactive sessions: python3 -i, bash, tmux
- Shell state commands: cd, export, source (when used alone)

After working, check telemetry with:
./scripts/te-analyze summary
./scripts/te-analyze candidates

Please confirm you understand the TE usage requirement.
```

---

## Why This Matters

TE (Tool Envelope) is a transparent shell wrapper that:
- Logs every command to `.llmc/te_telemetry.db`
- Enables pass-through for unknown commands
- Will eventually enrich common commands (ls, grep, git, etc.)

By using `te` consistently, we collect real usage data to:
1. Identify which commands LLMs use most
2. See what produces the most output (token cost)
3. Measure what's slow
4. Prioritize enrichment handler development

The data goes into the TUI analytics dashboard and `te-analyze` reports.

---

## Quick Reference Card

**Always use:**
```bash
cd /home/vmlinux/src/llmc && export TE_AGENT_ID="claude-dc" && ./scripts/te <cmd>
```

**Check telemetry:**
```bash
./scripts/te-analyze summary        # Overall stats
./scripts/te-analyze by-command     # Usage breakdown  
./scripts/te-analyze candidates     # What needs enrichment
./scripts/te-analyze slow          # Performance issues
```

**View in TUI:**
The analytics TUI (if running) shows real-time dashboards.

---

## Notes

- TE adds ~1-2ms overhead per command (negligible)
- All telemetry is local (stored in `.llmc/te_telemetry.db`)
- TE_AGENT_ID="claude-dc" tracks that Desktop Commander ran the command
- Pass-through mode means unknown commands work normally
- This is temporary for dogfooding - not a permanent workflow change
