# Embedding Model Selection — Companion Summary (LLMC)

> This markdown file summarizes the **Embedding Model Selection SDD** you uploaded (`embedding model.pdf`).  
> Use it as a quick-reference; the PDF remains the canonical source of truth.

---

## Executive Summary

- **Recommendation:** Use an **open-source, unified embedding model** for both code and docs, defaulting to **`intfloat/e5-base-v2` (768‑dim)**.
- **Why:** +10–15% Recall@5 improvement over MiniLM baseline with **zero API cost** and **<100 ms/embedding** on commodity hardware.
- **Runners‑up:** OpenAI `text-embedding-3-large` (best OpenAI, 3072‑dim, API) and **Voyage `voyage-code-2`** (code‑specialized, API). Use when you need absolute top code recall and can accept API dependency.
- **Dimension guidance:** **768–1536 dims** are the sweet spot. Above that yields diminishing returns but increases storage/memory.
- **Cost:** API costs are small per repo, but local stays effectively free at scale and avoids network/PII concerns.

---

## Model Comparison Highlights

**API**  
- **OpenAI `text-embedding-3-small` (1536)** — very cheap; solid text; decent for code.  
- **OpenAI `text-embedding-3-large` (3072)** — best OpenAI overall; supports dimension shortening.  
- **Cohere `embed-english-v3` (768)** — good text, not tuned for code.  
- **Voyage `voyage-code-2` (1536)** — code‑specialized; SOTA on code retrieval; API only.

**Local (Open Source)**  
- **E5‑Base‑v2 (768)** — **recommended default**; strong on both code and text; fast & light.  
- **BGE‑Base‑en‑v1.5 (768)** — also strong; prefers prompt prefixes.  
- **Nomic Embed‑Text‑v1 (768)** — top text accuracy; heavier; long input support.  
- **Nomic Embed‑Code (4096, 7B)** — SOTA code retriever; heavy; not suitable for <100 ms target.  
- **CodeBERT/GraphCodeBERT (768)** — older; trails modern models.

**Key takeaways**  
- Specialized code models (Voyage, Nomic‑Code) beat general models on code tasks, but the **gap to E5‑base** is often **≤5–10%**.  
- **Unified model** simplifies ops and is sufficient unless a **>15%** gain is proven for code‑only tasks.

---

## Performance & Storage

- **Latency:** 2–5 ms per 100–200‑token span on GPU; tens of ms on CPU.  
- **Storage:** 768‑dim ≈ 3 KB/vector; **50K spans ≈ ~150 MB** for vectors (plus DB overhead).  
- **Similarity:** Prefer cosine. Normalize vectors for consistency if your store doesn’t.

---

## Integration Steps

1. **Swap model:**  
   ```python
   from sentence_transformers import SentenceTransformer
   model = SentenceTransformer('intfloat/e5-base-v2')
   ```
   Optional prefixes: `"query: ..."`, `"passage: ..."`.

2. **Reindex:** Create a **new collection** (e.g., `workspace_code_e5`) in Chroma/SQLite; embed all spans; verify counts.

3. **Query path:** Embed incoming queries with the same model & prefixes; search the new collection.

4. **Validate:** Check relevance on known queries, measure P@5/R@5; verify <100 ms latency for 10K vectors.

5. **Cutover & monitor:** Phase out old vectors after validation; watch index growth and planner confidence.

---

## Fine‑Tuning (Optional)

- Consider only if recurring misses remain after the swap.  
- Use SentenceTransformers with **MultipleNegativesRankingLoss** on project‑specific (query, code/doc) pairs.  
- Start small (1–3 epochs), validate uplift; keep unified dimension.

---

## Migration Checklist

- [ ] Backup current index (SQLite/Chroma)  
- [ ] Switch model & prefixes; batch embed in new collection  
- [ ] Point queries to new collection  
- [ ] Validate P@5/R@5 against a small golden set  
- [ ] Retire old embeddings; document model + dim in README

---

**Source:** See the full SDD (`embedding model.pdf`) in this folder for detailed tables, benchmarks, code snippets, cost analysis, and a complete migration plan.
