## Contextual Retrieval Upgrade — Software Design Document (SDD)

**Project:** LLM Commander (LLMC)  
**Author:** Senior Software Architect  
**Date:** Nov 3, 2025

### Executive Summary

Our current Retrieval-Augmented Generation (RAG) pipeline relies on plain text chunks stored in `.rag/index.db` and semantic embeddings to retrieve relevant passages. Chunking documents into small spans often strips away crucial context (e.g., the company or timeframe associated with a metric), leading to retrieval misses. Anthropic’s Contextual Retrieval technique mitigates this by prepending each chunk with concise contextual metadata (document title, section summary, surrounding facts) before indexing. By integrating contextualized chunks and a hybrid retrieval strategy (BM25 lexical search + dense embeddings), Anthropic observed a 49% reduction in retrieval failures, and up to 67% when combined with reranking. We propose adopting this technique in LLM Commander, upgrading both the indexing and retrieval pipelines while remaining backward-compatible.

### Technical Background

#### Limitations of Traditional RAG
- Semantic embeddings can miss exact matches or disambiguating details if key terms are absent from the chunk.
- Chunking destroys surrounding context (“revenue grew 3%” without mentioning ACME or Q2 2023).
- Pure embedding search overlooks rare identifiers (error codes, IDs) that BM25 excels at finding.

#### Contextual Retrieval Overview
- Generate a short chunk-specific context sentence (via LLM or heuristics) that situates the chunk within its document.
- Prepend context to the chunk text before embedding and BM25 indexing.
- Hybrid retrieval: run both vector similarity and BM25; fuse results; optionally rerank.
- Anthropic reports contextualized chunks reduce failures by 35% (embeddings only) and 49% (hybrid); adding reranker cut failure rate by 67%.

### System Architecture

**Indexing Workflow**
```
Document → Chunking → Context Generator → Combined (context + chunk)
  → Embedding Index (vectors) & BM25 Index (FTS5)
```

**Query Workflow**
```
Query → Embed to vector → Vector search (top N)
      → BM25 search (top M)
      → Rank fusion (+ optional reranker)
      → Return top K chunks (with context) to agent → LLM answer
```

Components:
- Context Generator (LLM-backed or heuristic) producing 1–3 sentences per chunk.
- Embedding Indexer: stores contextualized vectors in SQLite `embeddings` table.
- BM25 Index: SQLite FTS5 virtual table for lexical search of combined text.
- Hybrid Retriever: merges vector and BM25 results using reciprocal rank fusion; optional reranker.
- LLM Commander Agent: calls retrieval as a tool; receives chunks with context metadata.

### Implementation Specification

#### Database Schema Changes (`.rag/index.db`)
- `ALTER TABLE enrichments ADD COLUMN context TEXT` — store generated context per span.
- `CREATE VIRTUAL TABLE fts_chunks USING fts5(content, span_id UNINDEXED, tokenize='porter');`
- Optional: triggers to delete/update `fts_chunks` entries when spans removed.

#### Context Generation
- Prompt template (customizable) similar to Anthropic’s: provide whole document + chunk; request concise context (≤2 sentences, ≤100 tokens).
- Support prompt caching when available (e.g., Claude). For other APIs, allow heuristic fallback (e.g., use document title/heading).
- Store context string in `enrichments.context`; mark model version.

#### Embedding & Text Indexing
- Combine context + chunk text (`context + 
