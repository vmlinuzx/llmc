# RFC: Fuzzy Knowledge Codification (The "Doc-Object Model")

**Status:** Draft / Research Idea
**Date:** 2026-01-26
**Topic:** Transforming unstructured documentation into structured, code-like objects for RLM.

---

## 1. The Problem
RLM (Recursive Language Model) excels at navigating code because code has "physics": strict syntax, explicit imports, and deterministic references. It can "pull the thread" of an import statement to find exactly where logic goes.

Documentation (PDFs, Markdown, Wikis) lacks this physics. It is "fuzzy" knowledge. Searching it requires probabilistic vector search (RAG), which is good for "finding" but bad for "reasoning".

**Gap:** You cannot currently "refactor" documentation against code, or "unit test" your knowledge base, because RLM treats docs as opaque text blobs rather than structured objects.

## 2. The Solution: "Doc-Object Model" (DOM)
We propose abstracting fuzzy knowledge into three rigid primitives that RLM understands natively:

1.  **Headers = Classes**: A generic H1/H2 becomes a container/namespace.
2.  **Links = Imports**: A hyperlink in a doc is functionally identical to `from x import y`. It is a directed edge to another node.
3.  **Content = Docstrings**: The prose itself is metadata attached to the node.

### Conceptual Workflow
Instead of RLM searching for "deployment guide", it would interact with a **Virtual Python Library** representing the documentation.

```python
import knowledge.docs.deployment as deploy

# RLM inspects the "object"
print(deploy.AWS_Configuration.__doc__)
# Output: "Timeout defaults to 60s..."
```

The system (LLMC) intercepts this import. It performs a Graph RAG lookup, finds relevant Markdown headers, "compiles" them into a Python class structure, and hands it to the agent.

## 3. Strategic Value: Knowledge Unit Testing
This abstraction unlocks **Drift Detection** and **Knowledge Engineering**:

1.  RLM reads the code: `function connect_db(timeout=30)`
2.  RLM reads the "Doc Object": `class DatabaseDocs: """Timeout defaults to 60s"""`
3.  RLM compares them:
    > *"Runtime Error: Documentation Object `DatabaseDocs` asserts timeout=60, but Code Object `connect_db` implements timeout=30. Logic Mismatch."*

## 4. Research Plan
1.  **Parsing Strategy**: Can we reliably map Markdown/PDF structure to a pseudo-AST?
2.  **Virtual Import System**: How to hook into RLM's sandbox to dynamically generate these "doc modules"?
3.  **Graph Alignment**: aligning the Doc Graph (headers/links) with the Code Graph (classes/imports).

---

*This RFC was generated from a conversation on the evolution of LLMC from "Compressor" to "Navigator".*
