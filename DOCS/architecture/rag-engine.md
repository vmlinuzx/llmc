# RAG Engine

The RAG (Retrieval-Augmented Generation) Engine is the core subsystem of LLMC responsible for indexing code and serving semantic queries.

## Components

### 1. Indexer (`llmc.rag.indexer`)
The indexer is responsible for:
- Scanning the repository for files.
- Parsing files into "Spans" (functions, classes, blocks).
- Managing the state of the index (incremental updates).

### 2. Database (`llmc.rag.database`)
LLMC uses a SQLite database (`index_v2.db`) to store:
- **Files Table**: Path, hash, last modified time.
- **Spans Table**: Code content, start/end lines, parent file.
- **Embeddings Table**: Vector representations for each span.
- **Enrichment Table**: LLM-generated metadata (summary, keywords).

### 3. Embedding Manager (`llmc.rag.embedding_manager`)
Computes vector embeddings for spans using local or remote models. It supports:
- **Profiles**: Configurable model settings (e.g., dimension, provider).
- **Batching**: Efficient processing of multiple spans.

### 4. Search (`llmc.rag.search`)
Performs semantic search over the index.
- **Vector Search**: Finds spans with similar embeddings to the query.
- **Hybrid Search**: Combines vector search with keyword matching (optional).
- **Reranking**: Re-orders results based on relevance scores.

## Indexing Process

1.  **Discovery**: `pathspec` is used to respect `.gitignore` and find relevant files.
2.  **Hashing**: Files are hashed to detect changes.
3.  **Parsing**: AST parsers (via `tree-sitter` or regex) split files into atomic spans.
4.  **Vectorization**: New or changed spans are sent to the embedding model.
5.  **Enrichment**: (Async) Spans are queued for LLM enrichment to add semantic metadata.
