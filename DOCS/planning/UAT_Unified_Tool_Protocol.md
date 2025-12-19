# UAT: Unified Tool Protocol (UTP)

**Version:** 1.0  
**Date:** 2025-12-18  
**HLD Reference:** `HLD_Unified_Tool_Protocol.md`  
**Status:** Draft – Pending Implementation

---

## 1. Overview

This document defines User Acceptance Testing criteria for the Unified Tool Protocol (UTP) implementation. Tests are organized by persona and use case, with explicit pass/fail criteria.

**Primary Test Environment:**
- **Boxxie** (Qwen3-Next-80B-A3B on Strix Halo via Ollama @ athena:11434)
- **LLMC Agent** (`bx` command)
- **Test Repository:** `/home/vmlinux/src/llmc`

---

## 2. Test Personas

| Persona | Description | Primary Tool Format |
|---------|-------------|---------------------|
| **Boxxie User** | Local LLM via Ollama on Strix Halo | OpenAI (native) or XML in content |
| **Claude MCP User** | Claude Desktop with MCP server | Anthropic XML |
| **Gemini User** | Gemini CLI or API | OpenAI-compatible |
| **Developer** | Testing/debugging tool calling | All formats |

---

## 3. Acceptance Criteria

### 3.1 Critical (Must Pass)

| ID | Criteria | Validation Method |
|----|----------|-------------------|
| **UAT-C1** | Boxxie can execute tool calls | `bx` runs search_code and returns results |
| **UAT-C2** | Tool call results are injected into conversation | Model references search results in response |
| **UAT-C3** | Existing MCP tool calling still works | Claude Desktop smoke test |
| **UAT-C4** | Progressive disclosure tier checks enforced | Tier 2 tools blocked when Tier 1 unlocked |
| **UAT-C5** | No security regression | Path traversal still blocked |

### 3.2 Important (Should Pass)

| ID | Criteria | Validation Method |
|----|----------|-------------------|
| **UAT-I1** | XML tool calls parsed correctly | `<tools>` blocks execute |
| **UAT-I2** | Mixed format responses handled | Native + XML in same response |
| **UAT-I3** | Malformed tool calls don't crash | Graceful error message |
| **UAT-I4** | Tool Envelope formatting preserved | TE headers in tool output |
| **UAT-I5** | Configuration respected | `call_parser` setting honored |

### 3.3 Nice to Have (May Pass)

| ID | Criteria | Validation Method |
|----|----------|-------------------|
| **UAT-N1** | Telemetry logs format detection | Check telemetry output |
| **UAT-N2** | Performance acceptable | <100ms parsing overhead |
| **UAT-N3** | Anthropic format works | Direct Anthropic API test |

---

## 4. Test Scenarios

### 4.1 Scenario: Boxxie Basic Tool Call

**Persona:** Boxxie User  
**Covers:** UAT-C1, UAT-C2

**Preconditions:**
- Ollama running on athena with `qwen3-next-80b-tools` model
- LLMC indexed for `/home/vmlinux/src/llmc`
- `boxxie-tools` profile configured in `llmc.toml`

**Test Steps:**

```bash
# Step 1: Invoke bx with a question that requires code search
bx "What functions handle tool parsing in the codebase?"
```

**Expected Result:**
1. Model outputs a tool call (either native `tool_calls` or XML in content)
2. Tool call is parsed and `search_code` is executed
3. RAG results are returned to model
4. Model responds with information synthesized from search results
5. Response mentions specific files/functions found

**Pass Criteria:**
- [ ] Tool call detected (visible in debug output or logs)
- [ ] Search results returned (file paths mentioned)
- [ ] Final response is coherent and references code

**Actual Result:** _[To be filled during testing]_

---

### 4.2 Scenario: XML Tool Call Parsing

**Persona:** Boxxie User  
**Covers:** UAT-I1

**Preconditions:**
- Same as 4.1
- Model configured to output XML format (via modelfile TEMPLATE)

**Test Steps:**

```bash
# Step 1: Send question that triggers tool use
bx "Search for authentication code"
```

**Expected Model Output (simulated):**
```
I'll search for authentication-related code.

<tools>
{"name": "search_code", "arguments": {"query": "authentication"}}
</tools>
```

**Expected Behavior:**
1. XML block is detected in content
2. JSON inside XML is parsed
3. `search_code` tool is executed
4. Results fed back to model

**Pass Criteria:**
- [ ] XML block parsed without error
- [ ] Tool executed correctly
- [ ] Model continues after receiving results

**Actual Result:** _[To be filled during testing]_

---

### 4.3 Scenario: Native Tool Call (OpenAI Format)

**Persona:** Boxxie User / Gemini User  
**Covers:** UAT-C1

**Preconditions:**
- Model configured for native tool calling
- Tools passed in `tools` parameter to API

**Test Steps:**

```bash
# Step 1: API call with tools parameter
curl -s http://athena:11434/api/chat -d '{
  "model": "qwen3-next-80b-tools",
  "messages": [{"role": "user", "content": "Search for MCP code"}],
  "tools": [{"type": "function", "function": {"name": "search_code", "description": "Search code", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}}}],
  "stream": false
}' | jq '.message.tool_calls'
```

**Expected Result:**
```json
[
  {
    "function": {
      "name": "search_code",
      "arguments": "{\"query\": \"MCP\"}"
    }
  }
]
```

**Pass Criteria:**
- [ ] `tool_calls` field is populated
- [ ] Function name matches expected
- [ ] Arguments are valid JSON

**Actual Result:** _[To be filled during testing]_

---

### 4.4 Scenario: Progressive Disclosure - Tier Enforcement

**Persona:** Developer  
**Covers:** UAT-C4

**Preconditions:**
- Agent started with `default_tier = WALK`
- User intent detected as WALK (read operation)

**Test Steps:**

```bash
# Step 1: Ask a question that triggers WALK tier
bx "Show me the contents of llmc.toml"

# Step 2: Model attempts to call write_file (Tier RUN)
# (Simulated by injecting a tool call manually in test)
```

**Expected Behavior:**
1. If model requests `write_file`, it should be blocked
2. Error message returned to model: "Tool 'write_file' not available at current tier (WALK)"
3. Model continues without executing write

**Pass Criteria:**
- [ ] Tier check prevents RUN tools at WALK tier
- [ ] Informative error returned (not crash)
- [ ] Model can still use WALK/CRAWL tools

**Actual Result:** _[To be filled during testing]_

---

### 4.5 Scenario: Malformed Tool Call Handling

**Persona:** Developer  
**Covers:** UAT-I3

**Preconditions:**
- Parser configured with CompositeParser

**Test Input (simulated malformed response):**
```python
response = {
    "message": {
        "content": """
I'll search for that.

<tools>
{"name": "search_code", "arguments": {broken json here
</tools>

Also trying:
<tool_call>not even close to valid</tool_call>
"""
    }
}
```

**Expected Behavior:**
1. Parser attempts to extract tool calls
2. Malformed JSON/XML is caught
3. No crash occurs
4. ParsedResponse returned with `tool_calls=[]` or partial results
5. Warning logged

**Pass Criteria:**
- [ ] No exception raised
- [ ] ParsedResponse returned
- [ ] Logging indicates parsing issue

**Actual Result:** _[To be filled during testing]_

---

### 4.6 Scenario: Security - Path Traversal Still Blocked

**Persona:** Developer (Security)  
**Covers:** UAT-C5

**Preconditions:**
- Agent with tools enabled
- `allowed_roots` set to repo directory

**Test Steps:**

```bash
# Step 1: Simulate tool call with path traversal
# (Inject directly or prompt model to try)
```

**Simulated Tool Call:**
```python
ToolCall(
    name="read_file",
    arguments={"path": "../../../etc/passwd"}
)
```

**Expected Behavior:**
1. Tool call is parsed successfully (format layer doesn't block)
2. Execution layer validates path
3. `PathSecurityError` raised
4. Error returned to model: "Path escapes repository boundary"

**Pass Criteria:**
- [ ] Path traversal blocked at execution, not parsing
- [ ] Clear error message
- [ ] No file content leaked

**Actual Result:** _[To be filled during testing]_

---

### 4.7 Scenario: Mixed Format Response

**Persona:** Developer  
**Covers:** UAT-I2

**Preconditions:**
- CompositeParser enabled

**Test Input (simulated mixed response):**
```python
response = {
    "message": {
        "tool_calls": [
            {"function": {"name": "search_code", "arguments": "{\"query\": \"native\"}"}}
        ],
        "content": """
I found some results via native calling. Let me also check with XML:

<tools>
{"name": "list_dir", "arguments": {"path": "."}}
</tools>
"""
    }
}
```

**Expected Behavior:**
1. Native `tool_calls` parsed (Priority 1)
2. XML in content also parsed (Priority 2)
3. Both tool calls returned (deduplicated if identical)
4. `tool_calls = [search_code, list_dir]`

**Pass Criteria:**
- [ ] Both formats parsed
- [ ] No duplicates
- [ ] Both tools executed

**Actual Result:** _[To be filled during testing]_

---

### 4.8 Scenario: Tool Envelope Output Integration

**Persona:** Boxxie User  
**Covers:** UAT-I4

**Preconditions:**
- TE enabled for search results
- Tool call executed successfully

**Test Steps:**

```bash
bx "Search for database connection code"
```

**Expected Tool Result Format:**
```
# TE_BEGIN_META
{"v":1,"cmd":"search","matches":15,"truncated":false}
# TE_END_META

tools/rag/database.py:42: def database_connection():
tools/rag/database.py:89: database_connection.execute(

# TE: 10 more in tools/rag/
```

**Pass Criteria:**
- [ ] TE meta headers present in tool result
- [ ] Breadcrumbs included if truncated
- [ ] Model can interpret TE-formatted output

**Actual Result:** _[To be filled during testing]_

---

### 4.9 Scenario: Configuration Override

**Persona:** Developer  
**Covers:** UAT-I5

**Preconditions:**
- Profile with explicit format config:
```toml
[profiles.test-xml]
provider = "ollama"
model = "qwen3-next-80b-tools"
[profiles.test-xml.tools]
call_parser = "qwen_xml"
```

**Test Steps:**

```bash
# Use profile with explicit XML parser
bx --profile test-xml "Search for something"
```

**Expected Behavior:**
1. FormatNegotiator uses configured parser
2. Only XML parsing attempted (not native first)
3. Tool call parsed if model outputs XML

**Pass Criteria:**
- [ ] Config read correctly
- [ ] Parser selection matches config
- [ ] Tool call parsed appropriately

**Actual Result:** _[To be filled during testing]_

---

### 4.10 Scenario: Claude MCP Compatibility (Regression)

**Persona:** Claude MCP User  
**Covers:** UAT-C3

**Preconditions:**
- Claude Desktop running
- LLMC MCP server configured
- Existing MCP tool calling working

**Test Steps:**

1. Open Claude Desktop
2. Ask: "Using MCP, search the LLMC codebase for tool parsing"
3. Observe tool execution

**Expected Behavior:**
1. Claude uses MCP tools (existing path)
2. Tool results returned
3. No change from pre-UTP behavior

**Pass Criteria:**
- [ ] MCP tools still work
- [ ] No errors in MCP server logs
- [ ] Response quality unchanged

**Actual Result:** _[To be filled during testing]_

---

## 5. Test Data

### 5.1 Known-Good Tool Calls

```python
# Native format (OpenAI/Ollama)
NATIVE_TOOL_CALL = {
    "function": {
        "name": "search_code",
        "arguments": "{\"query\": \"authentication\", \"limit\": 5}"
    },
    "id": "call_123"
}

# Anthropic XML format
ANTHROPIC_XML = """
<tool_use>
<name>search_code</name>
<arguments>{"query": "authentication", "limit": 5}</arguments>
</tool_use>
"""

# Qwen/Generic XML format
QWEN_XML = """
<tools>
{"name": "search_code", "arguments": {"query": "authentication"}}
</tools>
"""

# JSON in XML (common pattern)
JSON_IN_XML = """
<function_call>
{"name": "search_code", "arguments": {"query": "authentication"}}
</function_call>
"""
```

### 5.2 Known-Bad Tool Calls (For Error Handling)

```python
# Malformed JSON
MALFORMED_JSON = '<tools>{"name": "search" broken</tools>'

# Missing required field
MISSING_NAME = '<tools>{"arguments": {}}</tools>'

# Hallucinated tool
HALLUCINATED = '<tools>{"name": "magic_wand", "arguments": {}}</tools>'

# Empty block
EMPTY_BLOCK = '<tools></tools>'

# Nested incorrectly
NESTED_WRONG = '<tools><tools>{"name": "search"}</tools></tools>'
```

---

## 6. Environment Setup

### 6.1 Boxxie Test Environment

```bash
# Ensure Ollama is running on athena
ssh athena "systemctl status ollama"

# Verify model is loaded
ssh athena "ollama ps"

# Expected: qwen3-next-80b-tools or qwen3-next-80b-nothink

# Verify LLMC profile
grep -A5 '\[profiles.boxxie\]' llmc.toml
```

### 6.2 Test Commands

```bash
# Run bx with debug output
DEBUG=1 bx "test question"

# Check parsed tool calls
bx --dry-run "search for auth code"

# Run unit tests
pytest tests/agent/format/ -v

# Run integration tests
pytest tests/agent/test_tool_calling_integration.py -v
```

---

## 7. Sign-Off

### 7.1 Test Execution Summary

| Scenario | Status | Tester | Date |
|----------|--------|--------|------|
| 4.1 Boxxie Basic | ⬜ | | |
| 4.2 XML Parsing | ⬜ | | |
| 4.3 Native Format | ⬜ | | |
| 4.4 Tier Enforcement | ⬜ | | |
| 4.5 Malformed Handling | ⬜ | | |
| 4.6 Path Traversal | ⬜ | | |
| 4.7 Mixed Format | ⬜ | | |
| 4.8 Tool Envelope | ⬜ | | |
| 4.9 Config Override | ⬜ | | |
| 4.10 Claude MCP | ⬜ | | |

**Legend:** ⬜ Not Run | ✅ Pass | ❌ Fail | ⏳ Blocked

### 7.2 Acceptance Decision

| Criteria Category | Pass Count | Total | Status |
|-------------------|------------|-------|--------|
| Critical (C1-C5) | /5 | 5 | |
| Important (I1-I5) | /5 | 5 | |
| Nice to Have (N1-N3) | /3 | 3 | |

**Acceptance Threshold:**
- ✅ ALL Critical must pass
- ✅ 4/5 Important must pass
- ⬜ Nice to Have are bonus

**Final Decision:** ⬜ Pending Testing

---

## 8. Appendix

### 8.1 Related Documents

- `HLD_Unified_Tool_Protocol.md` - Architecture design
- `SDD_Tool_Envelope_v1.2.md` - Tool Envelope specification
- `llmc_agent/tools.py` - Progressive disclosure implementation
- `TURNOVER_Boxxie_StrixHalo_Vulkan_Setup.md` - Boxxie context

### 8.2 Test Automation

Future: These scenarios should be automated as pytest fixtures:

```python
# tests/agent/format/test_uat_scenarios.py

@pytest.mark.uat
class TestUATScenarios:
    @pytest.mark.critical
    def test_boxxie_basic_tool_call(self, boxxie_agent):
        """UAT-C1, UAT-C2: Boxxie can execute and use tool results."""
        ...
    
    @pytest.mark.critical
    def test_tier_enforcement(self, agent_walk_tier):
        """UAT-C4: Progressive disclosure enforced."""
        ...
```

---

*This UAT document will be updated with actual results during implementation testing.*
