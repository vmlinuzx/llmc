# Integration Guide: Architect Concise Mode

## Quick Start

### 1. Using in Claude/Codex Wrappers

Add the architect prompt to your orchestration:

```bash
# In codex_wrap.sh or claude_wrap.sh
ARCHITECT_PROMPT=$(cat prompts/system_architect_concise.md)

# Combine with user request
FULL_PROMPT="${ARCHITECT_PROMPT}

---

USER REQUEST:
${USER_REQUEST}"

# Send to LLM
# ... your existing LLM call
```

### 2. Validate Output

After architect generates spec:

```bash
# Save architect output to file
echo "$ARCHITECT_OUTPUT" > /tmp/spec.md

# Validate
python3 scripts/validate_architect_spec.py /tmp/spec.md
VALIDATION_EXIT=$?

if [ $VALIDATION_EXIT -eq 0 ]; then
    echo "✅ Spec validated"
    # Continue pipeline
else
    echo "❌ Spec invalid, regenerating..."
    # Retry logic
fi
```

### 3. Parse and Execute

Extract structured data from spec:

```python
# Example parser
import re
from pathlib import Path

def parse_architect_spec(spec_path: Path) -> dict:
    """Parse architect spec into structured data."""
    content = spec_path.read_text()
    sections = {}
    current_section = None
    
    for line in content.split('\n'):
        if line.startswith("### "):
            current_section = line[4:].strip()
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(line.strip())
    
    # Extract file operations
    files_to_create = []
    files_to_modify = []
    for line in sections.get("FILES", []):
        if "[CREATE]" in line:
            # Extract path: "- path/to/file [CREATE] - desc"
            match = re.match(r'^-\s+(\S+)\s+\[CREATE\]', line)
            if match:
                files_to_create.append(match.group(1))
        elif "[MODIFY]" in line:
            match = re.match(r'^-\s+(\S+)\s+\[MODIFY\]', line)
            if match:
                files_to_modify.append(match.group(1))
    
    # Extract functions to implement
    functions = []
    for line in sections.get("FUNCS", []):
        if line.startswith("- "):
            # Parse: "- module.func(args) → type - desc"
            match = re.match(r'^-\s+([\w\.]+)\(([^\)]*)\)\s+→\s+([\w\|\s]+)\s+-\s+(.+)$', line)
            if match:
                functions.append({
                    "name": match.group(1),
                    "args": match.group(2),
                    "return_type": match.group(3).strip(),
                    "description": match.group(4)
                })
    
    return {
        "goal": sections.get("GOAL", [""])[0],
        "files_to_create": files_to_create,
        "files_to_modify": files_to_modify,
        "functions": functions,
        "sections": sections
    }

# Usage
spec_data = parse_architect_spec(Path("/tmp/spec.md"))
print(f"Goal: {spec_data['goal']}")
print(f"Files to create: {spec_data['files_to_create']}")
```

## Pipeline Integration

### Option A: Direct Integration

Replace existing architect prompt with concise mode:

```bash
# Before
PROMPT="Design a system for user authentication..."

# After
PROMPT=$(cat prompts/system_architect_concise.md)
PROMPT="${PROMPT}\n\nDesign a system for user authentication..."
```

### Option B: Wrapper Script

Create `scripts/architect_concise.sh`:

```bash
#!/bin/bash
# Wrapper for architect concise mode

USER_REQUEST="$1"
OUTPUT_FILE="${2:--}"  # Default to stdout

PROMPT=$(cat prompts/system_architect_concise.md)
FULL_PROMPT="${PROMPT}

---

USER REQUEST:
${USER_REQUEST}"

# Call LLM (using your existing gateway)
RESPONSE=$(echo "$FULL_PROMPT" | ./scripts/llm_gateway.sh)

# Validate
echo "$RESPONSE" > /tmp/architect_out.md
if python3 scripts/validate_architect_spec.py /tmp/architect_out.md; then
    if [ "$OUTPUT_FILE" = "-" ]; then
        cat /tmp/architect_out.md
    else
        mv /tmp/architect_out.md "$OUTPUT_FILE"
    fi
    exit 0
else
    echo "ERROR: Generated spec failed validation" >&2
    exit 1
fi
```

Usage:

```bash
./scripts/architect_concise.sh "Add user authentication" specs/auth.md
```

### Option C: With Compressor Pipeline

Chain architect → compressor → execution:

```bash
# 1. Generate verbose spec
./scripts/architect_concise.sh "$USER_REQUEST" /tmp/verbose_spec.md

# 2. Compress (if needed)
if [ $(wc -c < /tmp/verbose_spec.md) -gt 3000 ]; then
    ./scripts/spec_compress.sh /tmp/verbose_spec.md /tmp/compressed_spec.md
    SPEC_FILE=/tmp/compressed_spec.md
else
    SPEC_FILE=/tmp/verbose_spec.md
fi

# 3. Send to Beatrice/implementation agent
./scripts/codex_wrap.sh --spec "$SPEC_FILE" --implement
```

## RAG Integration

Index architect specs for retrieval:

```bash
# After generating specs
mkdir -p specs/
mv /tmp/architect_out.md specs/feature_001.md

# Reindex
rag index specs/
rag embed --execute

# Later: retrieve similar specs
rag search "authentication implementation" --json | jq
```

## Quality Gates

Add validation as pre-commit hook:

```bash
# .git/hooks/pre-commit
#!/bin/bash

echo "Validating architect specs..."
find specs/ -name "*.md" | while read spec; do
    if ! python3 scripts/validate_architect_spec.py "$spec"; then
        echo "❌ Invalid spec: $spec"
        exit 1
    fi
done
echo "✅ All specs valid"
```

## Monitoring

Track token savings:

```bash
# Before/after token counts
BEFORE_TOKENS=$(echo "$PROSE_SPEC" | wc -c | awk '{print int($1/4)}')
AFTER_TOKENS=$(echo "$CONCISE_SPEC" | wc -c | awk '{print int($1/4)}')
SAVINGS=$(( (BEFORE_TOKENS - AFTER_TOKENS) * 100 / BEFORE_TOKENS ))

echo "Token savings: ${SAVINGS}%" >> logs/architect_metrics.log
```

## Troubleshooting

### Validation Failures

If validator rejects spec:

1. Check section headers match exactly: `### GOAL` not `## GOAL`
2. Verify file actions use valid verbs: `[CREATE]` not `[create]`
3. Check function signatures have types: `→ User` not `returns User`
4. Verify line lengths under 80 chars (except complex signatures)

### Agent Confusion

If implementation agents don't understand spec:

1. Add more detail to FUNCS (include arg types)
2. Expand POLICY with specific constraints
3. Add concrete examples to RUNBOOK
4. Split complex features into multiple specs

### Token Budget Exceeded

If spec exceeds 900 tokens:

1. Trim redundant bullets
2. Use abbreviations: `cfg` not `configuration`
3. Remove obvious constraints
4. Split into separate specs
5. Use references: `See auth_spec.md` instead of repeating

## Examples

### Minimal Spec (Simple CRUD)

```markdown
### GOAL
Add REST endpoints for todo item management

### FILES
- api/todos.py [CREATE] - CRUD handlers
- tests/test_todos.py [CREATE] - endpoint tests

### FUNCS
- todos.create(item: TodoItem) → TodoItem - POST /todos
- todos.list() → List[TodoItem] - GET /todos
- todos.delete(id: int) → None - DELETE /todos/{id}

### POLICY
- Max 100 items per user
- Soft delete (mark deleted, don't remove)

### TESTS
- Create item → returns 201 with item
- List items → returns array
- Delete item → returns 204

### RUNBOOK
1. Add routes: `app.include_router(todos.router)`
2. Test: `pytest tests/test_todos.py`
3. Deploy: restart API server

### RULES
- NO prose
- ≤900 tokens
```

### Complex Spec (Multi-file Feature)

See `examples/specs/auth_feature_example.md`

## Next Steps

1. **Try it**: Generate 3-5 specs for real features
2. **Measure**: Track token savings vs prose baseline
3. **Iterate**: Adjust schema based on agent feedback
4. **Automate**: Add to CI/CD pipeline
5. **Scale**: Use for all new features

---

**Integration Status:** ✅ Ready  
**Next Action:** Wire into `codex_wrap.sh` pipeline  
**Owner:** DC
