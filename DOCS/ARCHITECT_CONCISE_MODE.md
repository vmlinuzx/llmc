# System Architect Concise Mode

**Machine-parseable technical specifications for coding agents**

## Overview

The System Architect (Concise Mode) produces structured, bullet-only specifications that coding agents can parse and execute efficiently. This format eliminates verbose prose while maintaining precision and completeness.

## Key Benefits

- **Token Efficient**: Target ≤900 tokens (vs typical 2000+ for prose specs)
- **Machine Parseable**: Strict schema enables automated validation and parsing
- **Action Oriented**: Clear file operations, function signatures, test cases
- **Cost Effective**: Smaller specs = lower LLM costs across the pipeline

## Files

```
prompts/
└── system_architect_concise.md     # Full prompt for LLMs

scripts/
└── validate_architect_spec.py      # Schema validator CLI

examples/specs/
└── auth_feature_example.md         # Reference implementation
```

## Schema Structure

Every spec MUST contain these 7 sections in order:

1. **GOAL** - Single-line objective (≤80 chars)
2. **FILES** - File operations with actions
3. **FUNCS** - Function signatures with types
4. **POLICY** - Rules, constraints, invariants
5. **TESTS** - Test scenarios and edge cases
6. **RUNBOOK** - Numbered deployment steps
7. **RULES** - Meta-constraints (NO prose, ≤900 tokens, etc.)

## Usage

### For LLMs (Architect Agents)

Add this prompt to your system context:

```bash
cat prompts/system_architect_concise.md
```

Or reference it in your orchestration:

```python
architect_prompt = Path("prompts/system_architect_concise.md").read_text()
response = llm.complete(architect_prompt + user_request)
```

### For Humans (Spec Writers)

Use the example as a template:

```bash
cp examples/specs/auth_feature_example.md specs/my_feature.md
# Edit your spec
```

Validate before committing:

```bash
python3 scripts/validate_architect_spec.py specs/my_feature.md
```

### For Agents (Spec Consumers)

Parse the spec programmatically:

```python
from pathlib import Path
import re

spec_content = Path("specs/my_feature.md").read_text()

# Extract sections
sections = {}
current_section = None
for line in spec_content.split('\n'):
    if line.startswith("### "):
        current_section = line[4:].strip()
        sections[current_section] = []
    elif current_section:
        sections[current_section].append(line)

# Now work with structured data
files_to_create = [
    line for line in sections["FILES"] 
    if "[CREATE]" in line
]
```

## Validation

The validator checks:

- ✅ All required sections present
- ✅ Sections in correct order
- ✅ File actions use valid verbs (CREATE/MODIFY/DELETE/RENAME)
- ✅ Function signatures include types
- ✅ Line lengths within limits (≤80 chars for most)
- ✅ Token count under budget (≤1000 hard limit)

Run validation:

```bash
# Validate single spec
python3 scripts/validate_architect_spec.py specs/my_feature.md

# Validate all specs
find specs/ -name "*.md" -exec python3 scripts/validate_architect_spec.py {} \;
```

## Style Guide

### DO ✅

- Use bullet points exclusively
- Keep lines short (≤80 chars)
- Use code symbols: `function()`, `/path/to/file`, `CONSTANT`
- Be specific with types and paths
- Use `→` for return types
- Use `TBD` for unknowns

### DON'T ❌

- Write paragraphs or prose
- Repeat information across sections
- Use vague descriptions
- Exceed token budget (≤900 tokens)
- Include implementation details (save for code)

## Examples

### Good Spec Entry

```markdown
### FUNCS
- auth.verify_token(token: str) → User | None - validate JWT
- auth.create_token(user: User) → str - generate signed token
```

### Bad Spec Entry

```markdown
### FUNCS
The verify_token function takes a token string as input and returns 
either a User object if the token is valid or None if it's invalid. 
This function should...
```

## Integration with LLMC

### Router Integration

Architect specs can include routing hints:

```markdown
### POLICY
- Complex query → route to PREMIUM tier
- Schema extraction → use local Qwen 14B
- Simple CRUD → LOCAL tier sufficient
```

### RAG Enhancement

Specs become retrievable context:

```bash
# Index specs for RAG
rag index specs/
rag embed --execute

# Query during orchestration
rag search "authentication implementation" --json
```

### Compressor Pipeline

Architect output can feed into the spec compressor:

```
User Request → Architect (verbose) → Compressor → Beatrice (compressed spec)
```

## Token Economics

### Baseline (Prose Spec)
- Average: 2000-3000 tokens
- Cost @ $0.015/1K: $0.03-$0.045 per spec

### Concise Mode
- Average: 600-900 tokens
- Cost @ $0.015/1K: $0.009-$0.0135 per spec
- **Savings: 70% reduction**

At 100 specs/week:
- Prose cost: $150-180/month
- Concise cost: $36-54/month
- **Savings: $100-130/month**

## Roadmap Integration

This implements the roadmap item:

> **Swap in concise architect system prompt enforcing the new spec schema**
> - System: SYSTEM ARCHITECT (CONCISE MODE) with fixed sections (GOAL, FILES, FUNCS, POLICY, TESTS, RUNBOOK, RULES)
> - Enforce bullet-only output, ≤900 tokens, no prose; prefer symbols/paths/constants

Status: ✅ **COMPLETE**

## Next Steps

1. **Integrate with orchestration**: Wire architect prompt into `codex_wrap.sh` pipeline
2. **Build compressor**: Create `scripts/spec_compress.sh` for post-processing
3. **Test with real tasks**: Run 10+ real features through the pipeline
4. **Measure savings**: Track token reduction vs prose baseline
5. **Iterate**: Refine schema based on agent feedback

## Contributing

When improving the schema:

1. Update prompt: `prompts/system_architect_concise.md`
2. Update validator: `scripts/validate_architect_spec.py`
3. Add test case: `examples/specs/`
4. Run validation suite: `pytest tests/test_architect_spec.py`
5. Update this README

## FAQ

**Q: Why 900 token limit?**  
A: Balances completeness with cost. Most features fit comfortably; complex ones can be split.

**Q: Can I use prose in certain sections?**  
A: No. Use bullet points everywhere. If you need explanation, add to comments or separate docs.

**Q: What about really complex features?**  
A: Split into multiple specs (auth_spec.md, api_spec.md, db_spec.md) or use hierarchical structure.

**Q: How do I handle uncertainty?**  
A: Use `TBD - requires [detail]` or `See [doc] for details`. Never guess.

**Q: Can agents self-validate?**  
A: Yes! Architect can call validator on its own output before returning to user.

## License

Part of LLMC project. See root LICENSE file.

---

**Built with 🧠 by DC | Powered by LLMC**
