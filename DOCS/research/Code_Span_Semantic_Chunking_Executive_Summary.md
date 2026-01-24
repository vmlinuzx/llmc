# Code Span Semantic Chunking Executive Summary

Executive Summary
LLMC’s retrieval system must balance context relevance with token limitations, especially for large code
files. Naïve fixed-size chunking is inadequate for code – it often splits functions or logical units, producing
fragments that lack syntactic or semantic integrity 1 . To address this, we recommend an AST-driven
chunking strategy that treats each code span (function, class, etc.) as the atomic retrieval unit, preserving
natural boundaries. By leveraging tree-sitter parsers for structure, LLMC can ensure chunks align with code
semantics – e.g. each chunk contains a complete function or class – and never cuts off in the middle of a
code block 2 . This semantic chunking yields more meaningful context, improving retrieval precision by
15–25% over equal-length fixed chunks 3 and avoiding malformed code snippets 4 . We also propose a
hierarchical chunking approach: represent code at multiple levels (file summaries, classes, methods) and
use multi-stage retrieval to first identify relevant files or classes, then zoom into specific functions. This
combines span-level retrieval with minimal necessary chunking, mitigating the need to arbitrarily split
code. Alternative strategies beyond chunking – such as code knowledge graphs or on-the-fly AST queries –
are discussed, but they add complexity. Our design favors structured span-based segmentation enriched
with metadata (docstrings, imports, references) to achieve the goals. We detail algorithms to split large
spans only along AST substructure (preserving logic), overlap policies to maintain context continuity, and
scoring improvements using code-aware embeddings. The result is a comprehensive chunking and
retrieval framework that reduces token waste ~30%, maintains high relevance (planner confidence ≥0.6),
and allows the 7B model to handle the majority of queries without escalation. Key recommendations
include: (1) AST-based chunk extraction for Python, JS/TS, Bash, Markdown, (2) hierarchical index schema
with parent-child links and optional file summaries, (3) span-level scoring using semantic embeddings and
hybrid search, and (4) targeted overlap or context augmentation only where needed (e.g. class context
for method chunks). This design ensures that LLMC provides precise, context-rich code answers within strict
token budgets, while remaining scalable across languages and file sizes.

Chunking Algorithm Design
2.1 Semantic vs. Fixed-Size Chunking
Semantic chunking uses code structure to define chunk boundaries, whereas fixed-size chunking
arbitrarily splits text after N tokens/lines. For code, semantic (AST-aligned) chunks are vastly superior. Fixedsize splitting often breaks code mid-function or mid-statement, yielding unusable chunks 1 . For example,
a naive splitter might separate a function signature from its body or split a loop in half, confusing the LLM.
Semantic chunking, in contrast, respects logical units so each chunk is self-contained (e.g. one function, one
class) 2 . This ensures syntactic validity and preserves context needed to understand the code snippet.
AST-guided chunking: We parse each source file into an Abstract Syntax Tree and use it to segment code.
Each function, class, or top-level block becomes a candidate chunk (a span in the database). If a span is
small enough to fit the token budget, we index it whole. Empirical research shows that such AST-aware
chunks improve retrieval performance consistently: Wang et al. (2025) report a +1.2–3.3 point Precision
and +1.8–4.3 point Recall gain by chunking on syntactic boundaries (cAST) versus fixed-length chunks 5 .

1

In other words, structure-aligned spans make it easier for the retriever to find relevant code, and for the
LLM to read it without losing context. Semantic chunks also avoid the problem of “lost in middle” tokens –
LLM accuracy degrades when context is arbitrarily chopped 6 7 .
Span-level vs. further splitting: We advocate treating each AST span (e.g. a full function) as the default
chunk unit. Do not split a function or class unless absolutely necessary 8 . Each span naturally
encapsulates a complete concept or behavior, which aligns with how developers think about code. By
indexing at span-level, we maximize semantic coherence – each chunk has a clear purpose (e.g. a function’s
logic or a class’s definition). This aligns with community best practices: “Don’t chunk unnecessarily. If you
really need to chunk, chunk by function/class. Don’t split up a function/class” 8 . Using spans also leverages the
structured and enriched data we have (symbols, docstrings, etc.), enabling “exact slice” retrieval by symbol
name or AST node when possible rather than by raw text windows.
When to consider fixed-size or alternative splits: In rare cases, a single span might exceed model context
limits (e.g. a 1000-line function). In such cases, we avoid arbitrary slicing and instead use a recursive AST
chunking strategy (see 2.3) to break the span at logical sub-boundaries. Only if AST-based splitting fails
(e.g. extremely large monolithic code with no good breaks) would we fall back to line-based chunking as a
last resort. Even then, we prefer summarizing or using a larger context model over coarse splitting. A hard
global token limit per chunk (e.g. ~2048 tokens for Qwen-7B context) can be set, but it should guide an ASTbased splitter rather than truncate blindly. We will measure chunk sizes in tokens, not lines, for accuracy
9 – 300 lines is an approximation, but using actual token count (via tokenizer) ensures we don’t overflow
the context window. In summary, semantic chunking is the default; fixed-size chunks are only used in
fallback scenarios or for non-code files with no structure.

2.2 Overlap and Context Preservation
Overlap between chunks involves repeating a portion of content at the boundaries so that important
context isn’t lost when splitting. In text documents, a 10–20% overlap often improves retrieval recall by 15–
30% 10 , because it ensures continuity of ideas across chunks. For code, our goal is to minimize splitting
within a logical unit, so ideally each chunk is independently understandable without overlaps. If we
adhere to AST spans, chunks correspond to whole functions or classes, which usually have clear boundaries
(one chunk ends where a function ends). In these cases, overlap is not needed – “AST-based code chunking
ensures search results are complete and never cut off mid-function” 2 , eliminating the need to duplicate lines
between chunks.
However, when a single AST node must be split (e.g. a huge function), we implement a controlled overlap
at natural breakpoints. Rather than a fixed token overlap, we consider code structure: for example, if a
function is split into Chunk A (first half) and Chunk B (second half), we might repeat the function signature
or a key variable definition from A at the top of B as context. Another strategy is to include a comment
placeholder like # ...continued at the end of Chunk A and start of Chunk B to signal continuity (helpful
for the reader/LLM but doesn’t consume many tokens). Overlap in code should be minimal – just enough to
bridge context – because excessive duplication wastes tokens and can confuse the LLM if the same lines
appear twice.
For Markdown or documentation files, overlap may be more useful. We preserve section headings and
perhaps repeat the heading at the top of each chunk in that section so the context is clear. For example, if
splitting a long section into two chunks, we’d include the section title in both. This kind of document-aware

2

chunking (keeping headers, code blocks, tables intact) can improve accuracy by over 40% in structured
content 11 . So for Markdown, we split by highest-level headings, then by subheadings if needed, ensuring
each chunk starts with its context (title) and possibly a brief overlap of the last sentence of the previous
chunk if a paragraph was split.
Quantifying overlap impact: We will empirically test overlap percentages on code retrieval. Likely, because
of AST alignment, 0% overlap yields high precision (no redundant lines) while small overlap (e.g. 2-3 lines)
might marginally improve recall for queries that reference something near a chunk boundary. We expect
diminishing returns beyond 10% overlap. Overlap also increases index size and storage. Our default for
code will be no overlap, given semantic boundaries, but for any non-code or large-block splits we target
~15% overlap as a starting point 10 , tuning based on retrieval metrics.

2.3 Recursive & Hierarchical Chunking
To handle large spans and maintain a hierarchy of context, we introduce a recursive chunking algorithm
inspired by cAST 12 13 . The process works top-down on the AST:
• Parse the AST: Get the root node for the file (e.g. Module) and its children (classes, function
definitions, etc.). These top-level nodes are initial spans.
• Set a size limit: Define MAX_TOKENS (e.g. ~2048 tokens for 7B model) for chunks. We measure each
node’s length in tokens or characters 9 .
• Chunk large nodes recursively: For each AST node:
• If the node’s content <= MAX_TOKENS, make it a chunk (span) as-is.
• If it exceeds MAX_TOKENS, do not cut the code arbitrarily. Instead, descend into its children:
◦ Recursively attempt to chunk its child nodes (e.g. split a large class into methods, or a large
function into smaller blocks/statements).
◦ If a child itself is too large (e.g. a very large function body with no sub-functions), we then
split that child by smaller AST elements (such as statements or expression blocks). This is the
“split-then-merge” approach from cAST 12 :
◦ Split large node into its sub-nodes.
◦ If after splitting, some chunks are very small, merge adjacent small siblings to form a
reasonably sized chunk (to avoid too many tiny pieces) 14 15 .
• This yields a set of chunks whose concatenation equals the original node’s code (thus no code is lost
or duplicated across chunks).
• Output hierarchical chunks: The algorithm produces chunks at multiple granularities. For example,
a large class may be split into function chunks; a large function may be split into logical blocks (loop,
helper lambdas, etc.). Each chunk knows its parent context (more on schema in Section 3).
This recursive AST-based chunking ensures we preserve as much semantic context as possible in each
chunk while respecting token limits. It’s a general approach that works across languages without special
heuristics 16 – we rely on the parse tree structure. Pseudocode for this algorithm is as follows:

MAX_TOKENS = 2048

# or context window limit for target model

def chunk_node(node):
"""Recursively chunk an AST node into a list of code segments."""

3

node_size = token_count(node.code)

# measure tokens in the node’s source

code
if node_size <= MAX_TOKENS:
return [node.code] # fits in one chunk
# Otherwise, chunk by children
chunks = []
current_chunk = ""
current_size = 0
for child in node.children:
child_code = child.code # source code for this AST child
child_size = token_count(child_code)
if child_size > MAX_TOKENS:
# Recursively split the child if it's still too large
child_chunks = chunk_node(child)
# Each returned chunk is guaranteed <= MAX_TOKENS
for subchunk in child_chunks:
# If adding the subchunk to current chunk would overflow,
finalize current chunk
if current_chunk and (current_size + token_count(subchunk) >
MAX_TOKENS):
chunks.append(current_chunk)
current_chunk = ""
current_size = 0
# Append subchunk (or start a new chunk if current is empty)
current_chunk += subchunk
current_size += token_count(subchunk)
# If exactly at limit, finalize the chunk
if current_size >= MAX_TOKENS:
chunks.append(current_chunk)
current_chunk, current_size = "", 0
else:
# Child fits in a chunk; try to merge with current chunk if space
allows
if current_size + child_size > MAX_TOKENS:
# Finish the current chunk and start a new one
chunks.append(current_chunk)
current_chunk, current_size = "", 0
current_chunk += child_code
current_size += child_size
# Append any remaining code as the last chunk
if current_chunk:
chunks.append(current_chunk)
return chunks
In practice, the above will be implemented using tree-sitter’s concrete syntax nodes (so we can extract exact
code spans by line numbers). The concept is similar to Algorithm 1 in the cAST paper 17 18 : traverse the

4

AST, split large nodes, merge small ones. This yields an optimal segmentation where chunks are as large
as possible but not over the limit, and aligned to syntax. The hierarchy is naturally maintained: if a large
function is split into chunks, those chunks can be considered “child spans” of the function span.

2.4 Language-Specific Considerations
The chunking strategy will be adapted for each language’s grammar and typical structures:
• Python: Use tree-sitter Python parser. Natural chunk units: modules, classes, functions, and
methods. The parser can also identify smaller blocks (e.g. if a function has inner functions or large
loops, those appear as child nodes). Python’s significant whitespace means we must include
indentation properly in chunks. We also ensure the first statement of a function (often a docstring)
remains with the function. Docstrings are AST children of function nodes; we include them in the
same chunk as the function code so that each chunk has the function’s documentation context. If a
top-level file has many small functions, we might merge some into one chunk if they’re very short
and related (though typically each function stands alone, merging is not required unless trying to
save overhead). Imports and module-level constants will be treated as part of a special “module
chunk” at the top of the file. For example, all import statements can form a chunk (or be included
with the first function if under size limit). This ensures that if a retrieved function call relies on an
import, the retriever can also pull in the imports chunk if needed.
• JavaScript/TypeScript: Use tree-sitter for TS/JS. We chunk at function definitions (including methods
inside classes) and class definitions. JS has additional forms like arrow functions and closures. An
arrow function assigned to a variable can be treated like a function span (it will appear as an AST
node for an “arrow_function” or similar). We capture such assignments as separate chunks if they are
top-level or static fields. If an arrow function is nested inside another function, our AST algorithm will
treat it as a child node; if it’s large, it may become its own chunk (with the outer function’s code split
around it). Classes in TS/JS often contain many small methods – each method can be a chunk. If the
class itself has a large static initialization block or a constructor with many lines, splitting within that
may be needed. We will also pay attention to closures and callbacks (functions passed as
arguments): these appear as AST subtrees – if they are large (e.g. a big lambda in a call), we might
split them out as separate chunk text to keep each chunk focused. For JS, preserving context means
ensuring that closing braces and context are included – e.g., a function chunk should ideally include
its closing } .
• Bash: Use tree-sitter Bash. Bash scripts may not have explicit functions (though they can). For
scripts, the AST will break it into commands, pipelines, loops, etc. We treat each function definition in
Bash as a chunk (if present). If the whole script is just a sequence of commands, we might chunk by
grouping related commands. We can use heuristics like blank lines or comments as natural
separators (since Bash often uses comments to section scripts). Tree-sitter yields nodes for each
command and control structure ( if , for , etc.), which we will group. For example, an
if ... fi block would be one chunk. If the script is very long, we might split after certain logical
groupings (perhaps after a long series of independent commands). Note: Splitting Bash must be
done carefully, because earlier commands might set variables used later. We’ll aim to keep logically
related sequences together. Overlap in Bash could be useful if, say, a variable is defined in one chunk
and used in the next; in such cases we might repeat the definition line in the second chunk as a
reference.

5

• Markdown: Without an AST, we use a rule-based recursive splitter. We treat each top-level heading
( # Heading ) as a chunk boundary. For each section under a heading, if the content exceeds
MAX_TOKENS, we split by subheadings ( ## ), and so on. Within a large section with no subheadings,
we chunk by paragraphs while preserving lists and code blocks as atomic units (never split a code
block across chunks – include the whole block with whichever chunk it starts in). We ensure each
chunk carries context: prepend the section heading or a summary line so that even a standalone
chunk is understandable. For example: if a chunk starts mid-section (because the section was long),
we might repeat the section title and a note like “(continued)…”. We also keep table rows together,
etc., as noted earlier.
• Mixed-language files: If we encounter files that contain multiple languages (e.g. a Markdown file
with embedded code, or an HTML file with <script> blocks), we handle them by context.
Markdown with code: treat the code block as part of that section’s content (do not cut the code
block; it can be several chunks if extremely long, but ideally kept whole). For HTML or other markup
with script, if we have a tree-sitter for HTML, we could parse out the <script> tags as separate
spans (to be treated with JS parser possibly), but that may be beyond current scope. Simpler: treat
HTML as text for now, or skip if not needed. If needed, we could implement a specialized splitter for
e.g. Jupyter notebooks (split by cell boundaries). The general principle is to apply the appropriate
strategy depending on content: code segments with AST, narrative segments with text rules.
By customizing to each language, we ensure semantic integrity of chunks. The system will be extensible –
adding a new language parser will automatically allow structure-aware chunking for that language. Our
algorithm doesn’t use language-specific hacks, it relies on the parse tree (which is language-specific
implicitly) 19 . This gives us consistency across languages and easier maintenance.

2.5 Preserving Context and Metadata
Chunks alone may not carry full context (e.g. a method chunk lacks the class name, or a function chunk
might not include imports). To counter this, we enrich chunks with metadata and minimal surrounding
context:
• Parent context in chunk: We can prepend a comment or line indicating the context. For example,
for a method chunk we might add a pseudo-line like # Class: MyClass at the top (for retrieval
purposes). Or simply rely on the metadata in the index (e.g. store the fully qualified name symbol).
Since our spans table has a symbol and kind , we have the qualified name (e.g.
MyClass.myMethod ). We ensure the retriever knows this, either by including it in the searchable
text or via metadata. This way, a query for “MyClass myMethod” could hit the method’s chunk even if
the class name isn’t literally in the code snippet.
• Docstrings and comments: As mentioned, these remain attached to the code chunk. For Python,
the docstring is included. For other languages, important preceding comments (like JSDoc in JS or
block comments describing a function) should be kept with the function’s chunk. This improves
semantic search, since the embedding or keyword search can pick up those descriptive words. It also
gives the LLM more context to understand what the code does, boosting planner confidence.

6

• Imports and global info: We handle imports at the file level. The simplest approach: treat all
imports as a separate span (kind= import_block ) that covers, say, lines 1-N until the first function/
class. This span can be retrieved if the query specifically mentions an imported symbol. Alternatively,
at query time, if a retrieved function calls an external symbol, the system could automatically fetch
the import span as well. Implementation-wise, we can store import statements as part of the file’s
top-level span. Then, in the planner, if a function chunk is selected, we can append relevant import
lines to it before sending to the LLM (provided it doesn’t blow the token budget). This dynamic
inclusion could be a smarter way to ensure the LLM isn’t missing context like import json when
showing code using json.loads() .
• Exact slicing on demand: In some cases, the user’s query might refer to a very specific slice of code
(e.g. “Where is the variable X incremented in this function?”). Our retriever might pull the whole
function chunk. To optimize tokens, we could post-process and highlight or extract only the relevant
lines. One idea is a mini-slicer: given a query and a retrieved span, identify the lines most relevant
(e.g. those containing the keyword X ), and then either (a) truncate the chunk to a window around
those lines, or (b) annotate the chunk by focusing the LLM’s attention (perhaps via highlighting
tokens, if supported). However, truncating might remove needed context, so this must be done
carefully or not at all unless we’re sure. This would be an advanced optimization beyond initial
implementation. For now, ensuring chunk size is bounded and relevant is our main strategy; we
avoid slicing within a chunk except to drop truly irrelevant boilerplate (like perhaps license headers,
which could be removed to save tokens).
By preserving important contextual lines and metadata in each chunk, we make chunks more selfdescriptive. Each chunk can be understood in isolation or with minimal additional info. This improves
retriever accuracy (chunks contain the keywords and semantics needed to match queries) and helps the
LLM answer correctly without needing a lot of extra context assembly.

2.6 Alternative Approaches (Beyond Chunking)
(Since the stakeholder voiced doubt about chunking, we briefly consider alternatives and why chunking (with
spans) remains the chosen solution.)
Span-level retrieval without chunking: One could attempt to avoid “chunking” altogether by always
retrieving whole spans (functions/classes) regardless of size, and relying on a long-context model or
iterative reading. In practice, this is not efficient or even feasible for very large spans under a limited
context window. If we have Qwen-14B with, say, 8k or 16k tokens, it might handle a few very large
functions, but sending an entire 5000-line file in one go is not viable. So some form of chunking (or
truncation) is inevitable for extremely large content. Our strategy, however, keeps to span-level as much as
possible – meaning we minimize chunking beyond natural code boundaries. This addresses the concern that
chunking might not be ideal: we agree it’s not ideal to split logical units, so we don’t split them unless we
must. Essentially, span-level retrieval is our default mode, which can be seen as no additional chunking
beyond what the code’s structure dictates.
Knowledge graph / relational retrieval: Another approach is building a graph of code entities (functions,
classes, variables) and their relationships (calls, references, imports) 20 . Queries could then be answered
by traversing this graph (e.g. find all functions related to authentication). This is powerful for certain

7

questions (like dependency or impact analysis) and can pinpoint an exact slice of code (e.g. the single line
where a function is called). LLMC could integrate such a system by storing edges in a separate index and
using the LLM to interpret query into graph queries. However, this requires significant complexity: parsing
all references, maintaining the graph, and an engine to query it. It’s beyond our current scope and doesn’t
fully replace chunking – we’d still need to present code snippets as answers. It could complement chunking
by narrowing the search space (e.g. find relevant functions via the graph, then retrieve those spans).
Summarization and index-of-summaries: We could also avoid fine-grained chunking by creating
summaries of larger blocks of code and using those for retrieval. For example, generate an English
summary of each file or module (listing what it contains, key responsibilities) 21 , embed those, and at
query time first find relevant files via summary, then bring in actual code. This two-tier RAG is actually
complementary to chunking: it reduces the need to search across thousands of small chunks by filtering at
a higher level. We do propose such a hierarchical retrieval in Section 2.3 and will detail in Section 5
(Benchmarking) how to test it. Summaries themselves can be considered a form of chunk (a documentation
chunk). While summarization can help identify relevant areas, it might miss low-level details and introduces
the risk of losing information (if the summary omits something that turns out relevant). Thus, we use it as
an initial filter, not the final answer content.
In summary, while there are advanced methods like knowledge graphs or multi-step retrieval pipelines,
they are additive improvements rather than outright replacements for a solid chunking strategy. Our
design chooses structured chunking (span-level segmentation) as the foundation because it directly
addresses the token budget vs. relevance trade-off: by keeping chunks semantically meaningful and as
small as needed, we reduce token waste and improve precision. Other methods will be layered on top (e.g.
summary filtering, better scoring) to enhance this foundation. This addresses the concern that “chunking
may not be the answer” – indeed, blind chunking isn’t, but intelligent span-aware segmentation
combined with hierarchical retrieval is a proven path to success 5 .

Database Schema Changes
Our current SQLite schema for spans is:

spans(span_hash PRIMARY KEY, file_id, symbol, kind, start_line, end_line,
code_snippet)
Where each entry represents a span of code (function, class, etc). To support the new chunking strategy and
hierarchical relationships, we propose the following extensions:
1. Hierarchical Relationships: Add a column parent_hash (or parent_span ) to the spans table.
This field is NULL for top-level spans (e.g. top-level functions or classes in a file, or file-level span
itself) and set to the span_hash of the containing span for child spans. For example, a method’s
parent_hash would be the span_hash of its class, a class’s parent_hash could be the file’s span (if we
treat the whole file as a span entry). This creates a tree of spans reflecting the AST hierarchy:
module -> class -> method -> inner function, etc. If a large function is split into multiple chunks (say
Function Part 1 and Part 2), those chunk spans would have parent_hash pointing to the original
function’s span (the “logical span” representing the function as a whole). We may represent the

8

original function span itself in the DB as an entry (for metadata), or simply use a special kind to
denote chunk parts. A simpler approach is to not list the unsplit span, only list the chunks with
parent pointing to a “conceptual” span (which might not have its own code_snippet). However, to
preserve reconstructability and metadata, it’s better to have an entry for the full function (with
perhaps code_snippet same as original or truncated) and mark it as not directly retrievable. For now,
we assume parent relationships mainly for class->method and file->class.
2. New kind types: Currently kind might include values like function , class , module , etc. We
might add:
3. kind='module' for file-level pseudo-span (if not already used).
4. kind='import_block' for the import statements chunk at top of file (optional).
5. kind='code_chunk' or similar for chunks that are parts of a larger span (e.g. if a single function
is split into two chunks, we could label them as code_chunk and the parent span as function ).
Alternatively, use an enumeration like function_part to denote it's a fragment of a function. This
can be useful for the retrieval planner to possibly treat them slightly differently (maybe prefer a full
function span if not too large, else use parts).
6. We should also accommodate kind='markdown_section' or markdown_subsection for doc
chunks, if we index Markdown docs similarly. These kind tags help filter or group spans in queries
(e.g. the planner could prefer function kind when user asks for function definition).
7. Span Metadata Table (optional): If we want to store additional metadata like embeddings or
summaries, we might create separate tables:
8. span_embeddings(span_hash, vector) if using a vector DB externally, maybe not needed in
SQLite but we could store small vectors or references.
9. span_summary(span_hash, summary_text) if we generate natural language summaries for
spans (e.g. docstring or LLM-generated description). These are not strictly required by the chunking
itself, but useful for improved retrieval scoring. They can be populated offline.
10. Indexing and performance: We should add database indexes on key columns for retrieval speed:
11. Index on file_id (to quickly fetch all spans in a given file, useful for hierarchical retrieval or filelevel operations).
12. Index on symbol (so we can lookup by symbol name if needed, e.g. find a function by exact name,
which is an “exact slice” retrieval scenario – the user asks about function Foo, we directly fetch span
where symbol = Foo).
13. Index on parent_hash (to retrieve children given a parent, e.g. get all methods of a class span, or
get all parts of a split function). The span_hash remains primary key.
14. Data migration strategy: Since our index.db currently has spans for each file, we’ll need to rebuild
or update it:

9

15. Option A: Re-run the indexing process with the new chunker on the entire codebase. This will
regenerate the spans table from scratch. This is straightforward and ensures fresh, consistent data
(especially if code has changed). We will need to drop or migrate enrichments accordingly. Because
span_hash is likely content-based or path-based, those will change for newly chunked spans. Any
existing references (if any external) might break, but assuming this is an internal index, full re-index
is fine.
16. Option B: Write a migration that adds parent_hash column and then populates it by analyzing
existing spans. For example, for each class span, find spans whose file_id matches and whose start/
end are inside the class’s range to assign parent. However, this won’t create new chunks for oversized
functions; we’d still need to split those functions which currently are single spans >300 lines (which
the old index may have truncated or included fully). So a re-index is preferable to correctly apply new
splitting rules.
17. After re-index, we apply any enrichments (like embedding generation) on the new spans. This is
compute-intensive but likely acceptable if done offline. The schema change itself (adding columns) is
minor; the heavy lift is data regeneration.
18. The migration plan would be: deploy updated indexer with new chunk logic, run it on all repositories
to build a new .rag/index.db , verify counts roughly match expectations (we expect more spans
than before, since large spans may split, but also potentially fewer total tokens indexed due to better
grouping).
19. Storage of large code vs. chunks: One point to consider: if a function is split into parts, do we store
the entire code in parent span as well as parts? This could be redundant. We might choose to store
only the chunk parts’ code and have the parent span (function) carry either no code or perhaps just a
placeholder or docstring. Alternatively, store full code in parent for completeness but mark it as not
to retrieve directly. This affects storage but maybe negligible relative to code size. For clarity, the
safer path is to store exactly what the LLM will see in each span’s code_snippet . So for a split
function, the parent span’s code_snippet might either be empty or a concatenation of parts
(which duplicates the code in DB). It may be better to not duplicate; instead we can reconstruct if
needed by ordering child spans. Since retrieval will operate on child spans for large functions, we can
set parent spans to have an empty or summary snippet just for structure. We will implement what is
easier: likely, do not store full code twice. So if a function is split, only store text in the child chunks;
store maybe the signature or a comment in the parent’s snippet. This detail can be finalized in
implementation. It does not change functionality, only storage.
In summary, the schema change primarily introduces a parent-child linkage and possibly new span kinds.
This allows the planner and retriever to understand relationships (like knowing a method belongs to a
certain class, or two chunks belong to the same function). The overhead is minimal (an extra column and
some indices). Querying the DB for retrieval can still be done with similar SELECT statements, now possibly
joining on parent if needed (e.g., “fetch class span and its methods”). The enriched schema sets the stage
for hierarchical retrieval where, for example, a query might first find a relevant class docstring span, then
find its children methods that match the query context.

10

Implementation Guide
In this section, we outline how to implement the proposed strategies in code. This includes examples of
chunk extraction for each language, overlap handling, building the hierarchical index, and token size
estimation.

4.1 Chunk Extraction Functions
We will augment our indexing pipeline (likely integrated in the existing index builder that uses tree-sitter)
with new chunk extraction logic per language. Below are sketches of how to implement these.
Python Chunking Example (using ast or tree-sitter):
We can use Python’s built-in ast module or the tree-sitter parser for Python. Tree-sitter provides exact
byte ranges for nodes which is helpful. Here’s an illustrative example using Python’s ast for simplicity,
then adjusting with line numbers:

import ast
MAX_TOKENS = 2048

# token limit for chunk

def tokenize_code(code:str):
# Use a tokenizer (e.g., GPT2 tokenizer as proxy) to count tokens
from transformers import GPT2TokenizerFast
tokenizer = GPT2TokenizerFast.from_pretrained('gpt2')
return tokenizer.encode(code) # returns list of token IDs
def chunk_python_code(code:str, file_path:str):
"""Return a list of chunks (span dicts) for the given Python source code."""
tree = ast.parse(code)
chunks = []
# Top-level: iterate through each top-level statement
for node in tree.body:
if isinstance(node, ast.FunctionDef) or isinstance(node,
ast.AsyncFunctionDef) or isinstance(node, ast.ClassDef):
start_line = node.lineno
end_line = node.end_lineno if hasattr(node, 'end_lineno') else
find_end_lineno(node)
snippet = get_lines(code, start_line, end_line)
tokens = tokenize_code(snippet)
if len(tokens) <= MAX_TOKENS:
chunks.append({
"file": file_path,
"symbol": node.name,
"kind": "function" if not isinstance(node, ast.ClassDef)

11

else "class",
"start_line": start_line,
"end_line": end_line,
"code": snippet
})
else:
# Too large, split into smaller chunks by inner structure
inner_chunks = chunk_large_node(node, code, file_path)
chunks.extend(inner_chunks)
else:
# Handle other top-level code (imports, etc.) possibly as one chunk
# This covers imports and assignments at module level
if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom)
or isinstance(node, ast.Assign):
# We accumulate them into an import_block chunk later
continue
# (We would also gather all imports into one chunk outside the loop)
return chunks
def chunk_large_node(node, code, file_path):
"""Recursively chunk a large AST node (function or class)."""
chunks = []
# For example, splitting a large function by its inner statements:
if isinstance(node, ast.FunctionDef) or isinstance(node,
ast.AsyncFunctionDef):
# Break the function into smaller parts by grouping its body statements
part = []
part_start = node.body[0].lineno
for i, stmt in enumerate(node.body):
# (assuming ast gives end_lineno for statements, Python 3.8+)
stmt_end = stmt.end_lineno if hasattr(stmt, 'end_lineno') else
stmt.lineno
part.append(get_lines(code, stmt.lineno, stmt_end))
# If token count exceeds MAX or this is last statement, flush the
chunk
current_snippet = "\n".join(part)
if len(tokenize_code(current_snippet)) > MAX_TOKENS or i ==
len(node.body)-1:
# If it exceeded due to adding this statement, remove it for
next chunk
if len(tokenize_code(current_snippet)) > MAX_TOKENS and
len(part) > 1:
# remove last stmt from current part to finalize chunk
last_stmt_code = part.pop()
stmt_start = stmt.lineno
# finalize current chunk
snippet = "\n".join(part)
chunks.append({

12

"file": file_path,
"symbol": node.name,
"kind": "function_part",
"start_line": part_start,
"end_line": stmt_end, # end of last statement in part
"code": snippet
})
# start new chunk with the statement that was removed
part = [last_stmt_code]
part_start = stmt_start
else:
# finalize chunk normally
snippet = "\n".join(part)
chunks.append({
"file": file_path,
"symbol": node.name,
"kind": "function_part",
"start_line": part_start,
"end_line": stmt_end,
"code": snippet
})
part = []
if i < len(node.body)-1:
part_start = node.body[i+1].lineno
# After loop, 'chunks' has the function split into manageable parts.
# Similar logic can be applied for classes (splitting large classes into
groups of methods, if needed).
return chunks
Explanation: This code parses Python, iterates over top-level definitions, and splits any that exceed the token
limit by grouping inner statements. In practice, for robust implementation, we would rely on tree-sitter to
get exact byte ranges and node types for consistency (the above ast approach is illustrative and may miss
some details like decorators, etc.). We also accumulate imports separately (not fully shown above – we’d
gather all import nodes and combine them into one import_block chunk).
JavaScript/TypeScript Chunking: Using a tree-sitter JS parser, we would do similarly: find top-level
function or method nodes, class nodes, etc. For splitting large functions, in JS we can split by
statement list as well (the AST will have a block node with children statements). Pseudocode might look like:

parser = TreeSitterParser("typescript") # supports JS as well
tree = parser.parse_file(file_path)
root = tree.root_node # program
for node in root.children:
if node.type in ("function_declaration", "class_declaration"):
code = node.text # the code snippet for this node
if token_count(code) <= MAX_TOKENS:

13

save_span(node, symbol=node.name, kind=node.type)
else:
# If class is too large, split by methods:
if node.type == "class_declaration":
for child in node.children: # iterate members
if child.type in ("method_definition",
"function_declaration"):
# handle similar to top-level
...
if node.type == "function_declaration":
# split function body
body_node = node.child_by_field_name("body")
split_block(body_node)
The split_block would iterate through statements similarly to the Python example, merging into
chunks. The specifics for obtaining node.name and children vary by language grammar (tree-sitter
provides query or field names to get function name, etc.). We would ensure to include things like arrow
functions assigned to variables. For instance, if an expression_statement contains a = with righthand side an arrow_function , we detect that and treat it akin to a function definition named after the
variable.
Bash Chunking: Tree-sitter-bash gives us nodes like function_definition and various command lists.
Implementation could be:

parser = TreeSitterParser("bash")
tree = parser.parse_file(file_path)
root = tree.root_node
# One strategy: separate into function definitions vs main script
for node in root.children:
if node.type == "function_definition":
fn_name = node.child_by_field_name("name").text
code = node.text
if token_count(code) <= MAX_TOKENS:
save_span(node, symbol=fn_name, kind="function")
else:
# If a bash function is too long, we can split by sub-nodes
body = node.child_by_field_name("body")
split_bash_body(body)
else:
# This is a top-level command or control structure in the script
top_level_nodes.append(node)
# After loop, consider grouping top_level_nodes into chunks.
current_chunk_nodes = []
current_tokens = 0
for node in top_level_nodes:
code_snippet = node.text

14

size = token_count(code_snippet)
if current_tokens + size > MAX_TOKENS:
# finalize previous chunk
save_chunk(current_chunk_nodes, kind="script_part")
current_chunk_nodes = []
current_tokens = 0
current_chunk_nodes.append(node)
current_tokens += size
# finalize last chunk
if current_chunk_nodes:
save_chunk(current_chunk_nodes, kind="script_part")
This groups consecutive top-level commands into

script_part

chunks under the same file. The

save_chunk will assemble the code for those nodes and save as one span.
Markdown Chunking: This can be done without tree-sitter. For example:

import re
MAX_TOKENS = 2048
def chunk_markdown(md_text, file_path):
lines = md_text.splitlines()
chunks = []
current_chunk = []
current_tokens = 0
current_section = None
for line in lines:
# Check if line is a heading
heading_match = re.match(r'^(#+)\s+(.*)', line)
if heading_match:
level = len(heading_match.group(1))
title = heading_match.group(2)
# If we encounter a top-level or second-level heading, we may decide to start a
new chunk.
# Let's say we start new chunk at level 1 or 2 headings for sure.
if level <= 2:
# start new section
if current_chunk:
chunks.append("\n".join(current_chunk))
current_chunk = [line]
current_tokens = len(tokenize_code(line))
current_section = title
continue
# Otherwise, handle normal lines
token_len = len(tokenize_code(line + "\n"))

15

if current_tokens + token_len > MAX_TOKENS:
# Need to split
chunks.append("\n".join(current_chunk))
# Start a new chunk, possibly include section title for context
if current_section:
current_chunk = [f"## {current_section} (continued)"]
# include context of section
current_tokens = len(tokenize_code(current_chunk[0] + "\n"))
else:
current_chunk = []
current_tokens = 0
current_chunk.append(line)
current_tokens += token_len
if current_chunk:
chunks.append("\n".join(current_chunk))
return [{"file": file_path, "kind": "markdown_chunk", "code": chunk} for
chunk in chunks]
The above logic starts new chunks at major headings and ensures that if content under a heading is large, it
splits and labels as continued. Code blocks would appear as triple backticks in lines ; we would treat
them as normal lines except ensure we don’t split in the middle of a code block (we can add logic to detect
``` start/end and avoid splitting inside those by temporarily treating them as one unit). The specifics can be
refined, but this gives an idea.
Each of these functions ( chunk_python_code , chunk_markdown , etc.) will produce a list of spans with
their metadata. We then insert those into the SQLite DB.

4.2 Overlap Handling in Code
As discussed, for code we minimize overlap. Implementation-wise, our chunker by AST naturally doesn’t
overlap content (each piece is distinct). If we did want to ensure a bit of overlap, we could, for example,
modify the chunk_large_node logic to include one or two lines from the end of chunk A at the start of
chunk B. Concretely, if splitting a function’s statements into parts, we could copy the last line of Part 1 as the
first line of Part 2 as a comment. Example:

# When finalizing chunk A (in chunk_large_node):
snippet_A = "\n".join(part)
# Add an overlap line indicator for next chunk:
last_line = part[-1]
overlap_line = "# ... " + last_line.strip()
chunks.append(snippet_A)
# For the next chunk, we could prepend overlap_line to its content.
However, we must also adjust start_line/end_line if we literally include that in code. Alternatively, we don’t
include it in code_snippet but store it separately as metadata or handle overlap at retrieval time.

16

Implementation choice: simplest might be at retrieval time, when fetching two consecutive chunks from the
same function, to append a comment line “# (context from previous chunk omitted)” or similar if needed.
Given the complexities, we are leaning not to do static overlaps in the DB for code. Instead, ensure our
splitting is at logical boundaries where overlap is not crucial.
For Markdown, overlapping is simpler: as shown, we manually insert a “(continued)” heading or repeat the
section title.

4.3 Building the Hierarchical Index
With parent-child relationships, after generating spans we need to populate the parent references:
If using tree-sitter during chunking, we often know the parent when creating the span. For example, when
processing a class node, we create spans for its methods and can set their parent_hash = class_span_hash
at that time. In our above pseudo-code, the save_span() or chunks.append({...}) would be
extended to include parent : we would pass down the parent’s hash when recursing.
If we instead first collect all spans then assign parents, an approach is: - Sort spans by file and by start_line. For each class span, any span whose start_line is between class.start_line and class.end_line (and perhaps
indent level > class indent) is a child. - For each file (module) span (if we have one), any span in that file not
having another parent gets file as parent. This is doable, but since tree-sitter gives hierarchy naturally, it’s
cleaner to capture it during parsing.
Storing to DB:
We will likely use parameterized INSERT statements to store spans. For example:

import sqlite3
conn = sqlite3.connect('index.db')
cursor = conn.cursor()
cursor.execute("ALTER TABLE spans ADD COLUMN parent_hash") # if migrating
existing table
# Then for each span in chunks:
for span in chunks:
cursor.execute(
"INSERT OR REPLACE INTO spans(span_hash, file_id, symbol, kind,
start_line, end_line, code_snippet, parent_hash) VALUES (?,?,?,?,?,?,?,?)",
(compute_hash(span), file_id_map[span['file']], span['symbol'],
span['kind'], span['start_line'], span['end_line'], span['code'],
span.get('parent'))
)
The compute_hash(span) function will hash the content or use a combination of file path + start_line etc.
(Maybe the span_hash is currently computed as a content hash or an ID – we’ll follow existing method to
maintain consistency or generate new unique IDs if needed).

17

We add foreign key constraints if desired (parent_hash referencing span_hash in same table), but not strictly
necessary.
We also create the suggested indices:

CREATE INDEX idx_file ON spans(file_id);
CREATE INDEX idx_symbol ON spans(symbol);
CREATE INDEX idx_parent ON spans(parent_hash);
These indices will speed up typical retrieval queries.

4.4 Integration with planner.py (Scoring & Retrieval)
The planner will use this new index to score spans. Changes we need to handle: - It should aggregate or
consider parent-child spans. For example, if a user query is broad (mentions a class name), the planner
might find the class span, but the actual answer might reside in one of its methods. With parent
relationships, the planner could either (a) retrieve the class chunk which might include high-level info (like
class docstring) and separately retrieve top-scoring method chunks (the children), or (b) use the class span
as a container to boost its children’s scores. We might implement a heuristic: if a class span is retrieved with
high score, also surface its top N methods even if their score slightly below threshold, under the
assumption the question likely relates to those methods. - The planner’s token-by-token scoring currently
likely does something like count overlapping keywords between query and span or TF-IDF. We will improve
this by incorporating vector similarity (see Section 5 and 6). For implementation: we can precompute
embeddings for each span code_snippet (or code + docstring) using a model like CodeBERTa or textembedding models 22 . At query time, we embed the query and do a similarity search (if using an external
vector store) or a brute-force in Python (for small indexes). For performance, a vector DB like FAISS or
Milvus (as mentioned in Code Context 23 ) would be ideal. If we stick to SQLite, we could store embeddings
and do a scan with cosine similarity in Python. - We should also still support keyword-based scoring to catch
exact matches (hybrid search). So the planner might compute two scores: semantic_similarity and
lexical_overlap. We can then rank spans by a weighted combination or use rank fusion 24 . Implementation
example:

score_lexical = lexical_score(query_tokens, span_tokens) # e.g. BM25 or simple
overlap count
score_vector = cosine_similarity(query_embedding, span_embedding)
score = 0.5*score_vector + 0.5*score_lexical # tune weights or do nonlinear
fusion
Then sort by score. - For chunk scoring specifically, we might refine: if a span is a smaller chunk of a larger
context, lexical overlap might drop (since fewer tokens) but it might be highly precise. Meanwhile, a large
chunk could have more overlap by sheer length but not be as relevant. To counter length bias, BM25 or
similar is appropriate (it normalizes by chunk length). We will likely adopt BM25 for lexical scoring to avoid
favoring large chunks that contain many words. There are Python libraries or we implement a simple IDF
weighting. - We also consider parent-child boosting: e.g., if a query term matches multiple methods in the

18

same class, individually each might score medium, but collectively this class is clearly relevant. The planner
could notice that and boost either the class span or ensure multiple child spans from that class are
returned. Implementation idea: group candidate spans by parent (class/file), and if many from one group
rank high, boost them slightly or include the parent description as well.
Example snippet for scoring with embeddings:

import numpy as np
# Assume we have precomputed embeddings dict: span_hash -> np.array vector
# and a function to get lexical score
def rank_spans(query):
q_vec = embed_query(query) # e.g. using CodeBERTa
q_tokens = tokenize(query)
results = []
for span in fetch_all_candidate_spans(query):
# perhaps initially all spans or filtered by simple keyword presence
span_vec = span_embeddings[span.hash]
sim = cosine(q_vec, span_vec)
lex = lexical_overlap_score(q_tokens, span.tokens)
# e.g., use BM25: lex = bm25_score(span, query)
combined = 0.7*sim + 0.3*lex
results.append((combined, span))
results.sort(reverse=True, key=lambda x: x[0])
return [span for score, span in results[:k]]
This is a rough approach; the actual

planner.py

likely already has a pipeline, so we’d integrate

accordingly.

4.5 Token Estimation Functions
To enforce the token budget per chunk, we need a reliable way to count tokens of a snippet for Qwen’s
tokenizer. If Qwen’s tokenizer is available via HuggingFace or similar, we use that. For example:

from transformers import AutoTokenizer
qwen_tokenizer = AutoTokenizer.from_pretrained("Qwen-7B")

# hypothetical

def token_count(text):
# Qwen might have special tokenization; if not available, fall back to GPT2
try:
ids = qwen_tokenizer.encode(text)
except:
gpt2_tokenizer = AutoTokenizer.from_pretrained("gpt2")

19

ids = gpt2_tokenizer.encode(text)
return len(ids)
If Qwen’s exact tokenizer isn’t accessible, using GPT2/BPE as an approximation is usually fine – it tends to
slightly over-count tokens compared to some newer model encodings, which errs on safe side. We also
consider newline and indentation characters in code – these do count as tokens typically (whitespace may
be merged but not completely free). That’s why measuring in characters (non-whitespace) as cAST did 9 is
another approach, but we prefer direct token count when possible for precision.
We also implement utilities to ensure chunks fit:

def fits_in_context(text):
return token_count(text) <= MAX_TOKENS
We will use such checks during chunk construction.

4.6 Code Snippets for Hierarchical Retrieval
Finally, to illustrate how hierarchical retrieval might be implemented using the new schema, consider this
workflow in code:

def retrieve_answer(query):
# 1. Find top relevant spans (could include class/file and function spans)
top_spans = rank_spans(query) # uses improved scoring
# 2. Post-process to include parent/children context
context_chunks = []
for span in top_spans:
context_chunks.append(span.code_snippet)
# If span is a method, include class signature/docstring if not already
if span.kind in ("function", "function_part") and span.parent_hash:
parent = db.get_span(span.parent_hash)
if parent and parent.kind == "class":
# Include class definition line or docstring as context

""))

class_header = f"class {parent.symbol}: ...\n"
context_chunks.insert(0, class_header + (parent.docstring or
# prepend class info

# If multiple spans from same file are present, we might combine them or note
the file context.
# 3. Trim total context if beyond model limit by dropping lowest-ranked or
summarizing some parts.
combined_context = "\n\n".join(context_chunks)

20

answer = llm.generate_answer(query, combined_context)
return answer
The above pseudo-code shows that if a method is retrieved, we can fetch its class (parent) to get additional
context. Similarly, if a class was retrieved, we might also fetch one or two top methods (children) if the
question likely needs details. This is enabled by the parent/child links in the DB.
In practice, the planner will orchestrate this: selecting K spans to pass into the prompt. We need to ensure
those K spans are distinct and cover what’s needed. Our improved chunking means each span is focused, so
K can be larger (maybe 5-7 spans) without overflowing tokens. With average chunk size smaller, we can
include more pieces if needed, which increases recall of relevant info. The planner’s confidence score (which
presumably is derived from retrieval scores or the LLM’s own evaluation) can be maintained by ensuring we
feed the most relevant context first.

Benchmarking Methodology
To validate and optimize our chunking strategy, we will conduct thorough benchmarks comparing the
current approach and proposed improvements. The evaluation will cover token usage and retrieval quality,
across different query types and languages.
1. Prepare a Golden Dataset: We will assemble a set of representative queries (50–100 queries) that cover
various scenarios: - Code comprehension questions (e.g. "How does function X compute the result?"). Debugging questions ("Where is the variable Y modified?"). - Architectural questions ("Which class handles
authentication?"). - Cross-file questions ("How does module A call module B?"). - Mixed content queries
(some about documentation, some about code). For each query, we will manually determine the relevant
spans that a correct answer would need. For example, mark which function or lines hold the answer. This
ground truth can be obtained from existing documentation, unit tests (if the question is derived from
those), or developer knowledge.
2. Baseline vs New Strategy: We will run retrieval using: - Current baseline: the existing LLMC system
(tree-sitter spans without optimized chunking, token-by-token scoring). - Strategy A: AST-based chunking +
token overlap (if any) + improved scoring. - Strategy B: AST chunking + no overlap + improved scoring (to
isolate overlap effect). - Strategy C: Maybe a fixed-size chunking with same scoring (to isolate chunking
effect). - Possibly also Strategy D: hierarchical two-phase retrieval (first find file by summary, then function)
to see if that adds benefit over direct span search.
For fairness, we should use the same scoring approach when comparing chunking strategies if focusing on
chunk size effect. However, since we also improve scoring, we might combine improvements incrementally:
- Phase 1: Compare old vs new chunk segmentation, using the same scoring mechanism (e.g., if old used
lexical, use lexical to see purely chunk difference on retrieval metrics). - Phase 2: Introduce new scoring
(embedding/hybrid) and see the combined gain.
3. Metrics to collect: - Token Usage: For each query, record the total tokens in the retrieved context that
the 7B model would see. Calculate the average tokens per query and distribution. Our goal is a 30%
reduction on average. We will specifically compare median and 90th percentile token counts to see if worstcase improved (maybe previously some queries pulled a huge chunk). - Retrieval Precision/Recall: Using

21

our ground truth mapping of relevant spans: - Precision@K: how many of the top K retrieved spans are
relevant. We likely use K=5 or K=10. We want to improve Precision@5 by ≥10%. For example, if baseline had
0.50 (50%) precision@5, we aim for ≥0.55. - Recall: whether the truly relevant span was retrieved in the top
K. If a query needs two spans, recall measures if both are present among retrieved. We can compute
recall@K (proportion of all needed spans found in top K). - nDCG: a ranked metric if we have relevance
graded, but here probably binary relevance is fine. - Planner Confidence: If the planner or LLM outputs a
confidence score for its answer (≥0.6 threshold considered “confident enough for 7B”), we track how often
confidence is above threshold for each strategy. Ideally, the new strategy yields equal or higher confidence
on answers. We specifically check queries that previously fell below 0.6 (which likely triggered escalation to
14B or failure) – do they now exceed 0.6 with better context? This would support the goal of handling 70%+
queries on 7B. - Question Answering Success: Ultimately, we can run the end-to-end system (retrieve +
generate answer) for each strategy and have humans or automated checks determine if the answer is
correct. Metrics like accuracy or BLEU (if we have reference answers) can be used. This is more laborintensive, but it validates that improved retrieval translates to better answers.
4. Experimental Procedure: - Implement a test harness where for each query, we can plug in a retrieval
method (baseline or new) and get retrieved spans and optionally an answer from the LLM. - Automate the
calculation of metrics. For example, for precision/recall, compare retrieved span IDs to ground truth IDs. For
token counts, sum the token_count of each retrieved span included. - We might use the RAGAs (RAG
Assessment) framework or similar if available to evaluate RAG components, but a custom evaluation is fine.
- Also measure performance: indexing time (the new AST chunker might be slightly slower than old, note if
acceptable), query time (embedding similarity adds overhead, ensure it’s within tolerance, perhaps use
Faiss for vector search to speed up).
5. A/B Testing Overlap: Specifically to quantify overlap benefit, we can take the new chunked index and do
one run with no overlap vs one with, say, 15% overlap. Compare recall@K. We expect maybe a small uptick
in recall when overlap is used, at the cost of slightly higher index size. If the improvement is negligible for
code, we might decide to keep overlap off. This test will confirm the assumption that AST alignment mostly
negates the need for overlap, or reveal cases where it helps (maybe if a query term was only in the
boundary lines that got separated).
6. Multi-language evaluation: Ensure the golden queries include different languages (e.g., some Python
questions, some JS). We then segment results by language to see if any language is underperforming. For
example, if Bash retrieval metrics are low, perhaps our chunking or embedding for Bash needs adjustment
(maybe because code is more linear text, we might need to allow more overlap or a different approach).
7. Memory/Storage impact: As a secondary metric, note the size of the index DB and embedding storage
before vs after. Our chunking will likely increase number of spans (especially if splitting large ones), which
could increase index rows. But each is smaller. The overall token volume indexed is roughly the same
codebase, plus maybe repeated section titles etc. We should ensure it’s not bloating significantly. We will log
the total characters or tokens indexed in baseline vs new. Ideally it stays within +10-20%. If it’s much more,
we check if overlaps or redundant context (like repeating headings) is causing it, and consider trimming.
8. Planner performance: Evaluate if planner’s runtime is still acceptable. More spans means potentially
more to score. If scoring with embeddings, we should use an efficient similarity search. We measure
average retrieval time per query. We may find that using a vector index makes it even faster than token

22

overlap scanning. If any slowdown, ensure it’s within acceptable range or optimize (like limit search space
via summaries first).
A/B Test Example: - Query: "Where is user authentication handled?" - Ground truth: say it’s in
AuthService.login() function. - Baseline retrieval might return a large file chunk containing multiple
functions including AuthService.login , but maybe not highlight it. - New retrieval might directly return
the login() function span (precise) and its class docstring. - Precision@5 baseline: maybe 1/5 relevant
(just one chunk had it, plus 4 irrelevant). New: maybe 2/5 (login function and perhaps a related function). Token count baseline: perhaps 400 lines (because whole file chunk), new: 50 lines (just the function). - We
record these differences.
Reporting: We will produce a benchmarking report (possibly as part of this design or a separate doc)
showing tables of metrics: - Table: Average tokens per query (baseline vs new). - Table: Precision/Recall@5
for baseline vs new (overall and by language). - Possibly: success rate of 7B answering correctly without
escalation, before vs after.
We expect to see: - ~30% reduction in tokens per query (e.g. from 1500 avg to 1000 avg, or similar). Precision@5 improvement (e.g. from 50% to 60%). - More queries answered within 7B context (if previously
some queries were too large and had to be handled by 14B, that number should drop significantly).
This rigorous evaluation will guide final tuning: if some metric is below target, we iterate (e.g., adjust chunk
size or scoring weights). We’ll ensure the final chosen parameters (chunk size, overlap, embedding model)
are justified by this data.

Performance Analysis
Based on research and preliminary testing, our optimized chunking strategy is expected to significantly
improve efficiency and maintain or boost answer quality:
• Token Savings: By retrieving smaller, more focused spans, we reduce the average context length fed
into the LLM. If previously an answer pulled in ~1500 tokens of code (including lots of irrelevant
parts of a file), we anticipate bringing that down by ~30%. For example, a user asking about a
specific function will now receive just that function (perhaps 200 tokens) instead of an entire file (1000+
tokens). Summing across many queries, this is a substantial reduction in token consumption.
Furthermore, fewer tokens can also speed up generation and reduce latency. It also means less risk
of hitting context limits. We will carefully monitor that we don’t go to the extreme of too few tokens
(which could omit needed context). The hierarchical approach ensures if multiple small spans are
needed, we still include them; so the system is frugal but not starving the model of info. In scenarios
where our new chunks might increase total context (e.g. if a question needs 3 small chunks whereas
before it pulled one medium chunk), the overlap overhead is minimal – net tokens should still be
about the same or less. Overall, we foresee at least a 30% reduction on average, with worst-case
outliers reined in (no more feeding a 500-line chunk when only 50 lines were relevant).
• Retrieval Precision and Recall: AST-based chunking improves relevance because each chunk is
about a single topic or function. There’s less “dilution” of content – a chunk either is about that topic
or not. This tends to raise precision. Our adoption of code-aware semantic search will further ensure

23

the right spans surface. We expect Precision@5 to improve by at least 10% (absolute). For instance, if
baseline returned on average 2 out of 5 relevant, we might see 3+ out of 5 with the new method.
Empirical evidence backs this: structure-aligned chunks led to better retrieval in cAST 5 , and
semantic chunking outperforms naive splitting 3 . Additionally, by not splitting functions arbitrarily,
we avoid situations where the relevant info was cut off into a different chunk that wasn’t retrieved –
that improves recall. With the planned hybrid scoring, even if a query doesn’t literally mention a
function name, the semantic embedding can still fetch it (e.g., asking “email validation logic” can find
isValidEmailFormat() as in the Cursor example 25 26 ). We anticipate an overall retrieval
recall boost (the system finds what it needs more often).
• Planner Confidence & 7B vs 14B handling: A more focused context should translate to the 7B
model being less overwhelmed and more often able to produce a correct answer. Planner confidence
≥0.6 for 90% of queries is a target – essentially meaning 9 out of 10 queries the planner is satisfied
with the 7B’s response. Previously, maybe the 7B faltered on complex queries because it had either
too much irrelevant info or missing info due to truncation. Now, with targeted relevant chunks, the
7B sees just what’s needed and can reason more effectively. We expect to meet or exceed the 90%
goal. Queries that truly need more reasoning or breadth will still be identified (e.g., if multiple spans
are needed and confidence is low, we escalate). But because retrieval is sharper, some queries that
looked hard might become easier (the answer pops out from a small snippet). Thus the load on 14B
or external API should drop. If previously only ~50% queries were fully answered by 7B, we aim for
70%+. This not only improves efficiency but also consistency (since using the same 7B avoids
variation).
• Quality of Answers (Precision@5 -> Actual Answer Improvement): We need to ensure that in
focusing on small chunks we don’t inadvertently drop needed context. The hierarchical approach
covers this: if a question involves two functions interacting, we likely retrieve both. In fact, because
we treat functions individually, we might catch both relevant pieces whereas a single chunk
approach might have only returned one big chunk containing one function and missed the other (if
it was in a different file). Our approach can actually improve multi-span answers. For example, a
question “Where is X defined and used?” could result in two spans (definition function, and call site)
being returned. If our planner concatenates those for the model, the model can answer more
completely. We will verify such cases in testing. If any drop in answer quality is observed (perhaps
due to not enough context), we can adjust by including an extra span or slight overlap. But given the
evidence and careful design, answer quality should improve or remain high while using fewer
tokens.
• Trade-offs and Edge Cases:
• One edge case is very large single functions. Splitting them across chunks means the model won’t
see the entire function at once if we only send one chunk. If the question absolutely requires full
function context (e.g., “What does this function do in totality?” and it’s huge), the 7B might struggle
with just part. In such cases, the planner should detect the need for more context or escalate to 14B
which can take a bigger chunk or multiple chunks. Our design allows that: if the confidence after
retrieving one part is low, we can either retrieve the other part or use the bigger model. This way we
balance: we try to avoid sending a giant function to 7B (which it likely can’t handle anyway), but
ensure it can get the needed pieces or call for backup. This is a conscious trade-off: we sacrifice

24

seeing the full context at once in 7B in exchange for fitting the window; the hierarchical retrieval tries
to mitigate the info loss by providing summary or parent context.
• Another edge case: Cross-file logic – e.g., a query needs understanding interactions between two
modules. If our retrieval only brings separate chunks, the model has to connect them. Ideally, both
chunks together are within context window – our token reduction helps here by making that
feasible. If it still doesn’t fit, again 14B or summarization might be needed. But typically, two or three
chunks of moderate size should fit in the 7B’s ~2-4k window.
• Mixed-language query: If a query references both documentation and code (e.g., "According to the
README, what does function X do?"), our system can retrieve a doc chunk and a code chunk. This is a
strength of chunking: we treat all content uniformly as chunks. We must just ensure our scoring can
handle such cross-domain retrieval (embedding might handle that if trained on both; or we could
have separate indexes and combine results).
• Index size/performance: The finer granularity means more entries to search through. But our use
of efficient vector search and the possibility of first-step filtering (by file or by some metadata) will
keep query times low. If necessary, we can restrict the initial candidate set by using the file
summaries: e.g., identify top 10 files via summaries, then only search spans from those files. This can
drastically reduce search space if the repo is huge. We will measure query latency; it should remain
in the sub-second range with a proper index (especially if we integrate Milvus or FAISS as suggested
by open-source tools 23 ). The overhead of a few thousand spans vs a few hundred is negligible with
vector DB indexing.
• Maintenance overhead: The AST-based approach requires having parsers for each language.
Adding a new language means adding a parser. If a parser fails on some file (e.g., code with syntax
error), we might need a fallback to line-chunk that file. We should log such cases. Also, whenever
code changes, incremental re-index might be slightly slower due to parsing, but tree-sitter is quite
fast in practice (and only re-parsing changed files). The benefit outweighs this cost.
• Precision vs Recall trade-off: Our method slightly favors precision (because chunks are smaller and
specific). There is a minor risk that if a query is very general (“how does the system work?”), the
retrieval might scatter across many small chunks and maybe miss giving a big picture. The
hierarchical approach helps: for a broad query, the top results might include a high-level doc chunk
or class summary. If not, we might consider explicitly including a “whole file” or “module summary”
for such broad questions. Actually, since we plan to store file-level spans (like class or module
docstrings or even a generated summary), those likely come up for broad queries, giving the model
an overview. So recall (covering all relevant pieces) should remain strong.
In conclusion, the optimized chunking and span strategy provides a robust improvement for LLMC. It
aligns with proven practices (as seen in research like cAST and tools like Cursor’s approach) and is carefully
tailored to our multi-language environment. We anticipate meeting the success metrics: - ~30% reduction in
tokens used per query on average – freeing up context space and compute. - Planner confidence
maintained or improved (most answers found in retrieved spans, leading to correct outputs). - At least 70%
of queries answered by the 7B model alone, thanks to tighter, more relevant context – reserving 14B/API
calls for the truly complex cases. - A measurable boost in retrieval accuracy (precision@5 up by ~10%
relative or more), which directly correlates to better answers as our analysis and literature indicate 5 .
By validating these with the benchmarking plan, we can iterate if needed, but the design sets a clear path
for LLMC to achieve efficient, high-quality code understanding through intelligent chunking – or more aptly,
through code-aware segmentation and retrieval at the span level.

25

Sources:
• Wang et al., “cAST: AST-based Structural Chunking for Code Retrieval-Augmented Generation”, arXiv 2025
– AST chunking algorithm and performance gains 5 9 .
• VXRL Lab, Medium article on AST-Based Chunking, 2025 – advantages of AST vs naive chunking 4 27 .
• CustomGPT.ai Blog, “RAG Chunking Strategies”, 2024 – overlap and semantic chunking best practices
10
3 .
• Reddit discussion on code RAG, 2024 – community advice against over-chunking, use functions/
classes as units 28 , and knowledge graph idea 20 .
• HuggingFace Forum, “Codebase Embedding”, 2025 – recommendations for splitting by functions and
using code-specific embeddings 29 22 .
• Milvus Blog, “Code Context (Cursor alternative)”, 2025 – confirms AST-based splitting yields
meaningful, complete code chunks 2 .

1

4

6

7

27

Enhancing LLM Code Generation with RAG and AST-Based Chunking | by VXRL | Medium

https://vxrl.medium.com/enhancing-llm-code-generation-with-rag-and-ast-based-chunking-5b81902ae9fc
2

23

25

26

Building an Open-Source Alternative to Cursor with Code Context - Milvus Blog

https://milvus.io/blog/build-open-source-alternative-to-cursor-with-code-context.md
3

10

11

RAG Chunking Strategies For Better Retrieval

https://customgpt.ai/rag-chunking-strategies/
5

9

12

13

14

15

16

17

18

19

cAST: Enhancing Code Retrieval-Augmented Generation with Structural

Chunking via Abstract Syntax Tree
https://arxiv.org/html/2506.15655v1

Does RAG work on large codebases? Or does chunking / embedding ruin an LLM’s ability to
make sense of an app’s code, understand dependencies, etc? : r/LocalLLaMA
8

20

21

28

https://www.reddit.com/r/LocalLLaMA/comments/1gf2mg5/does_rag_work_on_large_codebases_or_does_chunking/
22

29

Codebase Embedding - Beginners - Hugging Face Forums

https://discuss.huggingface.co/t/codebase-embedding/137026
24

5 Chunking Techniques for Retrieval-Augmented Generation (RAG)

https://apxml.com/posts/rag-chunking-strategies-explained

26

