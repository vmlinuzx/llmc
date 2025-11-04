## Token Compression RAG — Software Design Document (SDD)

**Project:** LLM Commander (LLMC)  
**Author:** Senior Software Architect  
**Date:** Nov 3, 2025

### 1. Executive Summary

**Problem.** Retrieved RAG chunks in LLMC are verbose (5K–15K tokens per query batch), containing boilerplate, comments, and repetition. Even with Contextual Retrieval, input size remains the primary cost driver for GPT-class models.

**Solution.** Introduce a multi-layer token compression stage between retrieval and answer synthesis: (1) abstractive summarization using a fine-tuned sequence-to-sequence model (T5/BART), followed by (2) semantic token removal using deterministic, query-aware rules and entropy heuristics. Optionally (3) hybrid LLM compression using a low-cost API/local model as fallback.

**Expected Outcome.** ~65% reduction in retrieval tokens with maintained or slightly improved answer accuracy; an optional additional ~20% reduction with small, configurable accuracy tradeoff. Latency impact is modest (<500ms/chunk on local inference), offset by lower upstream LLM compute.

**Cost-Benefit.** A lightweight one-time fine-tune on in-repo corpora amortizes rapidly against recurring token costs. Compression runs locally; only compressed context is sent to cloud LLMs.

### 2. Technical Background

#### 2.1 Why LLMC RAG Chunks Are Verbose
- Boilerplate & legal headers repeated across files
- Code comments & docstrings with low marginal value for many queries
- Generated artifacts/logs that are long but semantically thin
- Chunking at paragraph/file boundaries pulls extra context that is not query-critical

#### 2.2 Research Basis & Approach
We operationalize two complementary strategies:

- **Abstractive summarization** — condense retrieved passages into short, query-aligned summaries while preserving key facts, identifiers, and constraints.
- **Semantic compression** — remove low-information tokens from the summarizer output and (when safe) directly from retrieved text (e.g., articles, filler phrases, repeated scaffolding, excessive whitespace/comments in code), with code-aware safeguards.

#### 2.3 Token Economics & Break-Even
- Typical pre-compression: ~10K input tokens/query batch
- Target post-compression: ~3.5K tokens (≈65% reduction)
- Savings: ~6.5K tokens/query. With $10 per 1M tokens, ≈$0.065 saved per query. Fine-tune costs pay back within 0.8–1.6K queries.

### 3. System Architecture

#### 3.1 High-Level Flow
```
Query → Retriever (Contextual Retrieval) → (K chunks + metadata)
    → Compression Layer
       → Abstractive Summarizer (T5/BART, local)
       → Semantic Token Removal (spaCy + rules + entropy)
       → Validation (length/semantic checks)
    → Cache (compressed_chunks)
    → Composer → LLM Prompt (Beatrice/Otto/Rem routing) → Answer
```

#### 3.2 Where Compression Happens
- **Retrieval-time (default):** compress on demand using query-aware signals.
- **Indexing-time (optional):** store static compressions for frequently retrieved files with fingerprints for revalidation.
- **Hybrid:** retrieval-time compression can further compress indexed summaries when a query demands brevity.

#### 3.3 Agent Responsibilities
- **Retriever (existing):** return top-K enriched spans from `.rag/index.db`.
- **Compressor (new):** performs summarization → semantic removal → validation; exposes a TypeScript API.
- **Composer/Router (existing):** chooses target model (Qwen 7B/14B, GPT-5 nano, etc.) and now feeds compressed spans.

#### 3.4 Integration with Contextual Retrieval
Contextual metadata (file path, symbol, commit, doc section) is fed to the summarizer prompt, steering query-aware compression. The compressor preserves identifiers, function signatures, config keys, and error codes.

### 4. Compression Strategies — Detailed Design

#### 4.1 Abstractive Summarization (Primary Strategy)
- **Model:** T5-base or BART-base fine-tuned on LLMC corpora.
- **Input:** retrieved chunk text + contextual metadata + query.
- **Output target size:** ~35% of original tokens (configurable via budget controller).
- **Prompting:** prefix with task tag (e.g., `summarize for rag:`) and append structured metadata lines. Fence code sections to cue preservation.
- **Safety rules:** always preserve
  - Function/method signatures
  - Configuration keys and environment variable names
  - Error/HTTP codes, CLI flags, file paths
  - Table/column names, SQL snippets
  - RFC/standard identifiers, version constraints
- **Training data generation:** sample chunks from `.rag/index.db` and docs, construct (chunk, query) → compressed summary pairs, bootstrap with high-quality API model, human spot-check, fine-tune locally.
- **Budget controller:** start with per-chunk token budget (e.g., 35%); if combined context exceeds prompt budget, proportionally reduce per-chunk budgets or rerank with tighter K.

#### 4.2 Semantic Token Removal (Secondary Layer)
- **Pipeline:**
  1. POS tagging (spaCy) to mark stopword-like tokens outside code blocks.
  2. Regex pruning to collapse whitespace, strip banners/legal boilerplate, long comment blocks (unless query mentions licensing/compliance).
  3. Entropy filter using tf-idf or perplexity proxies to drop low-information tokens within safety bounds.
  4. Code-aware minifier to remove comments/blank lines and optionally pretty-print signatures.
- **Goal:** additional ~20% reduction on summarizer outputs. Aggressiveness configurable to bound accuracy loss.

#### 4.3 Hybrid LLM Compression (Fallback)
If local model confidence is low (ROUGE/semantic thresholds), call a cheap LLM (Qwen 7B/14B local or GPT-3.5-tier API) to re-summarize short segments and re-assemble. Use only when cache miss + local model underperforms; cache the result.

### 5. Implementation Specification

#### 5.1 Database Schema (SQLite)
```sql
CREATE TABLE IF NOT EXISTS compressed_chunks (
  id INTEGER PRIMARY KEY,
  original_chunk_id INTEGER NOT NULL,
  query_hash TEXT NOT NULL,
  compressed_text TEXT NOT NULL,
  compression_ratio REAL NOT NULL,
  method_used TEXT NOT NULL,
  quality_score REAL,
  model_version TEXT NOT NULL,
  created_at_utc TEXT NOT NULL,
  UNIQUE(original_chunk_id, query_hash, model_version)
);

CREATE TABLE IF NOT EXISTS static_summaries (
  id INTEGER PRIMARY KEY,
  source_fingerprint TEXT NOT NULL,
  summary TEXT NOT NULL,
  model_version TEXT NOT NULL,
  created_at_utc TEXT NOT NULL,
  UNIQUE(source_fingerprint, model_version)
);
```

#### 5.2 Compression Pipeline (Runtime)
1. Retrieve top-K enriched chunks with metadata.  
2. For each chunk:
   - Compute `query_hash`; check `compressed_chunks` cache.
   - Cache hit → collect compressed text.
   - Cache miss →
     1. Run abstractive summarizer.
     2. Apply semantic pruning.
     3. Validate length/semantic similarity/guardrails.
     4. Store compressed chunk in cache.
3. Compose final prompt from compressed texts + minimal metadata header.
4. Send to selected LLM via LLMC router.

#### 5.3 TypeScript API Sketch
```ts
// lib/compression/types.ts
export type CompressionMethod = 't5' | 't5+semantic' | 'hybrid';
export interface CompressionOptions {
  targetRatio?: number;
  minQuality?: number;
  method?: CompressionMethod;
}

export interface CompressionResult {
  text: string;
  ratio: number;
  quality: number;
  method: CompressionMethod;
  modelVersion: string;
}
```
```ts
// lib/compression/index.ts
export async function compressChunk(
  chunkId: number,
  rawText: string,
  meta: Record<string, string>,
  query: string,
  opts: CompressionOptions = {}
): Promise<CompressionResult> {
  const { targetRatio = 0.35, minQuality = 0.78, method = 't5+semantic' } = opts;
  const cache = await getCompressed(chunkId, query);
  if (cache) return cache;

  const abstractive = await compressWithT5(rawText, meta, query, targetRatio);
  let text = abstractive.text;
  let ratio = abstractive.ratio;
  let quality = abstractive.quality;
  let used: CompressionMethod = 't5';

  if (method !== 't5') {
    const pruned = await pruneSemantically(text, { meta, query, targetRatio });
    text = pruned.text;
    ratio = pruned.ratio;
    quality = Math.min(quality, pruned.quality);
    used = 't5+semantic';
  }

  if (quality < minQuality) {
    const hybrid = await recompressHybrid(text, { query, targetRatio });
    text = hybrid.text;
    ratio = hybrid.ratio;
    quality = hybrid.quality;
    used = 'hybrid';
  }

  return await upsertCompressed(chunkId, query, { text, ratio, quality, method: used });
}
```

#### 5.4 Guardrails & Validation
- Length bound: enforce target ratio ±10%.
- Semantic similarity: cosine ≥ threshold with encoder embeddings.
- Critical tokens: regex lists for flags/env vars/routes.
- Abort: if quality < floor (e.g., 0.70), fall back to uncompressed chunk.

### 6. Fine-Tuning Implementation
- **Data:** ~10k (chunk, query) → summary pairs sampled from `.rag/index.db`, docs, scripts, apps/web.
- **Model:** T5-base for balance of speed & quality; evaluate BART/LED if needed.
- **Training (HuggingFace):** batch 16 (accum to 64), lr 3e-5, epochs 5–10, label smoothing 0.1, max input 2048, target 512. Monitor ROUGE-L and semantic similarity.
- **Deployment:** export to ONNX, run via onnxruntime/TensorRT, versioned in `.rag/models/`.

### 7. Performance & Cost Analysis
- **Token economics:** 10K → 3.5K, saving 6.5K tokens/query (~$0.065 at $10/M). 20K queries/year ≈ $1,300 saved.
- **Latency:** local T5 inference ~100–500ms/chunk; pruning adds 10–40ms. Smaller upstream prompts reduce total latency.
- **Quality metrics:** compression ratio, similarity score, cache hit rate, answer accuracy vs. baseline. Auto-tune aggressiveness if accuracy dips.

### 8. Configuration & UI
- Template Builder controls for enabling compression, aggressiveness slider (45–75%), method selection, model choice, cache toggles.
- Runtime parameters: `compressionRatio`, `minQualityThreshold`, `cacheEnabled`, `preserveCodeBlocks`, `maxPromptTokens`.

### 9. Testing Strategy
- **Unit:** summarizer correctness, pruner safety, cache integrity.
- **Integration:** end-to-end smoke tests; A/B harness for answer quality & latency.
- **Benchmarks:** corpus-wide compression ratio/quality; cost dashboard of token inputs/outputs.

### 10. Migration & Rollout
- **Phase 1:** opt-in behind `LLMC_COMPRESSION=on`.
- **Phase 2:** 25–50% traffic A/B; tune thresholds.
- **Phase 3:** default-on for large-span routes; auto-fallback on quality drops.
- **Phase 4:** maintain per-template fine-tunes.
- Backward compatibility: legacy flows still function; cache warms incrementally.

### 11. Future Enhancements
- Query-aware budgets allocating more budget to high-relevance chunks.
- Output compression for verbose model responses.
- Multi-modal compression for diagrams/alt-text when safe.
- Teaching-LM distillation to learn token importance maps from router targets.

### 12. Alternative Approaches Considered
- Reranking only (improves relevance but not size).
- Prompt “be concise” (doesn’t reduce input cost).
- Knowledge graph only (high complexity, loses nuance).

### 13. Code Examples
See sections 5.3 and 6 for TypeScript/Python/SQL snippets (fine-tuning T5, semantic pruner, DB accessors) included above.

### 14. Quality Assurance & Safety Nets
- Maintain critical token lists per project; regression tests validate preservation.
- Degradation detector: if A/B accuracy drops beyond SLA (e.g., −0.5%), auto-scale back aggressiveness and alert.
- Compressor emits per-chunk stats to `logs/autosave.log` for traceability.

### 15. Rollout Plan for LLMC
- Implement compression layer behind `LLMC_COMPRESSION=on`.
- Add Template Builder UI controls for defaults & sliders.
- Ship pre-trained T5-base; schedule nightly fine-tunes.
- Enable first for large-span routes determined by router pre-flight.
- Evaluate, tune, and eventually default-on for all RAG routes.

### 16. Appendix — Prompts & Heuristics
- **Summarizer prompt template:**
```
summarize for rag:
query: {QUERY}
meta:
- source_path: {PATH}
- symbol: {SYMBOL}
- commit: {COMMIT}
- section: {SECTION}

text:
{CHUNK_TEXT}

constraints:
- keep function signatures, flags, env vars, routes, SQL identifiers
- if code, keep fenced blocks; remove comments unless query mentions comments
- target_ratio: {TARGET_RATIO}
```
- **Composer header:**
```
# Context (compressed)
- provenance: compressed_chunks (t5+semantic)
- model: {MODEL_VERSION}
- compression_ratio: {AVG_RATIO}
- K: {K}
```
- **Heuristics:** disable license pruning if metadata indicates compliance topics; preserve complexity/big-O notes for performance queries; keep full error messages.

---

The design leverages cutting-edge research on TCRA token compression (~65% reduction with +0.3% accuracy) and semantic pruning (~20% extra reduction with ~1.6% accuracy tradeoff), while integrating seamlessly with LLMC’s existing routing and Template Builder UX.
