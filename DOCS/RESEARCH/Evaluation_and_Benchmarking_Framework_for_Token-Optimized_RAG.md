# Evaluation  Benchmarking Framework for Token-Optimized RAG

Evaluation & Benchmarking Framework for TokenOptimized RAG
Executive Summary
This document proposes a comprehensive evaluation and benchmarking framework for LLMC’s RetrievalAugmented Generation (RAG) pipeline, focusing on measuring the cost vs. quality trade-offs introduced
by recent token optimization techniques (compression, caching, tiered LLM routing). The goal is to provide
an automated harness that can quantitatively validate improvements (or catch regressions) in retrieval
accuracy and token efficiency. Key components of the design include a golden dataset of queries with
known relevant code spans and answers, a suite of retrieval quality metrics (Precision@K, Recall@K,
NDCG, MRR) 1 2 , and token efficiency metrics (e.g. tokens per answer, cost per query, context waste).
The framework will be built around pytest-based test suites and a command-line tool ( llmc eval ) to
run controlled experiments on different model tiers (local Qwen 7B vs 14B vs GPT-5-nano) under identical
conditions. Automated nightly evaluation runs (via GitHub Actions) will generate reports with
visualizations and flag any significant performance regressions (e.g. >10% drop in precision or >10%
increase in token usage). By combining rigorous information retrieval metrics with cost accounting, this
evaluation harness enables data-driven decisions on routing strategies and ensures that token
optimizations deliver real improvements in RAG quality per dollar.

Architecture Design
The evaluation framework is designed as a modular pipeline that interfaces with LLMC’s existing RAG
system and logging. It consists of several coordinated components:
• Test Harness & Runner: A Python-based harness (invoked via CLI or pytest) that orchestrates
running a set of standardized queries through the RAG pipeline. It ensures each query’s execution is
deterministic and instrumented – forcing specific model tiers when needed, capturing metrics
from logs, and controlling for randomness. The harness supports running in different modes (e.g.
local-only, full tiered routing) to compare strategies A vs B under identical conditions.
• Metrics Computation Engine: A library of metric functions to compute retrieval accuracy and
efficiency stats from the pipeline outputs. This engine parses the JSONL logs (e.g.
planner_metrics.jsonl and enrichment_metrics.jsonl ) to extract relevant fields
(retrieved span IDs, planner confidence, tokens used, etc.), then computes metrics like Precision@K
and Recall@K by comparing retrieved spans against the golden truth 3 4 . It also computes
aggregate token usage and cost metrics per query (using known token pricing for each tier).
• Golden Dataset Manager: A module responsible for loading and validating the curated set of test
queries (“golden” queries) along with their expected relevant spans and answers. It ensures the
dataset conforms to a fixed schema (see Golden Dataset Schema below) and that any code
references (file paths, symbol names) are up-to-date with the repository.
• Result Analyzer & Regressions: A comparison module that takes metrics from current runs and
optionally from a baseline (previous run or known good commit) to identify regressions. It can

1

perform statistical significance checks or simple threshold comparisons to decide if a difference in
metrics is likely noise or a real degradation. For example, if Precision@5 drops by >10% or average
tokens per query increases by >10%, the harness will mark it as a regression requiring attention.
• Reporting & Visualization: After computing metrics, the framework generates a human-readable
report (as Markdown or HTML). This report includes tabular summaries of metrics, trend graphs
over time (if historical data is stored), and specialized charts like cost vs. quality Pareto frontiers
(illustrating how different model tiers trade off answer quality for token cost) and tier usage
breakdowns (what percentage of queries were handled by local vs API vs Codex). These help
stakeholders quickly understand the impact of any changes.
Overall, the architecture cleanly separates data collection (via logs and test runs) from analysis (metrics
calculations) and presentation (reports), making it easy to extend. The harness will integrate with LLMC’s
existing CLI and logging: it uses the same pipeline invocation ( llmc CLI or underlying Python calls) and
reads the same JSONL log format to remain fully compatible with existing telemetry (append-only logs).
This modular design also allows re-running the evaluation on historical log files if needed, or plugging in
different metric computations (for example, integrating emerging RAG metrics like “faithfulness” from
RAGAS or “groundedness” from TruLens in the future 5 6 ).

Test Harness and Workflow
The test harness can be invoked either as a command-line tool ( llmc eval ) or as a pytest suite for CI
automation. Internally, it uses pytest fixtures to spin up any required services (e.g. ensuring the local
Chroma vector DB is populated, loading the Ollama Qwen models into memory) and to initialize log
capture. Each query from the golden set runs as a sub-test. The harness ensures that for each test query: 1.
The RAG planner is run to select a route/tier (unless a specific tier is being forced for an experiment), and
the retriever obtains top-K code spans from the knowledge base. We capture the planner’s chosen route
and confidence from planner_metrics.jsonl (fields: confidence , span_count , top_span etc.).
2. The enrichment step is executed – i.e., an LLM is prompted with the query and retrieved spans.
Depending on the mode, this could be forced to a particular model (e.g. always local 7B for a baseline run)
or use the normal smart routing. The enrichment_metrics.jsonl log captures which tier was used
( tier_used ), how many input tokens were sent ( tokens_in ), output tokens ( tokens_out ), and the
result status. 3. After each query, the harness collects the relevant log entries and resets any state for the
next query (to avoid cross-talk or cache interference).
Using pytest for the harness provides rich reporting and easy integration with CI. The harness will mark
tests as failed if certain quality criteria are not met (for instance, if a relevant span was missed entirely – low
recall – or if an answer is empty), and will record metrics for all queries regardless of pass/fail for aggregate
analysis.

Metrics Computation Pipeline
Once a batch of queries is executed, the framework computes metrics in two categories: RAG Quality and
Token Efficiency. All metric calculations are implemented in a standalone metrics.py module for clarity.
• Precision@K and Recall@K: Using the golden dataset’s list of expected relevant spans, the top-K spans
returned by the system are evaluated. Precision@K is the fraction of the retrieved top-K that are
relevant 3 . Recall@K is the fraction of all relevant spans that were retrieved in the top-K 4 . These

2

metrics are computed per query and averaged across the dataset. For example, if a query had 3
relevant code snippets and the system’s top-5 retrieval included 2 of them, Recall@5 = 0.67 while
Precision@5 = 0.4 for that query. We will typically use K corresponding to the number of spans the
system injects (e.g. K=3 or 5).
• Mean Reciprocal Rank (MRR): This is an order-aware metric focusing on the rank of the first relevant
result 2 . It computes the reciprocal of the rank position of the first correct span, averaged over all
queries. An MRR of 1.0 means the top result was always relevant 7 . This helps measure how well
the system prioritizes the most relevant context at rank 1.
• Normalized Discounted Cumulative Gain (NDCG@K): NDCG measures the quality of the ranking of
results, taking into account graded relevance and position 8 9 . In our case, we can treat each
span as either relevant or not (binary relevance), or assign a relevance score from the golden dataset
if available (e.g. if some spans are more relevant than others). NDCG@K will be computed to gauge
how well the system orders the spans – a higher NDCG means relevant spans are ranked high, close
to the ideal ordering 10 11 . We normalize DCG to account for varying number of results per query,
so scores are comparable across queries 12 11 .
• Tokens per Accurate Answer: For token efficiency, we define a metric of tokens consumed per correct
result. If a query’s answer is deemed accurate (e.g. the expected span was retrieved and used), we
record the total tokens (input + output) spent to get that answer. Averaged across the test set, this
tells us the token cost of each successful Q&A. A lower value is better – meaning the system uses
fewer tokens to get to a correct answer.
• Cost per Query: Using a cost model for each tier (e.g. $0.00 for local, $0.002 per 1K tokens for API,
$0.01 per 1K for Codex – actual rates to be defined), the harness estimates the dollar cost of each
query’s processing. It sums (tokens_in + tokens_out) * cost_per_token for the tier
actually used. We then report average cost per query and the distribution. This metric, combined
with quality metrics, allows plotting a Pareto frontier of cost vs quality. For instance, we might find
that using only local models yields $0 cost but lower recall, whereas using the API tier increases
recall by 5% at a marginal cost of $0.001 per query – such trade-offs will be made explicit by our eval
reports.
• Context Waste Ratio: This measures how much retrieved context was unnecessary. We can define it as
irrelevant tokens / total context tokens in the prompt. Using the golden dataset’s expected spans
as ground truth, any retrieved span that is not in the expected set is considered irrelevant
(potentially a false positive). We know how many tokens each span contributed (we can count
characters or tokens of those files). So for each query, if the system retrieved N spans totaling
T_tokens, and out of those, R_tokens were relevant (from spans that should have been retrieved), the
waste ratio = (T_tokens - R_tokens) / T_tokens. This helps quantify whether compression or better
retrieval filtering is reducing the inclusion of useless context. A lower waste ratio is better (more of
the prompt context was actually useful).
• Tier Efficiency & Escalation Rate: We track what percentage of queries were answered by each tier. Tier
efficiency is basically the routing distribution – e.g. 80% handled by local 7B, 15% escalated to API,
5% to Codex. A healthy trend might show more queries staying on cheaper tiers if optimizations are
working. Escalation rate specifically measures how often the system had to “retry” a query on a
higher tier after a lower-tier attempt failed or was deemed low-confidence. We can detect this by
seeing if a query ID appears multiple times in enrichment_metrics.jsonl with increasing
tier_used, or via a flag in the log result field (e.g. result: escalated ). This metric directly reflects
the planner’s accuracy: a high escalation rate means the router often underestimates difficulty
(tries local but then needs API, etc.).

3

• Confidence Calibration: The planner’s confidence score (as logged in planner_metrics) should
correlate with success. We will measure calibration by grouping queries into confidence buckets (e.g.
0-0.3, 0.3-0.6, 0.6-1.0) and computing the actual success rate in each bucket. If the planner is wellcalibrated, a group of queries with ~80% confidence should indeed have about 80% success (e.g.
retrieved the needed spans or answered correctly). We can use plots or a simple calibration error
metric. Additionally, we report the overall correlation between confidence and outcome. This helps
identify if the confidence scoring needs adjustment.
The metrics engine will output a structured summary (JSON or Python dict) of all these computed metrics
for use in reports. Notably, many of these metrics align with those used in industry frameworks: e.g. Arize’s
RAG monitoring focuses on Precision/Recall/F1 13 , ARES emphasizes MRR/NDCG 14 , and RAGAS includes
context relevancy and answer faithfulness 5 . By implementing Precision, Recall, MRR, NDCG, etc., we
ensure our evaluations are in line with accepted standards while tailoring additional metrics (token usage,
cost) to LLMC’s needs.

Golden Dataset Creation Methodology
Building a golden dataset is critical, as it serves as the ground truth for evaluation. Our approach to
curating and maintaining this dataset involves both expert knowledge and automation:
1. Representative Query Selection: We will gather a set of queries that reflect the real usage patterns
of LLMC. This includes common developer questions (e.g. “How does authentication work?”), edge
cases, and recent incidents where the system’s performance was suboptimal. Logs of actual user
queries can be mined for frequent or challenging queries. We aim for a dataset size that is large
enough to be representative (perhaps 50-100 queries) but small enough for manual verification.
2. Manual Annotation of Relevant Spans: For each query, domain experts (e.g. developers familiar
with the codebase) will identify which code snippets or documentation sections are relevant to
answering the question. This yields the list of expected_spans for that query. Each span entry
includes a stable identifier (could be a hash of the content or a reference like file path + function
name) and an optional relevance score. Initially, we can use binary relevance (relevant or not), but if
some spans are “highly relevant” vs “somewhat relevant,” we can encode that in
relevance_score . Important: We also record the context that should answer the question – if
the question is fact-based, the ground_truth_answer is provided for reference (this can be used for
evaluating answer correctness qualitatively, though our automated metrics focus on retrieval).
3. Diversity and Difficulty Tags: Each query in the golden set is tagged with metadata like topic area
( auth , database , UI etc.), difficulty ( easy , medium , hard ), and any special characteristics
(e.g. requires multi-hop reasoning, requires combining multiple files). This allows segmenting
results. For example, we might find that “hard” queries have lower precision, indicating room for
improvement in those cases.
4. Validation of Dataset: We will create a small script to verify that all expected_spans actually
exist in the current codebase (to avoid stale references). This script can be part of a pre-evaluation
step, warning if any span content changed significantly (in which case the expected answer might
change). The dataset file (likely a JSON or YAML like golden_queries.json ) will be under version
control so that updates are tracked via pull requests. Changes to the golden set (like adding a new
tricky query) should undergo review, since they effectively change the evaluation criteria.
5. Ongoing Updates: As the codebase evolves and new features are added, we’ll periodically update
the golden set. One methodology is to require that any major feature PR must contribute at least

4

one new golden query relevant to that feature. This way, the evaluation stays current. We will also
use the evaluation results themselves to identify gaps: for instance, if a certain type of question
consistently has poor recall, we may add more queries of that type (or refine expected spans) to
better cover that failure mode in testing.
The golden dataset schema will follow the structure given in the prompt, for example:

{
"query_id": "123e4567-e89b-12d3-a456-426614174000",
"query": "How does authentication work?",
"expected_spans": [
{
"span_hash": "sha256:abcd1234...",
"path": "auth/login.py",
"symbol": "authenticate_user",
"relevance_score": 1.0
},
{
"span_hash": "sha256:efgh5678...",
"path": "auth/token_service.py",
"symbol": "generate_jwt",
"relevance_score": 0.8
}
],
"ground_truth_answer": "Authentication uses JWT tokens issued at login. The
process is: ...",
"tags": ["auth", "security", "critical"],
"difficulty": "medium"
}
Each query gets a UUID for tracking. The expected spans list can include multiple relevant code pieces; in
the above example two functions are relevant, with one being absolutely critical ( relevance_score=1.0 )
and another somewhat relevant. The harness will treat any span with relevance_score > 0 as a true
positive for binary Precision/Recall, and could use the scores for weighted metrics like DCG. The
ground_truth_answer provides context for human evaluators (and could be used in future for automatic
answer checking via LLMs, though that’s outside our current scope due to avoiding external dependencies).
By having this curated dataset, we can perform consistent, reproducible evaluations. It effectively acts as
unit tests for the RAG system – if a code change or optimization causes a drop in performance on these
known queries, the harness will catch it. Over time, we’ll expand and refine the golden set to improve
coverage of LLMC’s capabilities.

Evaluation Harness Implementation
This section details how the framework will be implemented in code and integrated with the existing
system.

5

Language & Tools: We will use pure Python (for metrics and orchestration) and pytest for the test harness.
No external evaluation libraries are required beyond standard Python and possibly matplotlib or similar
for plotting in reports. The choice of pytest is motivated by simplicity and familiarity – developers can run
pytest -k eval locally to execute the eval suite, and CI can run it nightly. We will also implement a CLI
wrapper (as part of the llmc CLI tool) so that non-dev users can run llmc eval to generate a report
without dealing with pytest options.
Integration with LLMC Pipeline: The harness will likely call into existing scripts or modules to execute
queries. Since LLMC has a CLI ( llm_gateway.sh and possibly Python APIs in scripts/rag/* ), we have
options: - Use the LLM Gateway interface: e.g., call llm_gateway.js or codex_wrap.sh with flags to
simulate user queries. However, for fine-grained control (like forcing a particular tier or capturing outputs
programmatically), it’s better to call lower-level Python functions if available. - Leverage internal classes: If
the RAG system has classes like ContextQuerier or functions to retrieve spans (as seen in
query_context.py ), we can import and use them directly. Similarly, if there is a function to generate an
answer given context (the LLM call), that can be invoked directly with the model specified. - Alternatively,
use subprocess calls to the CLI for realism. But that complicates capturing intermediate data. Instead, we
might modify the code to log more details (e.g. log all retrieved span IDs in planner_metrics.jsonl ) so
we can rely on logs.
Given the need to measure retrieval metrics, we will ensure that during an eval run, all top-K retrieved
span identifiers are recorded. If the current logging only stores the top span and a count, we might extend
it to store a list of top span hashes. This could be added in a backward-compatible way (e.g. a new key
span_ids: [list,…] in planner_metrics.jsonl ). The harness can then read this after each query
to know exactly what was retrieved. If code changes are undesirable for now, an alternate approach is to
instrument the retrieval function in the harness (monkey-patch it to capture outputs). For the initial
implementation, a simple route is to parse the vector DB results directly by calling the ContextQuerier –
essentially duplicating what the system does, but in the test harness context where we can intercept the
results.
Running Evaluations: By default, llmc eval will run the entire golden suite with smart routing
enabled (to mimic real behavior). However, to support A/B testing and multi-model comparisons, the CLI
will allow parameters: - --tier local or --tier api or --tier codex to force all queries to use a
single tier model. This is useful to gather baseline metrics for each model (e.g. run all queries with Qwen-7B
vs with Qwen-14B vs with GPT-5-nano) for comparison. - --no-cache to disable any caching mechanism
(when caching is implemented) to ensure we measure fresh LLM calls. - --compare <config1.json>
<config2.json> to run two different configurations back-to-back and produce a comparative report. A
config JSON might specify settings like model, compression on/off, number of retrieved spans, etc., which
allows defining two experiment conditions. The harness would run the golden queries under each and then
use statistical tests to compare (details in A/B section). - --subset <tag> to run only queries matching a
certain tag or pattern (for faster debugging or focusing on a category of queries).
The harness will utilize existing logging as much as possible. After running, it reads

logs/

planner_metrics.jsonl and logs/enrichment_metrics.jsonl (which will have appended entries
for each query run) to extract the data. To isolate evaluation runs (so as not to mix with production logs),
the harness could direct the system to log to a separate location (e.g. set an env var to use logs/

6

eval_planner_metrics.jsonl for that run). Another approach is to timestamp each run and only read
log lines within that time window.
Performance and Cost Control: The implementation is mindful that evaluation should be efficient and
cheap. By using local Qwen models for most runs, we avoid incurring external API costs. We will likely
configure the router’s LLM (the one that makes routing decisions) to use a very cheap model or a local
heuristic for eval – or even bypass it entirely by deterministically routing in experiments (e.g. in a forced
local run, skip calling the router LLM). This not only saves cost but also makes eval results more
deterministic. If GPT-5-nano (or “Gemini 2.0 Flash” API) must be included, we will keep the query set
relatively small to cap the cost; moreover, the nightly CI could exclude the expensive model by default (only
run GPT-5-nano experiments on demand or weekly). In all cases, the cost per eval run is expected to be a
few cents at most (and <$1/month even with daily runs), satisfying the budget constraint.
Validation: We will write unit tests for the metrics functions (e.g., feed a known set of retrieved vs expected
spans and verify Precision@K is calculated correctly), and for the golden dataset loader (to ensure schema
compliance). These tests will reside in tests/eval/ and can be run as part of CI to ensure the evaluation
framework itself is reliable.
Finally, the harness will integrate with the existing workflow by adding a GitHub Actions job (see below)
and by including documentation (in README or a docs/ page) so developers know how to run it. The overall
implementation plan is greenfield (built from scratch) but informed by existing tools and patterns. For
instance, frameworks like LangSmith and RAGAS emphasize the importance of having both retrieval
metrics and answer quality metrics 15 5 ; while we are not using those frameworks directly (to avoid
external dependencies), our design takes inspiration from them and could integrate with them in the future
if desired. In summary, the harness will slot into LLMC’s toolkit as a natural extension, allowing continuous,
automated evaluation of the RAG pipeline’s efficacy.

A/B Testing Framework
A core objective is not only to measure absolute performance but also to facilitate A/B comparisons – for
example, comparing the current system with and without a new compression algorithm, or evaluating two
routing strategies. The evaluation framework supports this through both configuration and methodology:
• Configurable Experiments: As mentioned, the CLI can accept parameters or a config file to define a
run. We can represent an experiment as a set of system settings (e.g. {"compression": true,
"cache": false, "max_spans": 5, "router_model": "GPT-5-nano"} ) and a label. The
harness can run two (or more) configurations sequentially on the same golden queries and collect
metrics for each. All else being equal, differences in metrics can be attributed to the changed
setting.
• Isolation and Repeatability: Each experiment run will be self-contained. For instance, if comparing
caching vs no caching, we ensure that in the “no cache” condition, the system isn’t accidentally
benefiting from cache warmed in the other run. This might mean running experiments in separate
processes or clearing any in-memory cache between them. The harness will handle that (maybe by
restarting the context or using separate output log files).
• Statistical Significance: When comparing two strategies, we will compute the paired difference in
metrics per query where applicable. For example, for each query we can look at whether config A

7

returned the correct span and config B did, giving a set of outcomes. Statistical tests like McNemar’s
test (for binary success/failure comparisons) or a paired t-test (for metrics like tokens used per
query) can be applied to assess if the differences are significant at, say, p<0.05. Given our sample
size may be modest, we will be cautious and also rely on magnitude of improvement. For instance,
an increase of +5% Precision might not be significant on 50 queries, but +20% likely is. We will
highlight any differences beyond a certain threshold (like ±10%) as potentially meaningful even if
statistically borderline.
• Experiment Tracking: Each time an A/B test is run (especially in CI), we will record the results. This
could be as simple as committing a JSON summary of metrics for each config to a results directory,
or storing it as an artifact in CI. Over time, this builds a history of experiments. We can automate
comparison against the last main-branch run as the “B” in an A/B test for every pull request: i.e.,
treat the new code as A, baseline as B, and report if A is better or worse.
• Router Strategy Comparison: One specific use-case is to evaluate different routing LLM prompts
or thresholds. For example, maybe we have a new prompt for the routing LLM that is supposed to
better classify tasks. We can run one set where the router uses the old prompt, and one with the new
(this might require a slight interface to plug in different router behaviors – possibly by mocking the
router’s output or by actually using two different routing models). We then compare tier usage,
success rates, and cost. If the new strategy successfully keeps more queries on the cheaper local tier
without loss of quality, the metrics will show improved cost per query and similar precision – an ideal
outcome. If it under-routes (too many locals leading to missed answers), the recall/precision will
drop, which the harness would flag.
• Multiple Configs (A/B/C): While A/B usually implies two, our framework can generalize to multiple
variants if needed (though we must be careful to control variables). For example, we could compare
Qwen-7B vs Qwen-14B vs GPT-5-nano in one go (that’s effectively multi-model benchmarking). The
output would list metrics for each. In terms of significance, we’d likely do pairwise comparisons or
simply present the numbers and perhaps recommend an optimal choice (e.g. “GPT-5-nano gave
highest recall but at 2x cost of Qwen-14B – depending on priorities, one might choose differently”).
To implement A/B in code, the harness.py could have a function like run_experiment(config) ->
metrics and then a small loop to run for each config in a list. The results can then be passed to a
reports.compare_results(metrics_A, metrics_B) function which produces a diff report or overlay
charts.
The framework will also integrate with version control or CI in a basic way: for example, if a developer
pushes a branch with a proposed optimization, the nightly eval on that branch (or a PR-triggered eval) could
automatically compare its metrics to the last nightly on the main branch, and perhaps comment on the PR
with the comparison. This encourages data-driven merges (if the new code regresses metrics, we’d think
twice unless there’s a known trade-off).
In summary, the A/B testing capabilities ensure that we can experimentally validate each token optimization
technique’s impact. Instead of guessing, we can concretely say e.g. “Cache X reduced average tokens by
20% with no loss in Precision@3 13 ” or “The new compression scheme improved context waste ratio from
30% to 10%, boosting recall by 5 points.” Such statements will be backed by the automated eval data.

8

Regression Detection
One of the primary motivations for this framework is to catch regressions early, ideally before they hit
production. The design includes multiple layers of regression detection:
• Threshold-based Alerts: We will define clear thresholds for critical metrics. For example:
Precision@5 should not drop more than 5% relative to the baseline; average tokens per query should
not increase more than 10%; planner confidence calibration error should not worsen significantly.
These thresholds can be encoded as assertions in the test suite. For instance, after computing
metrics, a pytest test could assert assert current_metrics['Precision@5'] >= 0.95 *
baseline_metrics['Precision@5'] (if baseline is known). If this assertion fails, the CI run fails,
immediately flagging the regression.
• Baseline Management: We need a point of reference for regression checks. Initially, we might use a
static baseline (like metrics from the last release or a manually curated ideal). However, since the
system will hopefully improve over time, we likely treat the latest main branch metrics as the
baseline for new changes. We can store the last nightly main metrics in a JSON file (committed to the
repo or accessible to CI) and have the test harness load it when running on a feature branch. This
way, each run knows what “previous performance” was. In cases where improvements occur, we
update the baseline accordingly.
• Adaptive Gates: Some metrics might improve and we want to lock in that improvement. For
instance, if a new feature raises Precision@5 from 60% to 70%, we don’t want later changes to
silently slip back to 60%. We would adjust the baseline or threshold upward. A process will be
defined for updating these guardrails – likely via code review: e.g., when a PR intentionally improves
a metric, the PR can also update the expected baseline values in the test assertions.
• Automated Notifications: Failing the CI test is one mechanism, but we can make it more visible.
The GitHub Actions workflow can be configured to post a comment on the pull request or send a
Slack notification if an eval failure occurs on main. For nightly runs, if a regression is found, we could
have the action create a GitHub Issue or at least output a summary in the logs. Because we parse
metrics in a structured way, the workflow can even include a snippet like “ Regression detected:
Recall@10 dropped from 85% to seventy 75% (threshold 77%) on commit abc123” for quick visibility.
• Historical Trend Tracking: In addition to point-in-time regression checks, we’ll maintain a history of
metrics over time (could be simply a CSV or JSON appended each night). This allows trend analysis –
e.g., if answer latency or token usage has been creeping up over two weeks, we might want to
address it before it crosses a hard threshold. A simple script can plot metric values over date; more
advanced, we could integrate with a dashboard or monitoring tool if available. But even embedding
a chart of the last N runs in the report can help visually catch slow regressions that single-run
thresholds might miss.
• Zero-Tolerance Checks: Some failures are binary – e.g., if any golden query that used to succeed
now fails to retrieve the needed span, that’s a regression. We will treat any previously passing query
now failing as a high-severity regression (unless the golden set was updated). The harness can track
per-query outcomes and compare with previous outcomes. If a query’s Precision@K was 1 (it found
the answer) and now it’s 0, that’s a clear red flag. This is essentially a unit-test-like behavior: each
golden query ideally always passes unless intentionally changed.
• Controlled Environment: To avoid false alarms, we ensure the eval environment is consistent. The
vector DB should be the same snapshot of code for each run (the CI can rebuild the index nightly
from the repo). Randomness in LLM outputs could cause variance, but since we use local
deterministic models or set random seeds, the output should be stable. If using any non-

9

deterministic component (like an external model), we might run multiple trials or use moderate
thresholds to account for variance.
By combining these strategies, the framework will act as an early warning system. A developer will be
alerted within 24 hours (or immediately on PR CI) if their change negatively impacted the RAG pipeline’s
performance. This encourages quick iteration to fix the issue or to adjust the system. Moreover, having a
documented baseline of expected performance means we’re effectively putting quality gates in place –
LLMC’s pipeline cannot drift beyond certain bounds without detection.

Reporting & Visualization
The final output of the evaluation harness is a report that synthesizes all the findings for easy consumption
by engineers and product stakeholders. We outline the reporting features and format:
• Metrics Summary Tables: The report will start with a table of key metrics for the latest run (and
possibly a comparison to baseline). For example:
Metric

Current Run

Baseline (Last week)

Change

Precision@5

0.68

0.65

+0.03

Recall@5

0.50

0.48

+0.02

NDCG@5

0.72

0.70

+0.02

MRR

0.60

0.58

+0.02

Avg Tokens per Query

1200

1300

-100

Cost per Query (USD)

$0.00050

$0.00055

-9%

Context Waste Ratio

15%

25%

-10%

Tier1/2/3 Usage (% Qs)

80 / 15 / 5

75 / 20 / 5

-

Escalation Rate (% Qs)

5%

8%

-3pp

The table highlights improvements or regressions (e.g. bold for notable changes). This gives a quick at-aglance view.
• Detailed Breakdowns: Subsequent sections of the report dive deeper. For instance, a section on
“Retrieval Quality” will list the Precision and Recall at various K (maybe K=1,3,5,10) and could even list
query-by-query results (or at least the hardest queries). If certain queries had zero recall (missed
completely), we can list them here under a “Failures” subsection for inspection.
• Visual Plots: We will include a few key charts:
• Precision/Recall Curve: A line chart showing Precision@K vs Recall@K as K increases (like an IR
trade-off curve). This can illustrate how performance changes if we allowed more context (e.g.,
Precision drops as we include more spans, but recall increases). It helps decide an optimal K for
retrieval.
• Cost-Quality Frontier: Perhaps the most insightful – we can plot points representing different
configurations (7B vs 14B vs GPT-5-nano, or routing on vs off) on a graph of Cost (x-axis) vs Quality

10

(y-axis, say Precision or Recall). Ideally, our optimizations move the point towards bottom-right
(lower cost, higher quality). The Pareto frontier would connect the non-dominated configurations
14 . For example, one point might be (cost $0, Precision 0.6) for all-local, another (cost $0.0005,
Precision 0.7) for hybrid, another (cost $0.002, Precision 0.75) for all-codex. This visualization helps
justify if a more expensive model is worth the marginal gain in quality.
• Tier Usage Pie/Bar: A pie chart or bar graph showing what fraction of queries went to each tier
(Local, API, Codex). If we run multi-model comparisons, perhaps a stacked bar per model showing
how many queries were answered correctly vs needed escalation. This ties to the “Tier efficiency”
metric but in visual form.
• Confidence Calibration Plot: If feasible, a plot with confidence on x-axis and actual success
probability on y-axis (perhaps with error bars). A perfectly calibrated planner would lie on the
diagonal line y=x. This can reveal if the planner is overconfident or underconfident on average.
• Trend Graphs: If we have historical data, a time series line chart of a few metrics (Precision, cost,
etc.) over past weeks. This can be placed in an appendix or the online dashboard, but even a simple
sparkline in the report can be useful to see trajectory.
• Findings and Recommendations: The report will also include short textual analysis highlighting
notable results. E.g., “Finding: The new compression algorithm reduced context waste from 25% to
15%, leading to a slight increase in recall. However, precision remained roughly constant, indicating
the extra context was mostly relevant. Recommendation: Keep compression enabled and consider
increasing K to leverage freed token budget for possibly more recall.” This kind of commentary can
guide the team on next steps.
• Drill-down for Errors: For any queries where the system failed (didn’t retrieve something it should
have, or gave a wrong answer where we expected a certain answer), we provide a brief case study.
For example: Query: “How are JWT tokens generated?” – Expected span: auth/
token_service.py::generate_jwt – Retrieved: None in top 5. This indicates a recall failure;
maybe the embedding missed it. Such granular detail can be extremely useful for debugging (maybe
it turns out the code had a different terminology, etc.). We might limit this to the top N failures to
keep report concise.
• Format and Access: The primary format will be Markdown (for easy viewing in GitHub) and possibly
an HTML artifact for the CI. If using Markdown, we can include the charts as embedded images (the
GitHub Action can upload the chart images and embed links). Since the instructions mention
embedding images only if we have them, we will generate charts as PNGs and reference them
appropriately in the Markdown report. The report could be committed to a
docs/eval_report.md or posted as a PR comment.
• Automation: The nightly GitHub Action ( nightly_eval.yml ) will run llmc eval , collect the
output report and metrics, and perhaps push the report to a branch or store as an artifact. It can
also use the GitHub API to comment on any recent commits if regressions are found. Over time, we
might integrate this with Slack or email for critical alerts, but that’s optional.
The emphasis is on making the results easily interpretable. We want to lower the barrier for developers to
understand how a code change affected the RAG system. The combination of numeric metrics and visual
aids will cater to both detailed analysis and quick high-level overview.
In conclusion, this evaluation and benchmarking framework will enable continuous improvement of LLMC’s
RAG pipeline by providing clear, quantifiable feedback on every optimization. It ensures that token usage
optimizations truly pay off in either reduced costs or improved quality (or ideally both), and that any
degradation in performance is caught and addressed promptly. By drawing inspiration from existing best-

11

in-class RAG evaluation tools while tailoring to our specific system, we get the best of both worlds: a
custom, lightweight solution with rigorous metrics 5 6 .

Code Structure & Workflow Integration
Following the design above, below is the proposed code layout for implementing the evaluation harness
within the repository:

scripts/eval/
├── __init__.py
├── golden_dataset.py

# Loading and validating the golden dataset JSON/YAML

├── metrics.py
MRR, etc.)

# Metric computations (Precision@K, Recall@K, NDCG,

├── harness.py

# Core harness logic: running queries, controlling

tiers, collecting logs
├── regression.py
detecting regressions

# Functions for comparing metrics to baseline and

├── reports.py
assembly)

# Report generation (tables, charts, Markdown

└── cli.py
or argparse

# `llmc eval` CLI entry point, integrates with Click

tests/eval/
├── test_metrics.py
dummy data)

# Unit tests for metrics calculations (using small

├── test_golden_dataset.py

# Tests for golden dataset schema and loading

├── test_harness.py
# Tests for harness end-to-end on a tiny sample
dataset (possibly using a stub model)
└── test_confidence_calibration.py # Tests specifically for confidence
calibration logic (could simulate planner outputs)
.github/workflows/
└── nightly_eval.yml
# GitHub Actions workflow that triggers nightly (or
on demand) to run the eval and publish results
Module Descriptions: - golden_dataset.py : Contains the GoldenDataset class or methods to read
the golden dataset file. It will verify required fields for each query and possibly provide helper methods to
filter queries by tag or difficulty. It may also hold the path to the dataset file (e.g. data/
golden_queries.json ).

-

metrics.py :

Implements

functions

like

precision_at_k(retrieved_list, expected_list, k) , recall_at_k(...) , ndcg_at_k(...) ,
etc., as well as token efficiency calculations. Likely also has a
golden_data)

compute_all_metrics(run_logs,

that orchestrates computing all metrics from a run’s logs or results in memory. -

harness.py : This is the heart of the evaluation runner. It might define a class EvalHarness that takes
configuration (which model tiers to allow, etc.) and has a method run_all(golden_data) -> results .
Internally it will: - Loop through each query, call the RAG system (perhaps via a helper function that

12

encapsulates the query workflow). - Capture outputs and log data for that query in memory (we might
structure it as a dictionary per query with fields like retrieved_spans , used_tier , tokens_used ,
success etc.). - Optionally, it could also directly compute per-query metrics on the fly. - Ensure any
needed cleanup (clear caches, etc.) per iteration. - regression.py : Provides utilities to load baseline
metrics (e.g. from a file or previous run) and compare with new metrics. This could include functions for
statistical tests or simple threshold checks. It could return a summary of any regressions found (to be
consumed by reports or CLI for exit codes). - reports.py : Handles assembling the final report. It might
use templates for Markdown. For plotting, it could use matplotlib or plotly to generate charts saved to
logs/ or a temp folder, then reference them in the Markdown. This module focuses on presentation:
formatting percentages, highlighting changes, sorting outputs by worst cases, etc. -

cli.py : Ties

everything together. Likely uses Python’s argparse to parse options (or integrates into an existing CLI
framework if llmc has one). It will load the golden dataset, instantiate the harness with given options, run
the evaluation, get metrics, perform regression checks, generate the report, and finally print a summary to
console (and write report to a file). It will also set the process exit code to indicate success or failure (which
CI can use to mark the run pass/fail).
Testing: Under tests/eval/ , we will write tests for each piece: - test_metrics.py : e.g., test that
precision_at_k yields 1.0 when all retrieved are relevant, or yields correct fractions in known scenarios.
Also test NDCG with a toy relevance list. - test_golden_dataset.py : create a sample JSON in a temp file
and ensure our loader catches missing fields or bad formats (like non-unique IDs). - test_harness.py :
This one might use a mock RAG pipeline to simulate responses, because running the actual LLMs in a unit
test isn’t feasible. We can monkey-patch the call that queries the LLM to instead return a canned answer
and likewise stub the vector search to return predetermined spans. This way we can simulate a scenario
and ensure the harness correctly logs and captures it. For example, simulate a query where the retriever
returns spans A and B, expected answer uses A – then verify the harness’s results indicate a success. test_confidence_calibration.py : Could test our bucketing logic or a synthetic scenario to ensure
the calibration metric is computed as expected.
Workflow (nightly_eval.yml): This GitHub Action will likely: - Check out the repo, set up environment
(perhaps needs to install dependencies like sentence-transformers for embedding if not vendorized, and
ensure the Qwen model weights are present or can be pulled). - Possibly start up any services (if vector DB
is needed, e.g., ensure Chroma index is built – though we might use an in-memory index for eval). - Run
python -m scripts.eval.cli (or the equivalent llmc eval command). - Archive the resulting
report (as an artifact or commit to a branch, depending on the desired approach). - If failures, mark the job
as failed. Also, use regression.py output to possibly add annotations or messages.
Because the evaluation should run in <5 minutes locally (as per success criteria), we ensure efficiency by
limiting to, say, 50 queries and using local models. On CI, we might run on self-hosted runners with a GPU
for Qwen, or use CPU with quantized models if needed (Qwen-7B might run on CPU moderately okay for
small usage). We can also utilize the smaller “Qwen 2.5B” if available for faster run, since it’s mainly retrieval
we care about; however, for fidelity, using the same models as production is ideal.
In essence, this code structure cleanly isolates the evaluation code from production code, while still
leveraging the production pipeline where possible. The introduction of this scripts/eval module does
not interfere with runtime logic (it’s an additive test suite), thus maintaining the integrity of the system. By
placing it under scripts/ , we signify it’s a first-class tool for the project (not just tests).

13

With this framework in place, LLMC’s team will gain a powerful feedback loop: every day, they’ll know
exactly how their RAG pipeline is performing and where to focus improvements, supported by empirical
data and clear visualizations. This closes the loop between development and validation, ensuring the RAG
system continually moves toward an optimal cost-quality equilibrium. 14 5

1

2

3

4

5

7

8

9

10

11

12

13

14

RAG Evaluation: Don’t let customers tell you first | Pinecone

https://www.pinecone.io/learn/series/vector-databases-in-production-for-busy-engineers/rag-evaluation/
6

How do RAG evaluators like Trulens actually work? : r/LangChain

https://www.reddit.com/r/LangChain/comments/1lvevo2/how_do_rag_evaluators_like_trulens_actually_work/
15

The 5 best RAG evaluation tools in 2025 - Articles - Braintrust

https://www.braintrust.dev/articles/best-rag-evaluation-tools

14

