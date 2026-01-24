# Domain RAG Research Prompt

## Research Objective

Investigate groundbreaking and established methods for extending a code-focused RAG system to handle **non-code document repositories**, specifically:

1. **Legal Documents** (contracts, briefs, regulations, patents, filings)
2. **Medical Documents** (clinical notes, research papers, EHR exports, trial data)
3. **Technical Documentation** (manuals, specifications, API docs, knowledge bases)
4. **General Enterprise Documents** (policies, SOPs, memos, reports)

The goal is to identify:
- **Chunking strategies** that preserve semantic meaning for each domain
- **Structure extraction** methods (the equivalent of AST parsing for prose)
- **Domain-specific enrichment** approaches
- **Embedding model** recommendations per domain
- **Graph/relationship** extraction for non-code documents
- **Evaluation methodologies** for domain RAG quality

---

## Existing System Context: LLMC

LLMC (Large Language Model Compressor) is a production-ready, local-first RAG system optimized for code repositories. The research should identify how to extend its primitives to new domains.

### Current Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LLMC Core RAG Stack                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. INDEXING & CHUNKING                                             │
│     ├─ TreeSitter AST parsing (Python, TypeScript, JavaScript)      │
│     ├─ Logical span extraction (functions, classes, blocks)         │
│     ├─ File/span metadata storage (SQLite)                          │
│     └─ Content hashing for change detection (SHA256)                │
│                                                                     │
│  2. EMBEDDING & ROUTING                                             │
│     ├─ Multi-profile embedding system                               │
│     │   ├─ Local: SentenceTransformers, Ollama                      │
│     │   └─ Remote: OpenAI, Jina, custom providers                   │
│     ├─ Content-type routing (code vs docs vs ERP)                   │
│     ├─ Query classification and intent detection                    │
│     └─ Multi-route fan-out with score fusion                        │
│                                                                     │
│  3. ENRICHMENT PIPELINE                                             │
│     ├─ LLM-based metadata generation (summaries, tags, evidence)    │
│     ├─ Backend cascade: local → cheap cloud → premium               │
│     ├─ Domain-aware prompts per content type                        │
│     ├─ Circuit breakers, rate limiting, cost tracking               │
│     └─ Latin1 safety and garbage filtering                          │
│                                                                     │
│  4. SCHEMA GRAPH (GraphRAG)                                         │
│     ├─ Entity extraction: functions, classes, modules, types        │
│     ├─ Relationship extraction: calls, imports, extends, implements │
│     ├─ Graph traversal: where-used, lineage, neighbors              │
│     └─ Graph-aware query enrichment                                 │
│                                                                     │
│  5. SEARCH & RETRIEVAL                                              │
│     ├─ Hybrid search: BM25 + vector similarity                      │
│     ├─ Configurable reranker weights                                │
│     ├─ Extension/path boosting                                      │
│     ├─ Freshness-aware filtering (stale slice rejection)            │
│     └─ Context planner with token budget packing                    │
│                                                                     │
│  6. FRESHNESS & SAFETY                                              │
│     ├─ Per-slice freshness tracking vs. repo HEAD                   │
│     ├─ "No answer > wrong answer" philosophy                        │
│     ├─ Fallback to live file reads when RAG is stale                │
│     └─ Path traversal protection                                    │
│                                                                     │
│  7. SERVICE LAYER                                                   │
│     ├─ Daemon-based background indexing                             │
│     ├─ Event-driven (inotify) file watching                         │
│     ├─ Multi-repo registry                                          │
│     └─ MCP/agent tool integration                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Primitives That Must Generalize

| Code Primitive | Must Generalize To |
|----------------|-------------------|
| TreeSitter AST parsing | Document structure extraction |
| Function/class boundaries | Section/heading/clause boundaries |
| Import graphs | Citation/reference graphs |
| `def`, `class`, `return` signals | Domain-specific structural markers |
| Code enrichment prompts | Domain-tuned extraction prompts |
| Code embedding models | Domain-specific embedding models |
| Call relationships | Semantic relationships (cites, supersedes, contradicts) |

### Current Routing System

LLMC already supports content-type routing:

```toml
# Slice types → routes
[routing.slice_type_to_route]
code        = "code"
docs        = "docs"
erp_product = "erp"
config      = "docs"

# Routes → embedding profiles + indices
[embeddings.routes.code]
profile = "code_jina"
index   = "emb_code"

[embeddings.routes.docs]
profile = "default_docs"
index   = "emb_docs"
```

This architecture should extend to:
```toml
[routing.slice_type_to_route]
legal_contract    = "legal"
legal_regulation  = "legal"
medical_clinical  = "medical"
medical_research  = "medical"
technical_manual  = "tech_docs"
```

---

## Research Questions

### 1. Document Structure Extraction

**For each domain (legal, medical, technical), research:**

1. What are the **structural units** that should become "spans"?
   - Legal: clauses, sections, definitions, recitals, schedules
   - Medical: SOAP sections, findings, assessments, plan items
   - Technical: sections, procedures, warnings, specifications

2. What **parsers or extraction tools** exist?
   - Are there TreeSitter-like grammars for legal document markup?
   - Are there NLP-based section classifiers (e.g., SciBERT for papers)?
   - What about PDF/DOCX structure extraction (headers, lists, tables)?

3. How do we handle **nested/hierarchical structure**?
   - Contracts have nested clause numbering (1.1.1, 1.1.2)
   - Medical records have sections within sections
   - How does this map to LLMC's flat span model?

4. What **metadata** should be extracted per span?
   - Legal: parties mentioned, defined terms, dates, obligations
   - Medical: ICD codes, medications, procedures, patient identifiers (redacted)
   - Technical: cross-references, version numbers, applicability

### 2. Domain-Specific Embedding Models

**Research the landscape:**

1. **Legal Embeddings:**
   - Legal-BERT, CaseLaw-BERT, ContractBERT
   - Commercial offerings (Casetext, LexisNexis embeddings)
   - How do they compare to general-purpose models on legal queries?

2. **Medical/Biomedical Embeddings:**
   - PubMedBERT, BioBERT, ClinicalBERT, SciBERT
   - MedCPT (recent contrastive model)
   - FDA/clinical trial specific models
   - How do they handle medical jargon and abbreviations?

3. **Technical Documentation Embeddings:**
   - CodeBERT variants for API docs
   - Models trained on Stack Overflow + documentation
   - Do general models (E5, BGE) work well enough?

4. **Multi-domain Considerations:**
   - Should we use one model per domain or a strong generalist?
   - What's the performance delta (retrieval quality, latency, cost)?
   - Can we quantize/distill domain models for local inference?

### 3. Domain-Specific Enrichment

**Research enrichment prompts and extraction:**

1. **Legal Document Enrichment:**
   - Extract: parties, obligations, conditions precedent, termination clauses, governing law
   - Identify: defined terms, cross-references between clauses
   - Summarize: clause-level and document-level summaries
   - Risk signals: unusual terms, liability caps, indemnification

2. **Medical Document Enrichment:**
   - Extract: diagnoses (ICD-10), medications (RxNorm), procedures (CPT)
   - Identify: patient demographics (anonymized), provider notes
   - Summarize: clinical findings, treatment plans
   - Signals: contraindications, allergies, critical values

3. **Technical Documentation Enrichment:**
   - Extract: commands, parameters, return values, error codes
   - Identify: prerequisites, related topics, deprecation notices
   - Summarize: procedure summaries, quick reference extraction
   - Signals: warnings, safety notices, breaking changes

4. **Should enrichment use domain-specific LLMs?**
   - Med-PaLM, Legal-GPT variants
   - Or is a strong general model (GPT-4, Claude) sufficient with good prompts?

### 4. Relationship/Graph Extraction

**Extending GraphRAG to documents:**

1. **Legal Relationship Graph:**
   - Clause references other clauses (cross-references)
   - Document supersedes/amends prior document
   - Parties have obligations to other parties
   - Defined terms are used across sections

2. **Medical Relationship Graph:**
   - Diagnosis relates to symptoms, medications, procedures
   - Clinical notes reference prior encounters
   - Medication interactions and contraindications
   - Patient → encounters → providers

3. **Technical Documentation Graph:**
   - API endpoint → parameters → response types
   - Procedure → prerequisites → warnings
   - Component → depends on → other components
   - Topic → related topics

4. **What extraction methods work?**
   - Rule-based (regex, pattern matching)
   - NER + relation extraction models
   - LLM-based extraction with structured output
   - Knowledge graph population techniques

### 5. Evaluation and Quality Metrics

**How do we know if domain RAG is working?**

1. **Retrieval Quality Metrics:**
   - MRR, NDCG, Recall@K for domain-specific test queries
   - Human evaluation of relevance
   - Ground truth dataset creation

2. **Domain-Specific Benchmarks:**
   - LegalBench, ContractNLI (legal)
   - MedQA, PubMedQA, emrQA (medical)
   - Natural Questions, TriviaQA (general)

3. **Freshness and Hallucination Detection:**
   - Do answers cite the correct document/section?
   - Can we detect when RAG is returning stale or wrong context?

### 6. Prior Art and State of the Art

**Research existing systems and papers:**

1. **Commercial Systems:**
   - Harvey AI (legal)
   - Casetext CoCounsel (legal)
   - Google MedLM / Med-PaLM (medical)
   - Notion AI, Confluence AI (enterprise docs)

2. **Academic Papers:**
   - "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" (Lewis et al., 2020)
   - Domain-specific RAG papers (legal, medical, scientific)
   - Chunking strategies research (semantic, recursive, agentic)
   - Long-context alternatives (is RAG still needed with 1M+ context?)

3. **Open Source Projects:**
   - LlamaIndex domain modules
   - LangChain document loaders and splitters
   - Haystack pipelines
   - What do they do well? What's missing?

### 7. Implementation Considerations

**Practical questions for LLMC integration:**

1. **File Format Handling:**
   - PDF extraction (PyMuPDF, pdfplumber, Unstructured)
   - DOCX/ODT parsing
   - HTML/XML structured documents
   - Scanned documents (OCR considerations)

2. **Privacy and Security:**
   - PII/PHI detection and redaction for medical
   - Confidentiality markers for legal
   - Access control per document/section

3. **Scale Considerations:**
   - Legal: tens of thousands of contracts
   - Medical: millions of clinical notes
   - How does LLMC's SQLite backend scale?

4. **Incremental Updates:**
   - Version tracking for documents (amendments, revisions)
   - How to handle "this version supersedes that version"

---

## Deliverables Expected

1. **Literature Review:**
   - Landmark papers for each domain
   - State-of-the-art techniques with citations
   - Commercial system analysis

2. **Architecture Recommendations:**
   - Which primitives to extend vs. replace
   - New modules/extractors needed
   - Configuration schema changes for `llmc.toml`

3. **Model Recommendations:**
   - Embedding models per domain (with benchmarks if available)
   - Enrichment model recommendations
   - Local vs. cloud tradeoffs

4. **Chunking Strategy Recommendations:**
   - Algorithms/heuristics per document type
   - Handling of tables, lists, figures
   - Span boundary detection rules

5. **Prototype Scope:**
   - Suggested MVP for first domain (recommend starting point)
   - Estimated effort
   - Success criteria

---

## Research Sources to Prioritize

- arXiv (cs.CL, cs.IR, cs.AI)
- ACL Anthology
- Google Scholar
- Hugging Face model cards and papers
- LlamaIndex/LangChain documentation
- Industry blogs (Pinecone, Weaviate, Qdrant)
- Legal tech publications (Artificial Lawyer, LegalTech News)
- Medical informatics journals (JAMIA, JBI)

---

## Context: Why This Matters

LLMC already achieves 70-95% token cost reduction for code repositories. Extending this to enterprise documents could provide similar cost savings for:

- Legal departments drowning in contract review
- Healthcare organizations with massive EHR backlogs
- Technical writing teams maintaining documentation
- Compliance teams tracking regulatory changes

The core insight of LLMC—**local-first RAG with freshness guarantees and intelligent routing**—should apply to any domain where context poisoning and stale data are problems.

---

*Research prompt generated: 2025-12-12*
*System version: LLMC v0.6.6 "boxxy is alive"*
