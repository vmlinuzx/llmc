# SDD: Domain RAG – Technical Documentation Support

**Date:** 2025-12-12  
**Author:** Dave + Antigravity  
**Branch:** `feature/domain-rag-tech-docs`  
**Status:** Draft  
**Research:** `DOCS/legacy/research/Extending LLMC to Domain-Specific Documents Research Finding.md`, `DOCS/legacy/research/Extending RAG to Non-Code Domains.md`

---

## 1. Problem Statement

LLMC currently excels at **code repositories** but provides only basic support for **non-code document repositories** (legal, medical, technical docs). Users with:

- Technical documentation repos (API docs, manuals, knowledge bases)
- Legal document collections (contracts, regulations)
- Medical documentation (clinical notes, research papers)

...get suboptimal results because:

1. **Chunking** uses code-oriented boundaries (AST nodes) that don't apply to prose
2. **Embeddings** use generic models that miss domain-specific semantics
3. **Enrichment prompts** are tuned for code, not contract clauses or clinical findings
4. **Graph extraction** looks for imports/calls, not citations/cross-references

### Why Technical Docs First?

Technical documentation is the **lowest-risk, highest-value** starting point:

- Already semi-structured (Markdown headings, DITA XML, RST)
- Closest to code (often includes code snippets)
- Clear evaluation criteria (did it find the right API parameter?)
- No privacy concerns like medical data
- Already present in code repos (README, DOCS/)

---

## 2. Solution: Domain-Aware Repository Types

Add a **repository domain type** to `llmc.toml` that controls:

1. **Parser selection** – How to chunk documents
2. **Embedding profile** – Which model understands the domain
3. **Enrichment prompts** – What to extract
4. **Graph schema** – What relationships to capture

### Repository Types

| Type | Description | Parser | Embedding |
|------|-------------|--------|-----------|
| `code` | Source code repositories | TreeSitter AST | `nomic-embed-text` (default) |
| `tech_docs` | Technical documentation | Heading/Section-aware | `bge-m3` or `nomic-embed-text` |
| `legal` | Contracts, regulations | Clause/Section regex | `legal-bert` |
| `medical` | Clinical notes, research | SOAP/FHIR extraction | `medcpt` |
| `mixed` | Default – auto-detect per file | Hybrid | Per-file routing |

---

## 3. Configuration Schema

### 3.1 New Top-Level Section

```toml
# ==============================================================================
# REPOSITORY DOMAIN
# ==============================================================================
# Specifies the primary content type of this repository.
# Affects chunking, embedding, enrichment, and graph extraction.

[repository]
# Repository domain type: "code" | "tech_docs" | "legal" | "medical" | "mixed"
# Default: "mixed" (auto-detects per file)
domain = "code"

# For mixed repos: how to classify files not matching explicit rules
default_domain = "tech_docs"  # Fallback for unrecognized content

# Override domain for specific path patterns
[repository.path_overrides]
"DOCS/**" = "tech_docs"
"contracts/**" = "legal"
"*.md" = "tech_docs"
"*.py" = "code"
```

### 3.2 Override Precedence Rules

**Resolution order (first match wins):**

1. **Exact path match** – `"DOCS/API.md"` beats all
2. **Most specific glob** – `"DOCS/API/*.md"` beats `"DOCS/**"`
3. **Path depth** – deeper paths win (`"a/b/c/*"` > `"a/b/*"`)
4. **`default_domain`** – fallback for unmatched files
5. **`repository.domain`** – global default

**Diagnostics:** Add `--show-domain-decisions` flag to indexer:

```
INFO indexer: file=DOCS/API.md domain=tech_docs reason=path_override:DOCS/**
INFO indexer: file=src/main.py domain=code reason=extension:.py
INFO indexer: file=notes.txt domain=tech_docs reason=default_domain
```

### 3.3 Domain-Specific Embedding Profiles

Extend existing embedding profiles with domain hints:

```toml
# Tech docs embedding profile
[embeddings.profiles.tech_docs]
provider = "ollama"
model = "bge-m3"          # Hybrid dense+sparse, good for technical jargon
dimension = 1024
capabilities = ["technical", "multilingual"]

[embeddings.profiles.tech_docs.ollama]
api_base = "http://localhost:11434"
timeout = 120

# Legal embedding profile (future)
[embeddings.profiles.legal]
provider = "ollama"
model = "legal-bert-base-uncased"
dimension = 768
capabilities = ["legal"]
```

### 3.4 Domain Routing Extension

```toml
[routing.slice_type_to_route]
# Existing
code = "code"
docs = "docs"
erp_product = "erp"

# New domain-specific types
tech_manual = "tech_docs"
tech_api_reference = "tech_docs"
legal_contract = "legal"
legal_regulation = "legal"
medical_clinical = "medical"
medical_research = "medical"

[embeddings.routes.tech_docs]
profile = "tech_docs"
index = "emb_tech_docs"
sharing = "per-repo"          # "shared" | "per-repo" – index strategy for multi-repo
index_name_suffix = ""         # Optional suffix for collision-free multi-repo deployments

[embeddings.routes.legal]
profile = "legal"
index = "emb_legal"
sharing = "per-repo"

[embeddings.routes.medical]
profile = "medical"
index = "emb_medical"
sharing = "per-repo"
```

**Index Sharing Semantics:**
- `sharing = "shared"` – All repos using this profile write to the same index (e.g., org-wide docs)
- `sharing = "per-repo"` – Each repo gets `{index}_{repo_name}` (default, safer)
- `index_name_suffix` – For deployments with multiple LLMC instances

---

## 4. Technical Documentation Parser

### 4.1 Chunking Strategy

Technical docs should be chunked by **semantic structure**, not arbitrary token counts:

| Source Format | Chunk Boundaries | Metadata |
|---------------|------------------|----------|
| **Markdown** | `#` headings (H1-H6) | `section_path: "Install > Prerequisites"` |
| **DITA XML** | `<topic>`, `<task>`, `<concept>` | `topic_type: "task", prereqs: [...]` |
| **RST** | Section underlines | `section_path: "...""` |
| **HTML** | `<h1>`-`<h6>`, `<section>` | `section_path: "..."` |

#### Key Principles

1. **Never split procedures** – A 10-step procedure is one chunk, even if large
2. **Preserve code with context** – Keep code blocks with their surrounding explanation
3. **Prepend section path** – Every chunk includes its heading hierarchy for context
4. **Keep lists intact** – Bullet/numbered lists are atomic units

### 4.2 Implementation: `TechDocsExtractor`

```python
# tools/rag/extractors/tech_docs.py

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
import re

@dataclass
class TechDocsSpan:
    """A semantic chunk from technical documentation."""
    content: str
    section_path: str           # e.g. "Installation > Prerequisites"
    span_type: str              # "heading", "paragraph", "code_block", "list", "table"
    start_line: int
    end_line: int
    metadata: dict              # doc_title, version, etc.

class TechDocsExtractor:
    """Extracts semantic spans from technical documentation."""
    
    def __init__(self, 
                 max_chunk_tokens: int = 512,
                 preserve_code_context: bool = True):
        self.max_chunk_tokens = max_chunk_tokens
        self.preserve_code_context = preserve_code_context
    
    def extract(self, path: Path, content: str) -> Iterator[TechDocsSpan]:
        """Extract spans from a technical document."""
        ext = path.suffix.lower()
        
        if ext in {'.md', '.markdown'}:
            yield from self._extract_markdown(path, content)
        elif ext in {'.rst'}:
            yield from self._extract_rst(path, content)
        elif ext in {'.xml', '.dita'}:
            yield from self._extract_dita(path, content)
        elif ext in {'.html', '.htm'}:
            yield from self._extract_html(path, content)
        else:
            # Fallback: paragraph-based chunking
            yield from self._extract_paragraphs(path, content)
    
    def _extract_markdown(self, path: Path, content: str) -> Iterator[TechDocsSpan]:
        """Extract spans from Markdown using heading hierarchy."""
        lines = content.split('\n')
        heading_stack = []  # [(level, title), ...]
        current_chunk = []
        current_start = 0
        
        for i, line in enumerate(lines):
            # Detect ATX heading (supports trailing hashes: ## Title ##)
            heading_match = re.match(
                r'^(#{1,6})\s+(?P<title>.+?)(?:\s+#+\s*)?$', line
            )
            
            if heading_match:
                # Emit previous chunk
                if current_chunk:
                    yield self._make_span(
                        content='\n'.join(current_chunk),
                        section_path=self._build_section_path(heading_stack),
                        span_type='section',
                        start_line=current_start,
                        end_line=i - 1,
                        path=path
                    )
                
                # Update heading stack
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                # Pop deeper or equal headings
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, title))
                
                current_chunk = [line]
                current_start = i
            else:
                current_chunk.append(line)
        
        # Emit final chunk
        if current_chunk:
            yield self._make_span(
                content='\n'.join(current_chunk),
                section_path=self._build_section_path(heading_stack),
                span_type='section',
                start_line=current_start,
                end_line=len(lines) - 1,
                path=path
            )
    
    def _build_section_path(self, heading_stack: list) -> str:
        """Build section path like 'Install > Prerequisites > Step 1'."""
        return ' > '.join(title for _, title in heading_stack)
    
    def _make_span(self, content: str, section_path: str, span_type: str,
                   start_line: int, end_line: int, path: Path) -> TechDocsSpan:
        """Create a span with context prepended."""
        # Prepend section path for retrieval context
        if section_path:
            contextualized = f"[{section_path}]\n\n{content}"
        else:
            contextualized = content
        
        return TechDocsSpan(
            content=contextualized,
            section_path=section_path,
            span_type=span_type,
            start_line=start_line,
            end_line=end_line,
            metadata={
                'doc_title': path.stem,
                'file_path': str(path),
                'neighbors': {  # For large chunks, enable adjacency retrieval
                    'prev': None,  # Populated during indexing
                    'next': None,
                }
            }
        )
    
    def _extract_dita(self, path: Path, content: str) -> Iterator[TechDocsSpan]:
        """Extract spans from DITA XML using iterparse for memory efficiency.
        
        Note: Uses iterparse to handle large DITA files (20MB+) without memory spikes.
        Preserves @id/@rev attributes for graph versioning.
        """
        from lxml import etree
        
        try:
            # Use iterparse for streaming large files
            context = etree.iterparse(
                io.BytesIO(content.encode()),
                events=('end',),
                tag=('topic', 'task', 'concept', 'reference')
            )
        except etree.XMLSyntaxError:
            yield from self._extract_paragraphs(path, content)
            return
        
        for event, topic in context:
            title = topic.findtext('title', default='Untitled')
            body = topic.find('body') or topic.find('taskbody') or topic.find('conbody')
            
            if body is not None:
                text_content = etree.tostring(body, method='text', encoding='unicode')
                yield TechDocsSpan(
                    content=f"[{title}]\n\n{text_content}",
                    section_path=title,
                    span_type=topic.tag,
                    start_line=0,
                    end_line=0,
                    metadata={
                        'doc_title': path.stem,
                        'topic_type': topic.tag,
                        'topic_id': topic.get('id', ''),
                        'topic_rev': topic.get('rev', ''),  # Version tracking
                    }
                )
            # Clear element to free memory during streaming
            topic.clear()
    
    def _extract_paragraphs(self, path: Path, content: str) -> Iterator[TechDocsSpan]:
        """Fallback: split by blank lines (paragraph boundaries)."""
        paragraphs = re.split(r'\n\s*\n', content)
        line = 0
        
        for para in paragraphs:
            para = para.strip()
            if para:
                para_lines = para.count('\n') + 1
                yield TechDocsSpan(
                    content=para,
                    section_path='',
                    span_type='paragraph',
                    start_line=line,
                    end_line=line + para_lines - 1,
                    metadata={'doc_title': path.stem}
                )
                line += para_lines + 1  # +1 for blank line
```

---

## 5. Technical Docs Enrichment

### 5.1 Enrichment Prompt

Different from code enrichment – focuses on extracting technical metadata:

```python
TECH_DOCS_ENRICHMENT_PROMPT = """You are analyzing technical documentation. Extract structured information.

DOCUMENT SECTION:
{content}

EXTRACT (JSON):
{{
  "summary": "One sentence describing what this section explains",
  "key_concepts": ["list", "of", "main", "concepts"],
  "parameters": [
    {{"name": "param_name", "type": "string", "description": "what it does"}}
  ],
  "code_examples": true/false,
  "prerequisites": ["any", "required", "prior", "knowledge"],
  "warnings": ["any", "cautions", "or", "notes"],
  "related_topics": ["cross-references", "see also"],
  "audience": "developer" | "admin" | "user" | "mixed"
}}

Only include fields that are present in the content. Be concise.
"""
```

### 5.2 Enrichment Chain Config

```toml
# Technical documentation enrichment chain
[[enrichment.chain]]
name = "tech_docs_qwen3_4b"
chain = "tech_docs_chain"
provider = "ollama"
model = "qwen3:4b-instruct"
url = "http://localhost:11434"
routing_tier = "4b"
timeout_seconds = 90
enabled = true
options = { num_ctx = 8192, temperature = 0.2 }

[enrichment.routes]
tech_docs = "tech_docs_chain"
```

### 5.3 Schema-Validated Enrichment Output

**Rationale:** Enrichment outputs become stable handles for TE/MCP consumption. Use Pydantic for validation and persist to JSONL with stable IDs.

```python
# tools/rag/schemas/tech_docs_enrichment.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import hashlib

class ParameterDoc(BaseModel):
    """A documented parameter."""
    name: str = Field(..., max_length=100)
    type: Optional[str] = Field(None, max_length=50)
    description: str = Field(..., max_length=500)

class TechDocsEnrichment(BaseModel):
    """Schema-validated enrichment output for tech docs."""
    
    # Stable ID: hash(file_path + section_path)
    span_id: str = Field(..., description="Stable identifier for this span")
    
    summary: str = Field(..., max_length=200)
    key_concepts: list[str] = Field(default_factory=list, max_length=10)
    parameters: list[ParameterDoc] = Field(default_factory=list)
    code_examples: bool = False
    prerequisites: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    related_topics: list[str] = Field(default_factory=list)
    audience: str = Field("mixed", pattern=r"^(developer|admin|user|mixed)$")
    
    @field_validator('key_concepts', 'prerequisites', 'warnings', 'related_topics')
    @classmethod
    def limit_list_length(cls, v):
        return v[:10]  # Guard against injection of massive lists
    
    class Config:
        extra = "forbid"  # Reject unexpected keys (injection guard)
        
    @classmethod
    def make_span_id(cls, file_path: str, section_path: str) -> str:
        """Generate stable ID from file + section."""
        return hashlib.sha256(f"{file_path}::{section_path}".encode()).hexdigest()[:16]
```

**JSONL Persistence:**
```python
# Write validated enrichments to stable JSONL
def persist_enrichment(enrichment: TechDocsEnrichment, output_path: Path):
    with output_path.open('a') as f:
        f.write(enrichment.model_dump_json() + '\n')
```

### 5.4 Hybrid Search & Reranking

**Rationale:** Pure dense embeddings miss exact keyword matches on API parameters. Hybrid search combines best of both.

```toml
[search.tech_docs]
# Hybrid search: dense + sparse
hybrid_enabled = true
dense_weight = 0.6      # bge-m3 dense vectors
sparse_weight = 0.4      # BM25 for exact keyword matching

# Reranker for precision on parameter queries
reranker_enabled = true
reranker_model = "bge-reranker-v2-m3"
reranker_top_k = 20     # Rerank top 20 candidates

# Optional: curated synonym list for domain jargon
synonym_file = "synonyms/tech_docs.txt"  # sign-in/login/authentication
```

**Synonym file format (`synonyms/tech_docs.txt`):**
```
sign-in,login,authenticate,log in
config,configuration,settings
delete,remove,destroy,rm
```

---

## 6. Graph Extraction for Tech Docs

### 6.1 Relationship Types

| Edge Type | Meaning | Example |
|-----------|---------|---------|
| `REFERENCES` | Section cross-references | "See Installation Guide" |
| `REQUIRES` | Prerequisite dependency | "Requires Python 3.10+" |
| `RELATED_TO` | Topical relationship | "Related: Authentication" |
| `SUPERSEDES` | Version relationship | "Replaces v1.0 API" |
| `WARNS_ABOUT` | Warning/caution | "Warning: Data loss possible" |

### 6.2 Extraction Rules

```python
TECH_DOCS_GRAPH_PATTERNS = {
    # Cross-references
    'REFERENCES': [
        r'[Ss]ee (?:also:?\s+)?["\']?([^"\']+)["\']?',
        r'[Rr]efer to (?:the )?([^\.\,]+)',
        r'\[([^\]]+)\]\([^\)]+\)',  # Markdown links
    ],
    # Prerequisites
    'REQUIRES': [
        r'[Rr]equires?:?\s+(.+?)(?:\.|$)',
        r'[Pp]rerequisites?:?\s+(.+?)(?:\.|$)',
        r'[Mm]ust have:?\s+(.+?)(?:\.|$)',
    ],
    # Warnings
    'WARNS_ABOUT': [
        r'[Ww]arning:?\s+(.+?)(?:\.|$)',
        r'[Cc]aution:?\s+(.+?)(?:\.|$)',
        r'[Nn]ote:?\s+(.+?)(?:\.|$)',
    ],
}
```

### 6.3 Graph Node Canonicalization

**Node types** with canonical keys:

| Node Type | Required Keys | Optional Keys |
|-----------|---------------|---------------|
| `Section` | `id`, `path`, `title` | `version`, `rev` |
| `Procedure` | `id`, `path`, `steps_count` | `duration`, `difficulty` |
| `Parameter` | `id`, `name`, `type` | `default`, `required` |
| `Warning` | `id`, `severity`, `message` | `workaround` |

**Edge normalization:**
```python
@dataclass
class GraphEdge:
    source_id: str          # Canonical span_id
    target_id: str          # Resolved target (not raw text)
    edge_type: str          # REFERENCES, REQUIRES, etc.
    provenance: dict        # { "pattern_id": "...", "match_text": "..." }
```

### 6.4 LLM-Assisted Graph Extraction (Optional)

For complex cross-references that regex can't handle:

```toml
[graph.tech_docs]
ruleset = "default"        # Regex patterns above
llm_assist_enabled = false  # Toggle per environment
llm_model = "qwen3:4b"     # Cheaper model for extraction
store_provenance = true     # Track source of each edge
```

When enabled, LLM pass runs on spans where regex finds no edges but content suggests relationships exist.

### 6.5 Version Tracking & Supersession

```python
# Track document versions for SUPERSEDES edges
@dataclass  
class DocVersion:
    doc_id: str
    version: str           # From metadata or filename
    supersedes: list[str]  # Previous version IDs
    deprecated: bool = False
```

### 6.6 MCP Resource Exposure

**Rationale:** Expose tech-doc sections as MCP resources so hosts can fetch exactly what they need without flooding context. Aligns with selective capability strategy.

```python
# MCP resource URI scheme
# tech_doc://{repo}/{doc_id}#{section_path}
# Example: tech_doc://llmc/ROADMAP#Testing Demon Army

@dataclass
class TechDocResource:
    """MCP resource for a tech doc section."""
    uri: str                    # tech_doc://llmc/API#Parameters
    title: str                  # "Parameters"
    section_path: str           # "API > Configuration > Parameters"
    handle: str                 # Stable span_id for reference
    summary: str                # One-line from enrichment
    token_estimate: int         # For context budgeting
    
# Exposed via MCP as:
# - resources/list -> returns all tech_doc:// URIs with metadata
# - resources/read -> returns trimmed content + handle for follow-up
```

---

## 7. Execution Plan

### Phase 1 — Foundation: Naming + Diagnostics

**Goal:** Eliminate index collisions, make domain decisions observable during indexing.

**Deliverables:**

1. **Index naming rule** (deterministic):
```python
# tools/rag/index_naming.py
def resolve_index_name(base: str, repo: str, sharing: str, suffix: str = "") -> str:
    """Resolve final index name based on sharing strategy."""
    return base if sharing == "shared" else f"{base}_{repo}{suffix}"
```

2. **Structured diagnostic logs** (one line/file at index time):
```
domain=tech_docs override="DOCS/**" index="emb_tech_docs_llmc" extractor="TechDocsExtractor" chunks=24 ms=712
```

3. **CLI flag for decision trace:** `--show-domain-decisions`
```
INFO indexer: file=DOCS/API.md domain=tech_docs reason=path_override:DOCS/**
INFO indexer: file=src/main.py domain=code reason=extension:.py
INFO indexer: file=notes.txt domain=tech_docs reason=default_domain
```

**Definition of Done:**
- [ ] `resolve_index_name()` implemented and used; logs show `index=` resolved name
- [ ] `--show-domain-decisions` prints reasons for every file
- [ ] CI smoke job runs indexer with diagnostics enabled (artifact attached)

---

### Phase 2 — Parsing & MCP Surface

**Goal:** Deterministic chunking and host-friendly exposure with JSON schema.

**Deliverables:**

1. **AST parsing** (primary path):
   - `mistune` for Markdown (AST-based, fast)
   - `docutils` for RST (structured parse)
   - Keep ATX regex as fallback for malformed docs
   - **Benefit:** Determinism for headings, fenced code adjacency, lists/tables

2. **Anchor resolution:**
   - Slugify header anchors and include canonical targets in span metadata
   - MD/HTML: `{file_path}#{anchor}`
   - DITA: `{topic_id}`

3. **Acronym expansion TSV** (loaded at index time):
```tsv
# synonyms/tech_docs_acronyms.tsv
JWT	JSON Web Token
SSE	Server-Sent Events
GA4	Google Analytics 4
MCP	Model Context Protocol
RAG	Retrieval Augmented Generation
```

4. **MCP JSON Schema** (`resources/list` and `resources/read`):
```json
// mcp/resources/list.schema.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "TechDocResourceList",
  "type": "object",
  "properties": {
    "resources": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["uri","title","section_path","handle","summary","token_estimate","capabilities"],
        "properties": {
          "uri": { "type": "string" },
          "title": { "type": "string" },
          "section_path": { "type": "string" },
          "handle": { "type": "string" },
          "summary": { "type": "string" },
          "token_estimate": { "type": "integer" },
          "capabilities": { "type": "array", "items": { "type": "string" } }
        }
      }
    }
  },
  "additionalProperties": false
}
```

**Definition of Done:**
- [ ] AST parsers active; unit/property tests prove deterministic chunk boundaries
- [ ] Anchors present in span metadata; MD/RST/HTML anchors resolve and are unique
- [ ] Acronym TSV loaded; synonym/acronym expansion reflected in sparse scoring
- [ ] MCP JSON Schemas published with `token_estimate` & `capabilities`; hosts validate

---

### Phase 3 — Result Quality & Guardrails

**Goal:** Improve retrieval precision and enforce enrichment safety.

**Deliverables:**

1. **Reranker intent gating:**
   - Apply reranker only for `parameter_lookup` / `configuration` intents
   - Telemetry: `reranker_invocations_total`, `reranker_latency_ms`

2. **Field budgets + truncation flag:**
```python
MAX_SUMMARY_WORDS = 60
MAX_LIST_ITEMS = 10

def _truncate_words(text: str, max_words: int) -> tuple[str, bool]:
    """Truncate text with ellipsis, return (text, was_truncated)."""
    words = text.split()
    truncated = len(words) > max_words
    result = " ".join(words[:max_words]) + ("…" if truncated else "")
    return result, truncated
```

3. **Telemetry:** `enrichment_truncations_total` counter

**Definition of Done:**
- [ ] Reranker gated by intent; telemetry counts present
- [ ] Enrichment summaries and list fields respect budgets; truncations logged
- [ ] `truncated: true` flag set on affected enrichments

---

### Phase 4 — Graph Reliability

**Goal:** Make graph edges auditable and filterable.

**Deliverables:**

1. **Edge confidence + provenance:**
```python
@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: str
    score: float              # 0.0-1.0 confidence
    pattern_id: str | None    # Which regex pattern matched
    llm_trace_id: str | None  # If LLM-assisted
    model_name: str | None    # If LLM-assisted
    match_text: str           # Original matched text
```

**Definition of Done:**
- [ ] Graph edges include `score` and `provenance`
- [ ] LLM-assisted edges carry `llm_trace_id` and `model_name`
- [ ] Ops can threshold edges by confidence

---

### Phase 5 — CI Gates + Metrics

**Goal:** Prevent regressions, catch failures early.

**CI Gates (4 checks):**

1. **Config lint** — Validate `[repository]`, routes, `sharing`, resolved index names
2. **Extractor smoke** — Parse sample MD/RST/DITA; assert non-zero chunks deterministically
3. **Enrichment schema** — Validate JSON against Pydantic schema; reject unexpected keys
4. **Index connectivity** — Write/read test vectors; fail fast with summary artifact

**Metrics:**

1. **MRR (Mean Reciprocal Rank)** — Position of first relevant hit
2. **Recall@10** — Target ≥ 0.9 for parameter lookups

**Artifacts:**
- `tech_docs_eval.json` — All metrics for CI comparison
- `indexer_diagnostics.json` — On failure, shows exactly what broke

**Definition of Done:**
- [ ] All 4 CI gates green
- [ ] `tech_docs_eval.json` includes Recall@10 and MRR
- [ ] Failure artifacts attached on any gate failure

---

### Phase 6 — Extended Evaluation

**Goal:** Graded relevance for ranking quality.

**Deliverables:**

1. **nDCG@K** — Graded relevance (primary vs. secondary sections)
2. **Golden query sets** with labeled relevance judgments

**Definition of Done:**
- [ ] nDCG@K computed and reported for graded relevance sets
- [ ] Query sets versioned in `tests/eval/tech_docs_queries.json`

---

## 8. Test Plan

### 8.1 Unit Tests

- [ ] `test_tech_docs_extractor_markdown` - Heading-based chunking
- [ ] `test_tech_docs_extractor_dita` - DITA XML parsing (streaming)
- [ ] `test_section_path_building` - Correct hierarchy tracking
- [ ] `test_code_block_preservation` - Code kept with context
- [ ] `test_list_atomicity` - Lists not split
- [ ] `test_heading_regex_trailing_hashes` - `## Title ##` parsed correctly
- [ ] `test_setext_headings` - Underline-style headings (if supported)

### 8.2 Property-Based Tests

- [ ] `test_section_path_monotone` - Section path depth never decreases incorrectly within a document
- [ ] `test_no_context_loss` - Nested sections always include parent context
- [ ] `test_chunk_boundary_determinism` - Same input always produces same chunks

### 8.3 Large Document & Streaming Tests

- [ ] `test_dita_20mb_streaming` - DITA files ≥ 20 MB process within memory cap
- [ ] `test_index_time_budget` - Large docs complete within 60s
- [ ] `test_memory_ceiling` - No more than 500MB peak during indexing

### 8.4 Adjacency Retrieval Tests

- [ ] `test_neighbor_retrieval` - Given query hitting Step 7, assert Step 6/8 available via `neighbors`
- [ ] `test_large_chunk_adjacency` - Chunks exceeding token limit have collapsible neighbor context

### 8.5 Integration Tests

- [ ] `test_tech_docs_indexing` - Full pipeline on sample docs
- [ ] `test_tech_docs_search_quality` - Query relevance
- [ ] `test_domain_routing` - Correct slice_type assignment
- [ ] `test_hybrid_search_precision` - BM25+dense beats pure dense on parameter queries

### 8.6 Reranking Efficacy Tests

- [ ] `test_reranker_boost` - Top-K rerank improves relevance for "What does timeout do?" queries
- [ ] `test_reranker_vs_baseline` - Measure MRR improvement over dense-only

### 8.7 Schema Validation Tests

- [ ] `test_enrichment_schema_strict` - Enrichment JSON strictly matches Pydantic schema
- [ ] `test_injection_rejection` - Unexpected keys in LLM output are rejected
- [ ] `test_field_length_limits` - Oversized fields are truncated, not crashed

### 8.8 Validation on Real Docs

- [ ] Index LLMC's own `DOCS/` directory
- [ ] Query: "How do I configure enrichment chains?"
- [ ] Query: "What embedding models are available?"
- [ ] Query: "What does the timeout_seconds parameter do?" (parameter lookup)
- [ ] Compare retrieval quality to current baseline
- [ ] **Target:** Recall@10 ≥ 0.9 for tech-doc parameter lookups

---

## 9. Acceptance Criteria

- [ ] New config section `[repository]` with `domain` field
- [ ] `domain = "tech_docs"` uses heading-based chunking
- [ ] Markdown/RST/DITA files correctly parsed
- [ ] Section paths prepended to chunks for context
- [ ] Retrieval quality ≥ baseline on tech doc queries
- [ ] Backward compatible – existing repos work unchanged

---

## 10. Implementation Reference

> **See Section 7 (Execution Plan)** for detailed per-phase deliverables, code snippets, and Definition of Done criteria.

**Quick Phase Summary:**

| Phase | Focus | Key Deliverables |
|-------|-------|------------------|
| 1 | Foundation | Index naming, diagnostics, `--show-domain-decisions` |
| 2 | Parsing & MCP | AST parsers, anchors, acronyms, MCP schemas |
| 3 | Quality | Reranker gating, field budgets, truncation |
| 4 | Graph | Edge confidence, provenance, LLM trace IDs |
| 5 | CI & Metrics | 4 gates, Recall@10, MRR, eval artifacts |
| 6 | Evaluation | nDCG@K, golden query sets |

---

## 11. Operational Guardrails

### 11.1 Index Freshness

- Wire FS event watchers (`watchdog`) to re-index tech docs immediately on change
- Emit `llmc_tech_docs_reindex_lag_ms` metric for monitoring

### 11.2 Telemetry

Emit counters for observability:
- `chunks_per_doc` - Average chunks per document
- `avg_tokens_per_chunk` - Token budget utilization  
- `index_lag_ms` - Time from file change to searchable
- `query_intent` - Track query types: `api_parameter`, `procedure`, `warning`, `general`

### 11.3 Backward Compatibility

- Default `domain = "mixed"` for existing repos
- Code repos with incidental docs (README, DOCS/) work unchanged
- New behavior only activates with explicit `domain = "tech_docs"`

---

## 12. Deferred Items (Separate SDDs)

These are explicitly **out of scope** for this SDD:

| Item | Reason | Effort |
|------|--------|--------|
| **Cross-repo supersession** | Requires global deprecation registry + shared indexes | High |
| **Answer faithfulness** | R&D track (LLM-judge + rule-based span verification) | High |
| **MCP progress streaming** | Nice-to-have, adds complexity | Medium |

---

## 13. Future Work (Domain Expansion)

These extend LLMC to other document domains (post tech-docs success):

- **Legal Domain**: Clause regex grammar, SALI tags, Legal-BERT
- **Medical Domain**: SOAP parser, FHIR extraction, MedCPT, PHI redaction
- **Mixed Repos**: Per-file domain classification with ML
- **Domain-Specific Rerankers**: Cross-encoder fine-tuned for each domain

---

## 14. PR Template

Use this template for each phase PR:

```markdown
# PR: Domain RAG — Tech Docs (Phase X)

## Objectives
- Implements: [ ] Index naming rule | [ ] Diagnostics | [ ] AST parsing | [ ] MCP JSON Schema | [ ] Reranker gating | [ ] Field budgets | [ ] Edge provenance | [ ] CI gates | [ ] Metrics

## Code changes
- Index naming: `tools/rag/index_naming.py` (new) + usages in indexer
- Diagnostics: indexer emits single structured line per file
- Parsing: `tools/rag/extractors/tech_docs.py` (AST), `docutils` for RST
- Anchors: added to span metadata; resolver util
- Acronyms: `synonyms/tech_docs_acronyms.tsv` loader
- MCP schemas: `mcp/resources/*.schema.json`
- Enrichment budgets: `tools/rag/schemas/tech_docs_enrichment.py`
- Graph provenance: adds `score`, `pattern_id`, `llm_trace_id`

## Config updates
- `llmc.toml`: `[repository]`, `path_overrides`, `[embeddings.routes.tech_docs] sharing/index_name_suffix`
- `search.tech_docs`: `hybrid_enabled`, reranker block

## Tests
- Unit: AST parser, anchors, acronym loader
- Property: monotone section paths, deterministic chunking
- Integration: extractor smoke, enrichment schema guard
- Eval: Recall@10 + MRR; artifact `tech_docs_eval.json`

## CI
- Adds four gates: config lint, extractor smoke, enrichment schema validation, index connectivity

## Risks & mitigations
- Parser drift → property tests & AST primary path
- Index collisions → resolved naming rule & logs
- CI flakiness → fail-fast artifacts + verbose diagnostics
```

---

## 15. Decision Summary

| Suggestion | Verdict | Effort | Phase |
|------------|---------|--------|-------|
| Index naming rule in code | ✅ Yes | Low | 1 |
| Structured diagnostic logs | ✅ Yes | Low | 1 |
| AST parsing (mistune/docutils) | ✅ Yes | Medium | 2 |
| Anchor resolution | ✅ Yes | Low | 2 |
| Acronym expansion TSV | ✅ Yes | Low | 2 |
| MCP JSON Schema | ✅ Yes | Low | 2 |
| Reranker intent gating | ✅ Yes | Low | 3 |
| Field budgets + truncation flag | ✅ Yes | Low | 3 |
| Edge confidence + provenance | ✅ Yes | Low | 4 |
| CI gates (4 checks) | ✅ Yes | Medium | 5 |
| MRR metric | ✅ Yes | Low | 5 |
| nDCG@K | ⏸️ Defer | Medium | 6 |
| MCP progress streaming | ⏸️ Defer | Medium | Later |
| Cross-repo supersession | ⏸️ Defer | High | Separate SDD |
| Answer faithfulness | ⏸️ Defer | High | R&D |
