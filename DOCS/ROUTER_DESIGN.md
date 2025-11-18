# RAG-Powered Router -ALPHA BUGGY SUCKS- Engineering Design

## The Problem

You have three LLM tiers with different cost/capability profiles:
- **Local (Qwen)**: Free, fast, but limited
- **Mid (MiniMax)**: $1-2/M tokens, great for volume/testing
- **Premium (Claude)**: $3-15/M tokens, best reasoning

**Manual routing sucks.** You end up either:
- Over-routing to premium → wasting money
- Under-routing to cheap models → wasting time on retries

## The Solution

**Use RAG to make smart routing decisions.**

Your RAG system already knows:
1. What code exists (schema-enriched index)
2. Query intent (planner with confidence)
3. Required context (span retrieval)
4. Task complexity (symbol matching scores)

Use this to **automatically select the cheapest model that can do the job.**

## Architecture

```
User Query
    ↓
RAG Analysis (planner + search)
    ↓
Routing Decision (rag_router.py)
    ↓
LLM Execution (local/mid/premium)
    ↓
Result
```

### RAG Analysis Phase

The router calls your RAG planner to get:

```python
plan = generate_plan("Write tests for JWT validation", limit=5)
# Returns:
{
  "intent": "write-tests-jwt",
  "confidence": 0.85,
  "spans": [
    {"path": "auth.py", "symbol": "validate_jwt", "score": 0.92},
    {"path": "test_auth.py", "symbol": "test_jwt", "score": 0.87}
  ],
  "symbols": [...],
  "fallback_recommended": false
}
```

From this, the router extracts:
- **Complexity**: High confidence + few spans = simple
- **Context needed**: Number of spans * estimated tokens
- **Reasoning required**: Keywords like "why", "how", "design"
- **Validation needed**: Keywords like "review", "validate"

### Routing Decision Logic

```python
def decide_tier(analysis):
    # Force premium for validation/architecture
    if analysis.requires_validation:
        return "premium"
    
    # Force premium for complex reasoning
    if analysis.complexity == "complex" and analysis.requires_reasoning:
        return "premium"
    
    # Use local for simple + high confidence
    if analysis.complexity == "simple" and analysis.confidence > 0.8:
        return "local"
    
    # MiniMax's sweet spot: testing and bug hunting
    if "test" in query or "bug" in query:
        return "mid"  # MiniMax pathology = perfect for this
    
    # Default: mid tier (cost-effective)
    return "mid"
```

## Routing Tiers Explained

### Local Tier (Qwen 7B)
**Cost**: Free  
**Best for**:
- Simple refactors
- Code formatting
- Renaming variables
- Adding comments
- Known patterns

**Triggers**:
- High confidence (>0.8)
- Simple complexity
- No reasoning required
- Small context (<8K tokens)

**Example**:
```bash
llmc-route "Format this Python file"
→ local (qwen-2.5-coder-7b)
→ Confidence: 95%
→ Cost: $0.0000
```

### Mid Tier (MiniMax)
**Cost**: $1-2/M tokens  
**Best for**:
- **Testing** (MiniMax's pathology = perfect)
- **Bug hunting** (dies trying to find failures)
- Volume work
- Standard tasks
- Medium complexity

**Triggers**:
- Testing keywords ("write tests", "find bugs")
- Medium complexity
- Standard context (8K-32K tokens)
- Cost-effective default

**Example**:
```bash
llmc-route "Write comprehensive tests for authentication"
→ mid (minimax-m2)
→ Confidence: 87%
→ Cost: $0.0123
→ Rationale: Testing - MiniMax excels here
```

### Premium Tier (Claude)
**Cost**: $3-15/M tokens  
**Best for**:
- Architecture design
- Security validation
- Complex reasoning
- Senior engineer review
- Large context (>32K tokens)

**Triggers**:
- Validation keywords ("review", "validate", "check")
- Reasoning keywords ("why", "how", "design", "tradeoff")
- Complex tasks with low confidence
- Large context requirements

**Example**:
```bash
llmc-route "Design a caching architecture with Redis"
→ premium (claude-sonnet-4.5)
→ Confidence: 92%
→ Cost: $0.0842
→ Rationale: Complex reasoning required
```

## Key Features

### 1. Forced Routing Patterns

Some queries bypass RAG analysis:

```python
forced_routing = {
    "local": ["format code", "add comments", "rename variable"],
    "mid": ["write tests", "find bugs", "stress test"],
    "premium": ["design architecture", "review security"]
}
```

### 2. MiniMax Pathology Utilization

The router **explicitly routes testing to MiniMax**:

```python
if "test" in query or "bug" in query:
    return "mid"  # MiniMax's pathological success-seeking
                  # makes it perfect for finding failures
```

This is based on your empirical finding:
- MiniMax wrote 11K lines of tests
- Found 15 real bugs (83% precision)
- Success case = failure case → perfect alignment

### 3. Cost Estimation

Router estimates cost before execution:

```python
estimated_input = context_tokens + query_tokens
estimated_output = 2000  # Conservative
cost = (input/1M * input_cost) + (output/1M * output_cost)
```

**Example costs**:
- Local: $0.0000 (always free)
- Mid: $0.0050 - $0.0200 (typical task)
- Premium: $0.0300 - $0.1500 (complex task)

### 4. Context-Aware Routing

Router uses RAG to determine context needs:

```python
# Small context → local possible
if estimated_tokens < 8000 and simple:
    return "local"

# Medium context → mid tier
if estimated_tokens < 32000:
    return "mid"

# Large context → premium (bigger window)
if estimated_tokens > 32000:
    return "premium"
```

## Usage

### CLI

```bash
# Basic routing
llmc-route "Write tests for JWT"

# With verbose output
llmc-route "Design auth architecture" --verbose

# Override repo
llmc-route "Find bugs" --repo /path/to/repo
```

### Programmatic

```python
from tools.rag_router import route_query
from pathlib import Path

decision = route_query("Write tests for JWT validation")

print(f"Route to: {decision.tier}")
print(f"Model: {decision.model}")
print(f"Confidence: {decision.confidence:.2%}")
print(f"Cost: ${decision.cost_estimate:.4f}")

for reason in decision.rationale:
    print(f"  - {reason}")

# Use RAG context if provided
if decision.rag_results:
    spans = decision.rag_results.get("spans", [])
    for span in spans:
        print(f"Context: {span['path']}:{span['lines']}")
```

### Integration with Actual LLM Calls

```python
decision = route_query(user_query)

if decision.tier == "local":
    response = qwen_api.complete(user_query, context=decision.rag_results)
elif decision.tier == "mid":
    response = minimax_api.complete(user_query, context=decision.rag_results)
else:  # premium
    response = claude_api.complete(user_query, context=decision.rag_results)

# Log routing decision
log_routing(
    query=user_query,
    tier=decision.tier,
    cost=decision.cost_estimate,
    actual_cost=response.usage.total_cost
)
```

## Empirical Validation

Your test suite already proves the value:

**MiniMax for Testing**:
- 11,126 lines generated
- 15 real bugs found
- 3 false positives (17% FP rate = acceptable)
- Cost: ~$20-30 vs $250+ with Claude
- **90% cost savings**

**Routing Decision**:
```
Query: "Write comprehensive tests"
→ RAG detects: testing intent
→ Router selects: mid tier (MiniMax)
→ Rationale: "MiniMax pathology perfect for finding failures"
→ Result: 100% test pass rate, 15 bugs found
```

## Configuration

Router config lives in code but can be overridden:

```python
router = RAGRouter(repo_root, config={
    "models": {
        "local": {
            "name": "qwen-2.5-coder-7b",
            "input_cost": 0.0,
            "output_cost": 0.0,
        },
        "mid": {
            "name": "minimax-m2",
            "input_cost": 0.50,
            "output_cost": 1.50,
        },
        "premium": {
            "name": "claude-sonnet-4.5",
            "input_cost": 3.00,
            "output_cost": 15.00,
        }
    },
    "thresholds": {
        "simple_task_confidence": 0.8,
        "context_token_limit_local": 8000,
        "context_token_limit_mid": 32000,
    }
})
```

## Next Steps

### Immediate:
1. Test the router with real queries
2. Tune confidence thresholds
3. Add more forced routing patterns
4. Log routing decisions for analysis

### Short-term:
1. Integrate with actual LLM APIs
2. Add retry logic with tier promotion
3. Track actual vs estimated costs
4. Build routing analytics dashboard

### Long-term:
1. Learn from routing decisions (ML?)
2. Add user feedback loop
3. Per-user routing preferences
4. Multi-model parallel execution with voting

## Why This Works

**Traditional approach**:
- Dev manually picks model
- Over-routes → wastes money
- Under-routes → wastes time on retries

**RAG-powered approach**:
- RAG analyzes query automatically
- Routes to cheapest capable model
- Provides context if needed
- Estimates cost upfront

**Result**:
- 90% cost savings (proven in your tests)
- Better model utilization
- Faster iteration (right model first time)
- Empirical proof from 11K lines of tests

## The Bottom Line

You built a RAG system to save tokens.  
Now use it to **save money** by routing intelligently.

Your RAG already knows:
- What code exists
- What queries need
- How complex tasks are

Use that knowledge to **automatically route to the right tier**.

**Status**: Router built, ready to wire up to actual LLM execution.
