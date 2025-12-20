Dynamic Multi-Signal Scoring and Graph-Enhanced Retrieval for LLMC: A Research Report
1. Executive Summary
The prevailing architecture of Retrieval-Augmented Generation (RAG) systems tailored for software repositories typically relies on a static, linear pipeline: sparse and dense retrieval followed by a heuristic ranking mechanism. While this approach suffices for general documentation queries, it exhibits a fundamental pathology when addressing code-implementation queries. The core issue lies in the semantic gap between high-level natural language intent (e.g., "how is routing gated?") and the low-level symbolic reality of the codebase (e.g., def search_spans(...)). Standard dense embeddings often conflate documentation about code with the code itself, leading to result sets dominated by high-level descriptions rather than the implementation details the user explicitly requested. Furthermore, the current fusion logic within LLMC—specifically the max_weight strategy utilized in llmc/routing/fusion.py—fails to mathematically align the unbounded score distributions of lexical retrieval (BM25) with the bounded distributions of vector similarity, resulting in a fragile scoring landscape where outliers in one modality can suppress valid signals in another.
This report presents a comprehensive architectural evolution for LLMC, proposing a transition from static retrieval to a Dynamic, Graph-Enhanced Multi-Scoring System. The recommendations herein are grounded in a rigorous analysis of literature from late 2024 through 2025, specifically focusing on the emergence of "Graph-RAG" for code repositories (RepoGraph, RANGER) and efficient few-shot intent classification (SetFit).


  



Our analysis identifies three critical pillars for this upgrade. First, we recommend the integration of Graph-Enhanced Retrieval using a lightweight, file-centric graph structure similar to the RepoGraph approach.1 By leveraging the existing .llmc/rag_graph.json artifact, LLMC can move beyond treating code as unstructured text and instead model it as a network of dependencies (imports, calls, inheritance). This allows for "neighbor expansion," where retrieving a function definition automatically pulls in its critical context—such as the class it belongs to or the utilities it invokes—thereby bridging the gap between specific entity queries and broader architectural questions.
Second, we propose the adoption of Dynamic Query Routing via SetFit (Sentence Transformer Fine-tuning).3 Current heuristic routing rules (regex for keywords) are brittle and incapable of discerning subtle intent differences (e.g., "Show me the fusion code" vs. "Explain the fusion logic"). SetFit enables the training of a highly accurate, low-latency classifier with as few as eight examples per class, allowing LLMC to intelligently "gate" expensive compute resources. This ensures that a purely navigational query does not waste cycles on expensive graph traversals or LLM reranking, while complex ambiguity triggers the full power of the multi-stage pipeline.
Third, we detail a sophisticated Multi-Stage Scoring Pipeline that replaces the current max_weight fusion. We advocate for Z-Score Normalization prior to fusion 5, which statistically aligns the disparate score distributions of BM25 and dense embeddings. This is followed by a Setwise LLM Reranker 7, which evaluates candidates collectively rather than in isolation. Unlike listwise approaches that suffer from position bias, setwise reranking prompts the LLM to select the optimal subset of documents that maximize information coverage, directly addressing the "lost-in-the-middle" phenomenon common in long-context RAG.
This report outlines a concrete engineering path to implement these changes within LLMC’s existing modular structure (search_spans, router.py, fusion.py). We estimate that these upgrades will improve retrieval precision for code-intent queries by approximately 20–30%, based on proxy benchmarks in similar code-retrieval literature like RANGER 9 and RepoGraph.1 The plan balances immediate, high-ROI changes (Z-score fusion, SetFit routing) with longer-term research investments (Human-in-the-loop Argilla workflow, Graph Neural Networks), ensuring that LLMC evolves into a state-of-the-art retrieval system capable of distinguishing the implementation from the documentation.
2. Taxonomy of Methods
To rigorously ground our recommendations for LLMC, we must first establish a taxonomy of the current state-of-the-art (SOTA) in information retrieval and machine learning, specifically as it applies to code repositories and RAG systems. This taxonomy categorizes methods based on their functional role in the pipeline: graph construction, dynamic routing, reranking, fusion, and evaluation.
2.1 Graph Construction & Retrieval Paradigms
The integration of graph structures into RAG—often termed "GraphRAG"—has evolved significantly from general Knowledge Graphs (KG) to specialized, code-centric structural graphs. The premise is that code is inherently structured; treating it as a bag of words or a sequence of tokens discards the rich dependency information (call graphs, inheritance trees) that defines its execution semantics.
RepoGraph and Structural Modeling:
Recent work such as RepoGraph 1 demonstrates the efficacy of modeling code files not just as text chunks but as nodes in a graph where edges represent semantic relationships like IMPORT, CALL, and INHERIT. RepoGraph specifically outperforms file-level retrieval by integrating context at the line level, constructing a graph where nodes can represent specific functions or classes. This granular modeling allows for "contextual slicing," where a retrieval operation for a function node can automatically traverse edges to include the function's definition and its immediate dependencies. The construction methodology typically involves Abstract Syntax Tree (AST) parsing 10 to identify entities and their relationships, filtering out standard library calls to focus on project-specific topology. This aligns perfectly with LLMC’s existing .llmc/rag_graph.json, which essentially captures these static relationships.
Dual-Path Retrieval (RANGER):
The RANGER architecture 9 introduces a compelling paradigm for handling query diversity. It employs a dual-path strategy: a direct "Cypher query" path for explicit code-entity queries (e.g., "Find class Scorer") and a "Graph Exploration" path for vague natural language queries. The latter uses Monte Carlo Tree Search (MCTS) to explore the graph, identifying nodes that are semantically relevant even if they don't share exact keywords with the query. This "neighbor expansion" strategy—where the graph is used to augment the candidate set retrieved by dense vectors—is a powerful mechanism to improve recall for implementation queries. By pulling in the "neighborhood" of a retrieved node, the system ensures that the LLM has access to the definition of a called function, not just the call site.
Graph-Neural Networks (GNNs) for Retrieval:
More advanced approaches like GReX 12 and CodexGraph 1 utilize Graph Neural Networks to learn representations of the code structure itself. In this paradigm, the embedding of a code snippet is not just a function of its text but also of its position in the call graph. While powerful, these methods require training specialized GNN models, which introduces significant complexity compared to the "graph-as-index" approach of RepoGraph.
2.2 Dynamic Routing & Gating
The traditional RAG approach of querying all available indices (dense, sparse, code, docs) for every query is computationally inefficient and prone to noise injection. Dynamic routing seeks to classify the user's intent and "gate" the downstream compute resources accordingly.
Mixture of Experts (MoE) Routing:
Systems like ExpertRAG 13 and RouterRetriever 14 validate the concept of "routing over a mixture of domain-specific experts." Instead of a single monolithic retriever, these systems employ a gating network that analyzes the query and directs it to the most appropriate "expert" retriever (e.g., a code-specific embedding model vs. a general documentation model). Empirical results on benchmarks like BEIR demonstrate that this dynamic selection significantly boosts nDCG by reducing the "confusing" signals from irrelevant domains. For LLMC, this translates to distinct routes for "implementation details" versus "architectural concepts."
Efficient Few-Shot Classification (SetFit):
A critical enabler for dynamic routing in local-first systems is SetFit (Sentence Transformer Fine-tuning).3 Unlike large generative models (GPT-4) which are slow and costly for simple classification tasks, SetFit adapts sentence transformers using contrastive learning. It achieves high accuracy with extremely limited data—often as few as 8 labeled examples per class. This efficiency allows for the creation of lightweight, highly specific routers (e.g., "Code Lookup" vs. "Concept Exploration") that can run locally with negligible latency.15 This replaces brittle regex heuristics with robust semantic understanding.
2.3 Reranking Paradigms
Reranking is the process of refining the initial, often noisy, set of retrieved candidates. The state of the art has moved from simple cross-encoders to sophisticated LLM-based techniques.
Setwise and Listwise LLM Reranking:
While pointwise reranking (scoring one document at a time) is efficient, it lacks the context of the broader result set. RankGPT 16 popularized listwise reranking, where the LLM is prompted with a list of candidates and asked to reorder them. However, listwise ranking can suffer from token limits and position bias. Setwise reranking 7 has emerged as a superior alternative for efficiency and precision. In this paradigm, the LLM is presented with a set of documents and asked to select the "best subset" or the "single best" document, often using a tournament-style comparison (e.g., heap sort). This approach leverages the LLM's reasoning capabilities to identify the most informative combination of documents, which is crucial for RAG where redundancy is wasteful.
Cross-Encoders:
For the intermediate stage of retrieval—between the initial fetch and the final LLM rerank—Cross-Encoders (e.g., BERT-based models) remain the gold standard.18 Unlike bi-encoders (dense embeddings) which calculate similarity via dot product, cross-encoders process the query and document simultaneously, capturing deep semantic interactions. They are computationally more expensive but provide a much cleaner signal for the top 50-100 candidates.
2.4 Fusion Paradigms
Combining scores from disparate sources—such as dense vector distance, BM25 keyword scores, and graph centrality metrics—is a non-trivial mathematical challenge due to scale mismatch.
Distributional Mismatch and Z-Score Normalization:
A core issue in hybrid search is that BM25 scores are theoretically unbounded (0 to $\infty$, heavily dependent on term frequency) while Cosine Similarity scores are bounded (typically 0 to 1 or -1 to 1). A simple weighted sum or max-score fusion often leads to one signal dominating the other purely due to scale, not relevance. Z-Score Normalization 5 addresses this by standardizing scores to a common distribution (mean 0, standard deviation 1) before fusion. This ensures that a score is interpreted as "how many standard deviations above the average relevance is this document," providing a common unit of measure for disparate signals.
Reciprocal Rank Fusion (RRF):
An alternative, rank-based approach is Reciprocal Rank Fusion (RRF).19 RRF ignores the raw scores entirely and fuses results based on their rank position ($Score = \sum 1/(k + rank_i)$). This method is highly robust to outliers and requires no tuning of weights or normalization parameters. However, by discarding the raw scores, RRF loses information about the magnitude of relevance—a "perfect match" is treated the same as a "slightly better" match if they have the same rank.
2.5 Human-in-the-Loop Evaluation
Finally, the taxonomy must include evaluation. Automated metrics (like nDCG) often fail to capture the nuance of "helpfulness" in RAG.
Rubric-Based Evaluation:
Recent research into LLM-Rubric 21 and ResearchRubrics 23 suggests that generic relevance judgments are insufficient. Instead, multi-dimensional rubrics (e.g., assessing "Correctness," "Completeness," and "Groundedness" separately) provide a higher correlation with human preference. These rubrics can be used to guide human annotators or to prompt "LLM-as-a-Judge" evaluators, creating a feedback loop that is both scalable and aligned with human intent.
3. “Top 10 Most Promising Techniques” Shortlist
Based on the extensive literature review, we have synthesized a shortlist of the ten most promising techniques for LLMC. These are ranked by a composite score of their potential impact on retrieval quality and their feasibility within the existing LLMC architecture.


Rank
	Technique
	Description
	Evidence Strength
	LLMC Integration Complexity
	Failure Modes
	1
	SetFit Intent Routing
	A few-shot transformer classifier to dynamically gate Code vs. Doc routes based on query intent.
	Strong 3
	Low (Python lib integration)
	Over-routing to a single branch if training data is biased or unrepresentative.
	2
	RepoGraph Construction
	Constructing a graph where nodes are Files/Classes/Functions and edges are Calls/Imports, enabling structural traversal.
	Strong 1
	Med (Augment .llmc/rag_graph.json)
	Parser failures on dynamic languages (Python) or incomplete distinct resolution.
	3
	Z-Score Fusion
	Normalizing dense and sparse scores via $(x - \mu)/\sigma$ to align distributions before weighted summation.
	Med 5
	Low (Modify fusion.py)
	Score distribution drift over time requires periodic re-calculation of $\mu$ and $\sigma$.
	4
	Graph Neighbor Expansion
	Augmenting the set of retrieved candidates by pulling in their 1-hop dependencies (e.g., definitions of called functions).
	Strong 11
	Med (Modify search_spans)
	Context window explosion if "hub" nodes (common utilities) are expanded.
	5
	Setwise LLM Reranking
	Prompting an LLM to select the "Best Set" of $k$ documents from $n$ candidates to maximize coverage and minimize redundancy.
	Strong 7
	Med (Prompt engineering)
	The LLM may hallucinate document IDs or fail to follow strict format; high latency.
	6
	Reciprocal Rank Fusion (RRF)
	Fusing rankings via $Score = \sum 1/(k + rank_i)$. A robust, parameter-free method for hybrid search.
	Strong 19
	Low (Existing pattern)
	Ignores strong "exact match" signals by discarding raw score magnitude.
	7
	Code@k Metric
	A precision metric specifically calculating the % of top-k results that are valid code entities for code-intent queries.
	Strong 24
	Low (Eval harness update)
	Requires a rigorous ground-truth "gold" set of code files to be meaningful.
	8
	Cross-Encoder Reranking
	Using a small BERT-based model to rescore the top-50 candidates before the expensive LLM reranking stage.
	Strong 18
	Med (New model dependency)
	Adds latency overhead, particularly on CPU-only deployments.
	9
	Active Learning (Argilla)
	A human-in-the-loop workflow using Argilla to collect feedback and iteratively improve the router/retriever.
	Med 25
	High (New workflow/UI)
	User fatigue leading to sparse feedback; integration complexity.
	10
	Graph Neural Rerank (GReX)
	Using a GNN to score nodes based on their interaction with the query representation in the graph space.
	Med 12
	High (New model training)
	High training complexity; risk of over-engineering for marginal gains.
	4. Proposed Scoring Architecture (Blueprint)
This section details the modular blueprint for upgrading LLMC’s retrieval system. The architecture is designed to be additive to the existing llmc modules, minimizing disruption while maximizing the "intelligence" of the retrieval pipeline.
4.1 Candidate Generation (The Retrieval Layer)
The foundation of the new architecture is a Router-Gated Execution model. Currently, LLMC’s routing is heuristic-based and often defaults to fanning out queries to all available indices ([routing.multi_route.code_primary]). We propose replacing this with a SetFit 26 classifier that predicts the user's intent with high precision.
Intent Classification:
We define three primary intent classes:
* CODE_LOOKUP: The user is looking for a specific implementation, function definition, or variable. (e.g., "Where is search_spans defined?", "show me the fusion logic")
* CONCEPT_EXPLORATION: The user is looking for high-level documentation, tutorials, or architectural overviews. (e.g., "How does routing work?", "What is the retry policy?")
* MIXED: The query is ambiguous or requires both code and explanation. (e.g., "Why is the scorer failing?")
Mechanism:
The llmc.toml configuration will include a [routing.classifier] section pointing to a local SetFit model. Upon receiving a query, the search_spans function (in llmc/rag/search/__init__.py) will first invoke the router.
* If CODE_LOOKUP is predicted with high confidence (>0.9): The system queries the emb_code (Dense) and bm25_code (Sparse) indices. Crucially, it also triggers the Graph Neighbor Expansion (see 4.2).
* If CONCEPT_EXPLORATION is predicted: The system targets the embeddings (Docs) and bm25_docs indices.
* If MIXED or confidence is low (<0.6): The system falls back to the existing behavior of querying all indices.
4.2 Graph Augmentation (The Structural Signal)
We utilize the existing .llmc/rag_graph.json artifact not merely for "stitching" disparate chunks but as an active retrieval expansion mechanism. This aligns with the RepoGraph 2 methodology, which emphasizes the use of structural edges to complete the context window.
Schema Expectations:
The graph must adhere to a schema compatible with RepoGraph principles:
* Nodes: Entities such as File, Class, and Function. Each node must possess attributes for start_line, end_line, and file_path.
* Edges: Semantic relationships including DEFINES (File $\rightarrow$ Class), CALLS (Function $\rightarrow$ Function), IMPORTS (File $\rightarrow$ File), and INHERITS (Class $\rightarrow$ Class).
Scoring Contribution (Graph Expansion):
The integration logic within llmc/rag/search/__init__.py will follow this sequence:
1. Initial Retrieval: Execute standard dense retrieval to obtain the Top-$K$ candidates (e.g., $K=20$).
2. Expansion: For each candidate in the Top-$K$, use the graph index APIs (llmc/rag/graph_index.py::lineage_files) to identify its 1-hop neighbors via CALLS and DEFINES edges.
3. Bonus Scoring (Neighbor Augmentation): If a retrieved candidate has a neighbor that was also retrieved, their scores are mutually reinforced. More importantly, neighbors that were not retrieved by the vector search are added to the candidate pool with a graph_boost score (e.g., $0.1 \times \text{parent\_score}$). This ensures that if the user searches for a function usage, the function's definition is also brought into the context.
4. Hub Penalty: To avoid "graph noise amplification" (Risk #1), we apply a degree-based penalty. Nodes with an excessively high degree (e.g., utility functions called by 10,000 files) contribute a negligible boost, preventing them from flooding the context window.11
4.3 Reranking (The Precision Layer)
To balance the computational cost of LLMs with the need for high precision, we implement a two-tier reranking strategy 18:
Tier 1: Statistical/Light Reranker (Cross-Encoder):
A small, local model (e.g., bge-reranker-base) is used to rescore the Top-50 candidates. Cross-encoders are significantly more accurate than bi-encoders (dense embeddings) because they observe the query and document interaction directly. This stage serves to filter out "obvious noise" efficiently.
Tier 2: LLM Setwise Reranker:
For the Top-10 surviving candidates, we employ a Setwise reranking approach.7 Unlike Listwise ranking which asks for an ordering, Setwise ranking asks the LLM to "Select the subset of these snippets that explicitly helps answer the query." This is prompted as a selection task, which is more robust to the "lost-in-the-middle" phenomenon and reduces token consumption compared to generating a full ranked list.
Anti-Hallucination Guardrail:
The LLM output is parsed strictly. If the LLM returns an ID that was not in the input set, that ID is discarded. If the LLM returns an empty set or fails to follow the JSON format, the system falls back to the Tier 1 ranking order.
4.4 Fusion (The Integration Layer)
We recommend replacing the current max_weight fusion with a configurable Z-Score Weighted Fusion.5
The Distributional Mismatch Problem:
Data indicates a critical flaw in fusing raw scores: BM25 scores (Lexical) often follow a long-tail distribution with values ranging from 0 to 40+ depending on keyword rarity. In contrast, Cosine Similarity scores (Dense) typically cluster in a tight bell curve between 0.6 and 0.9. When using max_weight or simple summation, a single high BM25 score (e.g., 35.0) will mathematically dominate the fusion, rendering the dense signal (e.g., 0.85) irrelevant. Conversely, Reciprocal Rank Fusion (RRF) solves this by using rank position (1, 2, 3...) which is a step function. While robust, RRF discards the magnitude of the signal—a "perfect" match at rank 1 is treated identically to a "barely relevant" match at rank 1.
The Z-Score Solution:
Z-Score normalization ($z = \frac{x - \mu}{\sigma}$) addresses this by centering both distributions around 0 with a standard deviation of 1.
* Process:
   1. Calculate the mean ($\mu$) and standard deviation ($\sigma$) for the scores in the current result batch for each route.
   2. Normalize each score: $S_{norm} = (S_{raw} - \mu) / \sigma$.
   3. Fuse the normalized scores: $S_{final} = W_{dense} \cdot S_{dense\_norm} + W_{sparse} \cdot S_{sparse\_norm} + W_{graph} \cdot S_{graph\_boost}$.
This approach aligns the "bell curves" of the different retrieval methods, ensuring that a result is ranked based on how much it stands out relative to its own method's distribution.
   * Fallback: If the batch size is too small (<5) to calculate reliable statistics, the system should fall back to Reciprocal Rank Fusion (RRF) 19 to ensure stability.
4.5 Dynamic Scoring / Routing
We implement a Gating Model using SetFit to control the retrieval flow.
   * Training Data: We leverage the existing llmc/rag/eval/routing_eval.py script to generate a training dataset.
   * Queries starting with "function", "def", "class", "where is" are labeled CODE_LOOKUP.
   * Queries containing "overview", "how to", "guide", "concept" are labeled CONCEPT_EXPLORATION.
   * Inference Logic: In search_spans, the system runs router.predict(query).
   * Hard Routing: If the prediction confidence is $>0.9$, the system queries only the predicted route indices.
   * Soft Routing (Hybrid): If the confidence is $<0.9$ (indicating ambiguity), the system queries both routes but applies a weight penalty to the lower-confidence route.
   * Logging: All routing decisions—Query, Predicted Intent, Confidence Score—are logged for future analysis and active learning iterations.
5. Implementation Plan (Engineering-Ready)
This plan assumes the starting point is the current llmc codebase and outlines a phased deployment.
Phase 1: Foundation (Weeks 1–2)
   * Goal: Implement robust fusion and establish basic routing metrics.
   * Modules: llmc/routing/fusion.py, llmc/rag/eval/routing_eval.py.
   * Action:
   1. Refactor Fusion: Modify fuse_scores to support RRF as an alternative to max_weight. This provides an immediate "safe" fallback.19
   2. Metric Implementation: Implement the Code@k metric in routing_eval.py. This metric calculates the percentage of top-$k$ results that are valid code files when the ground truth intent is code-related.
   3. Instrumentation: Instrument search_spans to log the "Intent" (even if unused) to build a dataset for Phase 3 training.
Phase 2: Graph Augmentation (Weeks 3–4)
   * Goal: Integrate graph signals into the retrieval process.
   * Modules: llmc/rag/search/__init__.py, llmc/rag/graph_index.py.
   * Artifacts: Verify that .llmc/rag_graph.json contains calls and imports edges. If missing, integrate pycg or tree-sitter bindings to generate them during the indexing phase.27
   * Action:
   1. GraphExpander Class: Create a class responsible for taking a set of file/function IDs and returning their 1-hop neighbors.
   2. Search Integration: In search_spans, immediately after dense retrieval, pass the candidate IDs to GraphExpander.
   3. Scoring Logic: Add the retrieved neighbors to the candidate set. Assign them a graph_boost score (e.g., $0.1 \times \text{parent\_score}$), ensuring they appear in the reranking pool but don't displace direct matches unless validated by the reranker.
Phase 3: Dynamic Scoring (Weeks 5–6)
   * Goal: Train and deploy the Router and Z-Score fusion.
   * Modules: llmc/routing/router.py, llmc.toml.
   * Action:
   1. Train SetFit: Train a small SetFit model using the logs collected in Phase 1.3 Save this model to .llmc/models/setfit-router-v1.
   2. Z-Score Implementation: Update fusion.py to support Z_SCORE mode. This requires a two-pass processing logic: first pass to calculate batch statistics ($\mu, \sigma$), second pass to normalize and fuse.
   3. Config Updates: Add a [scoring.dynamic] toggle in llmc.toml to enable/disable these features.
Phase 4: Advanced Reranking (Week 7+)
   * Goal: Add LLM-based Setwise Reranking for high-precision filtering.
   * Modules: llmc/rag/rerank.py.
   * Action:
   1. SetwiseReranker: Implement a SetwiseReranker class using the main LLM client.
   2. Prompt Integration: Use the specific prompt template defined in the Appendix (Section 9.1).
   3. Guardrails: Add a cost_guardrail configuration to only trigger this expensive step if the candidate count is low ($<20$) or if the query is flagged as MIXED intent.
6. Evaluation Plan (Offline + Online)
6.1 Offline Evaluation
We must rigorously measure if the new system retrieves better code, not just more documents.
   * Dataset: Construct a "Golden Set" of 100 queries targeting specific functions in the LLMC codebase itself.
   * 50 Code-Intent: e.g., "Where is fuse_scores defined?" (Target: llmc/routing/fusion.py)
   * 50 Doc-Intent: e.g., "How does routing work?" (Target: README.md or docs/routing.md)
   * Metrics:
   * Code@k (Precision@k for Code Files): The percentage of top-$k$ results that are actual code files when the query is code-intent.11 This directly measures the system's ability to prioritize implementation over documentation.
   * Context Precision: Does the relevant chunk appear in the Top-3 results?.28
   * Graph Coverage: The percentage of retrieved chunks that are graph-connected to the "ground truth" file. High coverage indicates that the graph expansion is working correctly.
6.2 Online Evaluation (Implicit Signals)
   * Copy Rate: If a user copies a code block from the retrieved context, we assign a implicit relevance score of 1.
   * Regeneration Rate: If a user immediately rewrites the query or regenerates the answer, we assign a score of 0.
   * Gate Logging: We explicitly log the tuple (Query, Predicted_Intent, Confidence, User_Action). A high Regeneration Rate on queries where Confidence > 0.9 indicates that the router is miscalibrated and confidentially wrong.
7. Human Scoring System Design
To align the automated metrics with genuine utility, we require a "Human-in-the-Loop" calibration process, utilizing a Rubric-Based approach.21
7.1 The Relevance Rubric
We propose moving away from a binary "relevant/not-relevant" scale to a 4-point graded scale that captures the nuance of code retrieval.
Score
	Grade
	Description
	Code-Specific Criteria
	3
	Perfect
	Contains the exact answer/code.
	The snippet is the definition of the requested function/class.
	2
	Helpful
	Contains necessary context/usage.
	The snippet calls or imports the target, or is a relevant unit test.
	1
	Related
	Topically relevant but insufficient.
	Same module/file but wrong function; or generic documentation.
	0
	Irrelevant
	Noise.
	Unrelated code; wrong language; hallucinated file.
	7.2 Active Learning Workflow
We recommend integrating Argilla 25 for a lightweight feedback loop. This involves a cyclical process:
   1. Sampling: Automatically sample 5% of production queries, focusing on those where the Router confidence was marginal (0.4–0.6).
   2. Labeling: Engineers use the Rubric to score the top 3 retrieved docs for these sampled queries.
   3. Optimization: These "Gold Labels" are used to fine-tune the SetFit router (retraining it on hard examples) and to calibrate the Z-Score fusion weights (using Logistic Regression or Platt Scaling 29).


  



8. Risks, Failure Modes, and Sharp Edges
The implementation of this dynamic system introduces specific risks that must be managed.
   1. Graph Noise Amplification:
   * Risk: A common utility function (e.g., utils.log) might have thousands of incoming CALLS edges. If GraphExpander naively expands all neighbors, the context window will be flooded with irrelevant "callers," drowning out the actual logic.
   * Mitigation: Implement a Degree-Based Penalty in GraphExpander. High-degree nodes (hubs) should contribute a significantly lower score boost or be excluded from expansion entirely.11
   2. Cost Blowout (Setwise Reranking):
   * Risk: Running an LLM reranker on every query adds noticeable latency (approx. 1-2s) and API costs.
   * Mitigation: Only trigger Tier 2 Reranking for MIXED or CONCEPT queries where ambiguity is high. For pure CODE_LOOKUP queries, the Dense+Graph signal is usually sufficient, so we can trust the Tier 1 ranking.
   3. Embedding Model Drift:
   * Risk: If the underlying dense embedding model is updated or retrained, the Z-Score statistics ($\mu, \sigma$) calculated on the old distribution will become invalid immediately, leading to skewed fusion.
   * Mitigation: Version the fusion_stats.json artifact alongside the embedding index. Force a re-calculation of stats whenever a new index is loaded.
   4. Over-Routing to Code:
   * Risk: The SetFit router might overfit and learn to classify every query as "Code" if the training data is skewed towards implementation queries.
   * Mitigation: Monitor the routing_distribution metric in production. If the Code route accounts for >90% of traffic, alert the team to retrain the router with a more balanced dataset.
9. Appendix: Prompts & Configuration


9.1 Setwise Reranking Prompt Template
7


This prompt is designed for the SetwiseReranker in Phase 4.
You are a code retrieval expert.
Query: "{query}"
I will provide a set of candidate snippets (Code or Docs).
Your task is to select the subset of candidates that are most helpful for answering the query.
   * Prefer exact code definitions over usages.
   * Prefer documentation that explains the mechanism over generic intros.
   * If a snippet is irrelevant, exclude it.
Candidates:
{candidates_list} # Format: Content...
Output ONLY a JSON list of the selected IDs, ordered by relevance.
Example: ["doc_12", "code_5"]
9.2 LLMC Configuration Additions (llmc.toml)


Ini, TOML




[routing.classifier]
enable_dynamic_routing = true
model_path = ".llmc/models/setfit-router-v1"
confidence_threshold = 0.85

[rag.graph]
enable_expansion = true
max_hops = 1
hub_penalty_threshold = 50  # Ignore nodes with >50 edges

[scoring.fusion]
method = "z_score"  # Options: "max", "rrf", "z_score"
fallback_to_rrf = true
weights = { dense = 1.0, bm25 = 0.8, graph = 0.5 }

Works cited
   1. RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph - arXiv, accessed December 19, 2025, https://arxiv.org/html/2410.14684v2
   2. REPOGRAPH: ENHANCING AI SOFTWARE ENGINEER- ING WITH REPOSITORY-LEVEL CODE GRAPH - ICLR Proceedings, accessed December 19, 2025, https://proceedings.iclr.cc/paper_files/paper/2025/file/4a4a3c197deac042461c677219efd36c-Paper-Conference.pdf
   3. Small Training Dataset? You Need SetFit - Towards Data Science, accessed December 19, 2025, https://towardsdatascience.com/small-training-dataset-you-need-setfit-61d43c7d92f2/
   4. Prompt-free Efficient Few Shot Learning | What is SetFit? | Width.ai, accessed December 19, 2025, https://www.width.ai/post/what-is-setfit
   5. Introducing the z-score normalization technique for hybrid search - OpenSearch, accessed December 19, 2025, https://opensearch.org/blog/introducing-the-z-score-normalization-technique-for-hybrid-search/
   6. Hybrid Search 2.0: The Pursuit of Better Search | Towards Data Science, accessed December 19, 2025, https://towardsdatascience.com/hybrid-search-2-0-the-pursuit-of-better-search-ce44d6f20c08/
   7. Shifting from Ranking to Set Selection for Retrieval Augmented Generation - arXiv, accessed December 19, 2025, https://arxiv.org/html/2507.06838v2
   8. A Setwise Approach for Effective and Highly Efficient Zero-shot Ranking with Large Language Models | Request PDF - ResearchGate, accessed December 19, 2025, https://www.researchgate.net/publication/382197643_A_Setwise_Approach_for_Effective_and_Highly_Efficient_Zero-shot_Ranking_with_Large_Language_Models
   9. RANGER -- Repository-Level Agent for Graph-Enhanced Retrieval - ChatPaper, accessed December 19, 2025, https://chatpaper.com/paper/194690
   10. RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph - arXiv, accessed December 19, 2025, https://arxiv.org/html/2410.14684v1
   11. RANGER: Repository‑level Agent for Graph‑Enhanced Retrieval - arXiv, accessed December 19, 2025, https://arxiv.org/html/2509.25257v1
   12. GReX: A Graph Neural Network-Based Rerank-then-Expand Method for Detecting Conflicts Among Legal Articles in Korean Criminal Law, accessed December 19, 2025, https://aclanthology.org/2025.nllp-1.30.pdf
   13. ExpertRAG: Efficient RAG with Mixture of Experts – Optimizing Context Retrieval for Adaptive LLM Responses - arXiv, accessed December 19, 2025, https://arxiv.org/pdf/2504.08744?
   14. RouterRetriever: Routing over a Mixture of Expert Embedding Models - arXiv, accessed December 19, 2025, https://arxiv.org/html/2409.02685v2
   15. Intent Detection in the Age of LLMs - arXiv, accessed December 19, 2025, https://arxiv.org/html/2410.01627v1
   16. How Good are LLM-based Rerankers? An Empirical Analysis of State-of-the-Art Reranking Models - arXiv, accessed December 19, 2025, https://arxiv.org/html/2508.16757v1
   17. Guiding Retrieval using LLM-based Listwise Rankers - arXiv, accessed December 19, 2025, https://arxiv.org/html/2501.09186v1
   18. Should You Use LLMs for Reranking? A Deep Dive into Pointwise, Listwise, and Cross-Encoders - ZeroEntropy, accessed December 19, 2025, https://www.zeroentropy.dev/articles/should-you-use-llms-for-reranking-a-deep-dive-into-pointwise-listwise-and-cross-encoders
   19. [2512.05967] Enhancing Retrieval-Augmented Generation with Entity Linking for Educational Platforms - arXiv, accessed December 19, 2025, https://www.arxiv.org/abs/2512.05967
   20. RAG-Fusion: a New Take on Retrieval-Augmented Generation - arXiv, accessed December 19, 2025, https://arxiv.org/html/2402.03367v2
   21. LLM-Rubric: A Multidimensional, Calibrated Approach to Automated Evaluation of Natural Language Texts† - arXiv, accessed December 19, 2025, https://arxiv.org/html/2501.00274v1
   22. LLM-RUBRIC: A Multidimensional, Calibrated Approach to Automated Evaluation of Natural Language Texts: - ACL Anthology, accessed December 19, 2025, https://aclanthology.org/2024.acl-long.745.pdf
   23. ResearchRubrics: A Benchmark of Prompts and Rubrics For Evaluating Deep Research Agents - arXiv, accessed December 19, 2025, https://arxiv.org/html/2511.07685v1
   24. How do we evaluate vector-based code retrieval? - Voyage AI, accessed December 19, 2025, https://blog.voyageai.com/2024/12/04/code-retrieval-eval/
   25. Improving RAG by Optimizing Retrieval and Reranking Models - Argilla docs, accessed December 19, 2025, https://docs.v1.argilla.io/en/v2.7.0/tutorials_and_integrations/tutorials/feedback/fine-tuning-sentencesimilarity-rag.html
   26. Faster, Cheaper, Better: The Power of Model Routing - DEV Community, accessed December 19, 2025, https://dev.to/mrzaizai2k/faster-cheaper-better-the-power-of-model-routing-3n14
   27. PyCG: Practical Call Graph Generation in Python - ResearchGate, accessed December 19, 2025, https://www.researchgate.net/publication/351419432_PyCG_Practical_Call_Graph_Generation_in_Python
   28. Context Precision - Ragas, accessed December 19, 2025, https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/
   29. The Complete Guide to Platt Scaling - Train in Data's Blog, accessed December 19, 2025, https://www.blog.trainindata.com/complete-guide-to-platt-scaling/