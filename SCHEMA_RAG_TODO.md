# Schema RAG v1 - Remaining Work Checklist

## Week 3: Router Integration (4-6 hours)

### 1. Create Router Enrichment Module
**File:** `router/enrichment_policy.py`

```python
# TODO: Implement routing rules from roadmap
# 
# Rule 1: High-confidence local handling
# IF relation_task AND relation_density > 0.7 AND complexity < 7
# THEN route_to = LOCAL
#
# Rule 2: Medium-confidence API tier  
# IF relation_task AND relation_density > 0.4 AND complexity < 5
# THEN route_to = API
#
# Rule 3: Complex multi-hop escalation
# IF relation_task AND complexity >= 7
# THEN route_to = PREMIUM
#
# Rule 4: Sparse graph fallback
# IF relation_task AND relation_density < 0.3
# THEN route_to = PREMIUM with web_search
#
# Rule 5: Non-relationship queries
# IF NOT relation_task
# THEN use existing baseline routing
```

**Tasks:**
- [ ] Load graph store on router startup
- [ ] Integrate QueryAnalyzer into query processing
- [ ] Implement 5 routing rules
- [ ] Add logging for enrichment features
- [ ] Add metrics: `tier_distribution`, `enrichment_feature_values`

### 2. Integration Points

**Modify existing router:**
- [ ] Import `GraphStore`, `QueryAnalyzer`, `HybridRetriever`
- [ ] Load schema graph from `.rag/entities_relations.json`
- [ ] Call `analyzer.analyze(query)` before tier selection
- [ ] Use `EnrichmentFeatures` in routing decision
- [ ] Log features with each routing decision

### 3. A/B Testing Setup
- [ ] Feature flag: `ENABLE_SCHEMA_RAG` (default: false)
- [ ] Random 50/50 split for testing
- [ ] Metrics: baseline tier vs enriched tier per query
- [ ] Duration: 1 week of testing

**Success Criteria:**
- Router doesn't crash with schema enabled
- Queries with high relation_density → LOCAL tier
- Complex queries → PREMIUM tier  
- Metrics logged correctly

---

## Week 4: Validation + Metrics (6-8 hours)

### 1. Build Relationship Query Benchmark
**File:** `DOCS/RESEARCH/relationship_benchmark.json`

**20 Test Queries:**
```json
[
  {
    "query": "Which functions call getUserData?",
    "expected_entities": ["sym:auth.getUserData"],
    "expected_relations": ["calls"],
    "ground_truth_files": ["auth.py", "api.py"],
    "complexity": "low"
  },
  {
    "query": "Trace database dependencies for order processor",
    "expected_entities": ["sym:orders.process", "db:table.orders"],
    "expected_relations": ["calls", "reads", "writes"],
    "ground_truth_files": ["orders.py", "database.py", "models.py"],
    "complexity": "high"
  },
  // ... 18 more queries
]
```

**Tasks:**
- [ ] Create 20 queries covering:
  - Function calls (5 queries)
  - Data dependencies (5 queries)
  - Inheritance chains (3 queries)
  - Multi-hop traversal (4 queries)
  - Complex scenarios (3 queries)
- [ ] Manually label ground truth for each
- [ ] Include queries of varying complexity (low/medium/high)

### 2. Evaluation Script
**File:** `tools/rag/evaluate_schema_rag.py`

```python
# TODO: Implement evaluation pipeline
#
# For each query:
#   1. Run baseline (vector-only)
#   2. Run enriched (vector + graph)
#   3. Compare results
#
# Metrics to calculate:
#   - Recall@10 (are ground truth files in top 10?)
#   - nDCG@10 (normalized discounted cumulative gain)
#   - Citation accuracy (do LLM answers cite correct files?)
#   - P95 latency (is it under 800ms?)
#   - Tier distribution (LOCAL vs API vs PREMIUM)
```

**Tasks:**
- [ ] Load benchmark queries
- [ ] Run baseline retrieval for each query
- [ ] Run enriched retrieval for each query
- [ ] Calculate Recall@10, nDCG@10
- [ ] Measure latency (p50, p95, p99)
- [ ] Sample 10 queries for citation accuracy check
- [ ] Generate comparison report

### 3. Results Documentation
**File:** `DOCS/RESEARCH/schema_rag_v1_results.md`

**Required Sections:**
- [ ] Executive summary (did we hit targets?)
- [ ] Methodology (how we tested)
- [ ] Quantitative results (tables with metrics)
- [ ] Qualitative examples (3-5 query examples)
- [ ] Failure cases (what didn't work)
- [ ] Recommendations for v2
- [ ] Go/no-go decision

**Target Metrics (from roadmap):**
```
Recall@10:           ≥ 0.85 (baseline: 0.62) → +37%
Citation accuracy:   ≥ 0.90 (baseline: 0.72) → +25%  
Local tier share:    60% (baseline: 45%) → +33%
P95 latency:         ≤ 800ms (baseline: 600ms) → +200ms budget
```

**Go Decision Criteria:**
- ✅ Recall improvement ≥ 20%
- ✅ Citation accuracy ≥ 0.85
- ✅ P95 latency ≤ 1000ms
- ✅ No critical bugs

**No-Go Criteria:**
- ❌ Recall drops below baseline
- ❌ Citation accuracy < 0.70
- ❌ P95 latency > 1500ms
- ❌ Critical bugs in production

### 4. Production Rollout Plan
**File:** `DOCS/ROLLOUT.md`

- [ ] Shadow mode (log only, no routing changes) - 1 week
- [ ] Internal dogfooding - 1 week
- [ ] 10% rollout - 1 week
- [ ] 50% rollout - 1 week  
- [ ] 100% rollout
- [ ] Rollback procedure documented

---

## Optional Enhancements (If Time Permits)

### Graph Visualization Tool
**File:** `tools/rag/visualize_graph.py`

```bash
# Generate call graph visualization
python3 visualize_graph.py sym:auth.login --output graph.svg
```

- [ ] ASCII tree output for terminal
- [ ] DOT format export for Graphviz
- [ ] Interactive HTML viewer

### CLI Debugging Tools
**File:** `tools/rag/debug_cli.py`

```bash
# Inspect entity
llmc-rag inspect sym:auth.login

# Test query analysis
llmc-rag analyze "Which functions call getUserData?"

# Validate graph
llmc-rag validate --check-broken-links
```

### Monitoring Dashboard
**Integration:** Add to existing LLMC dashboard

- [ ] Graph statistics panel (entities, edges, coverage)
- [ ] Enrichment feature distribution charts
- [ ] Tier shift visualization (before/after comparison)
- [ ] Query complexity histogram

---

## Estimated Time Budget

| Task | Hours | Priority |
|------|-------|----------|
| Router integration | 4-6 | HIGH |
| Benchmark creation | 2-3 | HIGH |
| Evaluation script | 3-4 | HIGH |
| Results documentation | 2-3 | HIGH |
| Rollout planning | 1-2 | MEDIUM |
| Optional enhancements | 4-6 | LOW |

**Total:** 12-18 hours (HIGH priority items)  
**With optional:** 16-24 hours

---

## Definition of Done

**v1 is complete when:**
- [x] Schema extraction working (Week 1)
- [x] Graph storage working (Week 2)
- [x] Enrichment integration working (Week 2)
- [x] Tests passing (Week 2)
- [ ] Router integration live (Week 3)
- [ ] A/B test running (Week 3)
- [ ] Benchmark evaluation complete (Week 4)
- [ ] Results documented (Week 4)
- [ ] Go/no-go decision made (Week 4)

**Ship Criteria:**
- Metrics meet targets (Recall, citation, latency)
- No critical bugs in production
- Rollout plan approved
- v2 roadmap updated based on learnings

---

**Current Status:** 50% complete (Weeks 1-2 ✅)  
**Next Milestone:** Router integration (Week 3)  
**Ship Date:** End of Week 4 (Nov 26-30)

---

## Questions for DC

1. **Router Integration:** Which router file should I modify? (`router/*.py`?)
2. **Graph Location:** Where should `entities_relations.json` be stored? (Suggest: `.rag/schema_graph.json`)
3. **A/B Testing:** Do you want feature flag or percentage-based rollout?
4. **Metrics Priority:** Which metric is most important? (Recall? Cost savings?)
5. **Ship Blocker:** Anything that would block v1 ship decision?

---

**Ready to proceed with Week 3?** Let me know if you want to:
1. Start router integration now
2. Build the benchmark first
3. Add optional visualization tools
4. Something else

🚢 **Foundation built. Let's ship this thing!**
