# How to Benchmark RLM

You have **two sandbox-safe API keys** in `.env`:
- **DeepSeek** (`DEEPSEEK_API_KEY`) - Fast, cheap reasoning model (~$0.001/query)
- **MiniMax** (`MINIMAX_API_KEY`) - Alternative Chinese model

**Safety note**: Both keys have limited funds loaded (~few dollars), so safe to expose in benchmarks.

## Quick Start (30 seconds)

```bash
cd /home/vmlinux/src/llmc

# Run with DeepSeek (recommended)
python scripts/benchmark_rlm_quick.py --model deepseek

# Run with MiniMax
python scripts/benchmark_rlm_quick.py --model minimax

# Show full answers
python scripts/benchmark_rlm_quick.py --model deepseek --verbose
```

## What You'll See

The benchmark runs 4 tests and shows:
- ✅ Success rate and correctness
- 📊 Token usage (proves lazy loading works)
- 💰 Cost per query (should be <$0.01 each)
- 🔄 Subcall count (proves recursive reasoning)
- ⏱️ Latency

**Key validation**: If RLM is working correctly, you'll see **70-95% token reduction** vs traditional RAG.

## The Tests

1. **Simple lookup** - Find a config value (tests basic navigation)
2. **Code understanding** - Explain a method (tests tool usage)
3. **Multi-hop trace** - Follow data flow (tests recursion)
4. **Security check** - Find blocked builtins (tests pattern matching)

## Expected Results (Good Run)

```
Success rate: 4/4 (100%)
Avg correctness: 80-100%
Total tokens: 8,000-12,000 (vs 60,000 for traditional RAG)
Total cost: $0.01-0.02
Context reduction: 80-95%
```

## Troubleshooting

### Quick fixes:
```bash
# Make sure you're in repo root
cd /home/vmlinux/src/llmc

# Check API keys loaded
grep DEEPSEEK .env

# Test DeepSeek is working
python -c "import os; print('Key loaded' if os.getenv('DEEPSEEK_API_KEY') else 'Missing')"
```

### If tests fail:
1. Check `llmc.toml` has `[mcp.rlm] enabled = true`
2. Rebuild index: `llmc-cli repo index .`
3. Verify model: Try `litellm --test` if needed

## Save the Results

Results auto-save to `/tmp/rlm_benchmark_results.json`

You can compare multiple runs:
```bash
# Run both models
python scripts/benchmark_rlm_quick.py --model deepseek > /tmp/deepseek_results.txt
python scripts/benchmark_rlm_quick.py --model minimax > /tmp/minimax_results.txt

# Compare
diff /tmp/deepseek_results.txt /tmp/minimax_results.txt
```

---

**Cost**: ~$0.01-0.02 per full run (4 tests)
**Time**: ~15-30 seconds
**Safety**: Keys have limited funds, safe to expose
