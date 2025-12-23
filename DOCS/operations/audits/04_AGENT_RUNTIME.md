# Audit Charter: Agent Runtime & Protocols

**Target Systems:**
*   `llmc_agent/` (The chat/agent logic)
*   `llmc_mcp/` (The Model Context Protocol server)
*   `llmc/client.py` (The API client wrapper)

**The Objective:**
Agents are expensive. Every token sent to an agent costs money and time. We must optimize the "Protocol Overhead."

**Specific Hunting Grounds:**

1.  **The Context Stuffer:**
    *   `llmc_agent/agent.py`.
    *   Are we sending the entire conversation history for every tool call?
    *   Are we truncating old context intelligently, or just letting it overflow?

2.  **The Tool Definition Bloat:**
    *   `llmc_mcp/server.py`.
    *   Inspect the JSON schema generated for tools.
    *   Are descriptions terse and precise? Or are we sending 500-word essays as "tool documentation"?
    *   Bloated tool schemas confuse models and waste input tokens.

3.  **The Double-JSON-Encode:**
    *   Are we taking a dict, `json.dumps`ing it, passing it to an API that `json.dumps` it again?
    *   This happens often in MCP implementations. Find it. Kill it.

4.  **The "Busy Wait" Loop:**
    *   `llmc_agent/session.py`.
    *   When waiting for a user input or tool result, how does the agent sleep?
    *   Does it poll? Does it block?

**Command for Jules:**
`audit_agent --persona=architect --target=llmc_agent`
