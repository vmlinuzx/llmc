# Knowledge Graph Authority Engine Implementation SDD

Knowledge Graph Authority Engine
Implementation SDD
1. Executive Summary
Problem: Large Language Models (LLMs) in our system frequently hallucinate factual details – e.g.
inventing API endpoints, version numbers, or relationships – and waste tokens by repeatedly asking for
known facts. Retrieval-Augmented Generation (RAG) helps by providing context, but unstructured text
snippets can themselves contain errors or outdated info, and LLMs still lack a guaranteed source of truth.
This leads to inaccuracies and inefficiencies.
Solution: Integrate a Knowledge Graph (KG) as a deterministic authority engine alongside the LLM
orchestration. A knowledge graph is a structured network of factual entities, their attributes, and
relationships. By querying this graph directly for facts, the system can provide 100% reliable answers for
structured queries, eliminating hallucinations. The KG will store authoritative data (from documentation,
APIs, etc.) such as API endpoints, configuration values, product categories, and known relationships
(dependencies, requirements) in a queryable form. LLM agents will use the KG for facts instead of relying
solely on prompts or vector search.
Expected Outcomes: - Zero Fact Hallucinations: All facts (endpoints, versions, etc.) are retrieved from the
KG, which is populated from trusted sources. This ensures factual accuracy in LLM responses 1 2 . Reduced Token Usage: Instead of consuming hundreds of tokens to recall or double-check a fact, agents
make a lightweight graph query (no tokens) and get the answer directly. We anticipate a significant token
reduction (20–30% on queries that involve factual lookups). - Complex Multi-Hop Reasoning: The KG
enables agents to answer complex questions by traversing relationships (e.g. understanding that Skew-T
requires atmospheric data which comes from a specific API). This structured reasoning was previously
difficult with plain RAG 3 . - Seamless Integration: The KG will work in tandem with existing RAG and
caching layers – using the KG for definite facts and the RAG (vector database) for explanatory or
unstructured context. The LLM Commander’s agents (Beatrice, Otto, Rem) will be orchestrated to first query
the KG for facts, then use RAG for additional context if needed, combining both in their final responses.
In summary, by introducing a knowledge graph as an authority, we transform our LLM system from a purely
probabilistic engine to a fact-grounded intelligent assistant. This hybrid approach of KG + RAG (inspired
by emerging techniques like GraphRAG from Microsoft Research) will improve accuracy, provide up-todate authoritative information, and reduce hallucinations in AI-generated content 4 . It leverages
the strengths of structured knowledge without sacrificing the rich context that the unstructured data and
LLM reasoning provide.

1

2. Technical Background
Knowledge Graphs: A knowledge graph is a structured representation of information composed of nodes
(entities/concepts) and edges (relationships) connecting them. Each node or edge can have properties
(attributes) that store factual data. Unlike a relational DB, a KG explicitly emphasizes connections, enabling
efficient multi-hop traversal of relationships 5 . For example, in a KG, one can easily ask “Which API provides
atmospheric sounding data?” and traverse from a Weather Data node to its provider API node via a
provided_by relationship.
Why KGs for LLMs: Integrating KGs with LLM systems addresses key shortcomings of pure LLM or vectorbased approaches: - Factual Grounding: Knowledge graphs serve as an up-to-date, curated fact repository.
They reduce AI hallucinations by providing a source of truth the LLM can rely on 6 2 . Instead of the
LLM guessing an answer, it retrieves the fact from the graph. - Complex Reasoning: KGs excel at
representing and querying complex relationships. Microsoft’s GraphRAG approach demonstrated that
extracting a knowledge graph from textual data and using it in RAG yields substantial improvements in
answering multi-hop and complex queries 7 . Graph traversal allows connecting disparate info (e.g.,
linking a tool to its prerequisites to their data sources) which plain vector search might miss 8 . - Authority
and Determinism: By treating the KG as an authority, we implement an “authority engine” pattern: the
LLM never invents critical facts – it must retrieve them. The KG acts as the highest authority for static facts,
followed by live APIs (for dynamic data), then documentation (RAG), and finally the LLM’s own reasoning as
a last resort. This hierarchical approach ensures deterministic answers for things the KG knows (like a config
value or endpoint). - Real-World Examples: Industry leaders blend KGs with AI: Google’s Knowledge Graph
powers the factual info in search results and assistants (improving search accuracy and multi-hop query
handling 9 ), and platforms like LinkedIn and Amazon use product or social graphs to enhance
recommendations and Q&A. These show that KGs provide structured context that LLMs/AI can leverage for
better accuracy 10 11 .
GraphRAG and Hybrid RAG: GraphRAG (Graphs + RAG) from Microsoft Research is a technique that uses an
LLM to build a knowledge graph from a text corpus and then uses that graph to aid retrieval and reasoning
3 . It improves upon baseline RAG (which uses only vector similarity search) by adding structure – leading
to better performance on complex questions that require connecting multiple pieces of information 8 . In
our design, we adopt a similar philosophy but with a deterministic spin: our KG is curated for correctness,
rather than entirely LLM-generated. We will use the graph to answer factual queries and to guide retrieval
of relevant text. This can be seen as a hybrid approach: VectorRAG for unstructured data + Knowledge
Graph for structured data, combining the strengths of both. Recent evaluations (e.g., by NVIDIA) show
that such Hybrid RAG methods can offer a balanced improvement, with graph-backed retrieval excelling in
correctness 12 .
Authority Engine Pattern: The knowledge graph implementation embodies an “authority engine” design:
it establishes a hierarchy of information sources by trust level. The LLM or agent must consult higherauthority sources first: 1. Knowledge Graph – highest authority for curated facts (zero ambiguity). 2. Live
APIs/Databases – authoritative for real-time data (e.g., current weather, latest values). 3. Documentation
via RAG – secondary source, used if the fact isn’t in KG (might contain more detail but could be outdated). 4.
LLM Internal Knowledge – last resort, used only for reasoning or if all else fails (and even then, any critical
fact from LLM is treated with low confidence).

2

By always preferring the KG or other deterministic tools for factual info, we ensure the LLM primarily
contributes language generation and reasoning, not raw fact production. This pattern has been proposed
as a way to eliminate hallucinations – the LLM becomes an orchestrator of knowledge sources rather than
an all-knowing oracle 2 . Our system will log any conflicts (e.g., if an LLM answer disagrees with the KG)
and always side with the highest-authority source, thus maintaining consistency.
In summary, the technical foundation for this project is the synergy of knowledge graphs with LLMs to
create a system that is grounded, accurate, and capable of sophisticated reasoning. The rest of this
document details the design of this Knowledge Graph Authority Engine, including technology comparisons,
schema design, integration points, and implementation strategy.

3. Knowledge Graph Solution Comparison
There are many graph database technologies available. We evaluated several options to find the best fit for
integrating into our LLM Commander framework. The main contenders include both native graph
databases (optimized solely for graph data) and multi-model databases (which support graph along with
other data models), as well as embedded solutions. Below is a comparison of the key solutions across
various criteria:

3.1 Comparison Matrix
The table below compares the graph database options on setup effort, query language, performance/
scalability, developer experience, and cost/licensing. All options considered are capable of storing property
graphs (nodes with properties and typed relationships).

Graph DB

Neo4j

Model & Query

Native property
graph; Cypher
query language
13 .

Setup
Complexity

Performance
& Scalability

Developer
Experience

Cost/
Licensing

Easy start
(one-click
desktop or
Docker);
requires Java
runtime.

Good singlenode
performance;
enterprise
clustering for
scale (billions
of nodes);
ACID
transactions.

Excellent
docs, tools
(Neo4j
Browser,
Bloom);
largest
community
13 .

Community
Edition free;
Enterprise
paid (or
AuraDB cloud
subscription).

3

Graph DB

MemGraph

ArangoDB

Amazon
Neptune

Setup
Complexity

Performance
& Scalability

Developer
Experience

Cost/
Licensing

Native property
graph (Cypher);
in-memory.

Very easy
(single
binary or
Docker);
minimal
config.

In-memory
storage ->
extremely fast
on < millions
of nodes; can
handle
streaming
data in realtime, but
limited by
RAM 14 ;
single-node
(no native
sharding in
community).

Dev-friendly,
focuses on
real-time use;
Cypher
support
means low
learning curve
15 ; smaller
but growing
community.

Community
Edition free
(opensource);
Enterprise
adds
clustering
(paid).

Multi-model
(graph +
document + key/
value); AQL query
(SQL-like).

Moderate:
install
service or
Docker;
more
components
due to multimodel.

Decent
performance
for mid-sized
graphs; not as
optimized as
native DBs for
deep graph
analytics; can
form clusters
in enterprise.

Good docs;
requires
learning AQL
(similar to
JSON/SQL);
flexibility to
use document
store and
graph in one
system 16 .

Open-source
Community;
Enterprise for
cluster
features
(commercial).

Easy (fully
managed
AWS
service);
virtually zero
setup, but
AWS-only.

High
scalability via
AWS scaling
(can handle
100M+ nodes/
edges);
~millisecond
query latency;
multi-AZ HA.
Some queries
(Gremlin) can
be slower on
very large
traversals.
ACID
compliance on
single cluster.

No
installation
needed; uses
standard APIs
(Gremlin,
SPARQL) – but
less tooling
(no built-in UI,
rely on AWS
console or
third-party).
Integration
with AWS
ecosystem is
seamless 17 .

Proprietary
cloud service;
pay-as-you-go
( ~$0.10/hour
+ storage)
18 , which
can be costly
at scale.

Model & Query

Cloud-managed
graph DB;
supports
Property
(Gremlin/
OpenCypher) and
RDF (SPARQL)
APIs 17 .

4

Graph DB

JanusGraph

TigerGraph

Model & Query

Distributed
property graph;
TinkerPop/
Gremlin query.

Native parallel
graph; GSQL
query language.

Setup
Complexity

Performance
& Scalability

Developer
Experience

Cost/
Licensing

High
complexity:
deploy
distributed
backend
(Cassandra/
HBase +
Elastic/Solr
index).
DevOps
heavy.

Designed for
very large
graphs
(hundreds of
billions of
nodes) 19 ;
horizontally
scalable via
backend
store. Trades
some latency
for massive
scale. Gremlin
queries can be
complex to
optimize.

Steep
learning curve
(TinkerPop
stack); limited
UI – mostly
code and
REPL. Open
source
community
support
(active but
smaller), no
official
enterprise
support
(communitydriven).

Open-source
(Apache 2.0)
19 ; no
license cost,
but requires
infrastructure
(multiple
servers/
nodes).

Moderate to
High:
enterprise
software –
setup via
AWS/GCP
marketplace
or on-prem
installer.
Freemium
single-node
available.

Highest
performance
on complex
analytics –
parallel
execution
yields fast
multi-hop
queries (10+
hop deep
traversals in
real-time) 20
21 . Scales via
built-in
distributed
clustering and
partitioning.
Meant for
enterprisescale data and
real-time
analytics.

Steeper
learning curve
(GSQL is
unique);
smaller
community
than Neo4j.
Has a visual
IDE
(GraphStudio)
for modeling.
Enterprisefocused
features.

Enterprise
product
(paid); a free
tier or dev
license exists,
but full
features
require
subscription.

5

Graph DB

SQLite +
Graph Ext

Model & Query

Embedded
SQLite with
openCypher
extension (e.g.
sqlite-graph
module).

PostgreSQL
+ AGE

Relational+Graph
hybrid; Apache
AGE extension
(PGQ/Cypher
query) 23 .

Setup
Complexity

Performance
& Scalability

Developer
Experience

Cost/
Licensing

Low: simply
load
extension
into SQLite;
no separate
server. Still
alpha-level
software
22 .

Meant for
lightweight
use: suitable
for thousands
of nodes/
edges. Inmemory or
file-based.
Performance
good for local
small graphs,
but not
optimized for
large-scale
traversals. No
network
overhead
(runs inprocess).

Familiar
environment
(SQLite) and
Cypher query
22 ; but
tooling is
minimal (no
visualization
except
custom).
Good for
prototyping,
not yet
productionhardened.

Open-source
(in
development)
22 . No extra
cost. Uses
existing
SQLite (free).

Moderate:
requires
PostgreSQL
and
installing
the AGE
extension.
Uses SQL
and Cypher
mix.

Leverages
PostgreSQL’s
robustness for
storage/
transactions.
Suitable for
moderatesized graphs
integrated
with relational
data.
Performance
acceptable for
<= millions of
edges, but for
very deep
graph
analytics a
native graph
DB may
outperform.

Benefit:
existing
PostgreSQL
ecosystem
(tools,
familiarity).
Cypher
queries via
SQL functions.
However, not
as many
graph-specific
optimizations
as dedicated
DB.

PostgreSQL is
open-source;
Apache AGE is
open-source
23 . No
license cost;
can use
existing
Postgres
deployments.

Notes: All solutions above support ACID transactions to some degree (Neo4j, MemGraph, ArangoDB,
PostgreSQL are fully ACID; Neptune is ACID within a cluster; JanusGraph relies on backend consistency –
usually eventual with Cassandra, but can tune). For our use case of moderately sized, mostly read-heavy

6

knowledge graphs (likely on the order of 1k–100k nodes), a single-node solution is sufficient initially. The
choice will balance ease of integration with our current stack, performance, and future scalability needs.

3.2 Recommendations by Scenario
Different projects have different needs. Based on the comparison, we recommend the following graph
solutions in various scenarios:
• Solo Developer / Local-First Project: Simplicity and zero-cost are paramount. Use SQLite with a
graph extension or an embedded solution. This keeps everything in-process with minimal
overhead. For example, the sqlite-graph extension allows using Cypher queries directly in a
local SQLite database 22 . This is perfect for a lightweight knowledge graph on a single machine and
avoids running a separate server. Alternatively, a local Neo4j Community Edition is a good choice if
a more mature platform is desired – it’s easy to install and comes with a user-friendly browser UI for
inspecting the graph. Both options are free.
• Small Team / Moderate Scale: Balance ease of use and capability. Neo4j (Community) or
MemGraph are excellent here. Neo4j offers a proven platform with extensive documentation and
community support 13 , which helps onboard the team quickly. MemGraph, on the other hand,
might be chosen if real-time analytics on streaming data is a requirement, thanks to its in-memory
design 14 . Both use Cypher, so the learning curve is low. If the team’s data also includes non-graph
aspects (documents, key-value), ArangoDB could be considered for its multi-model flexibility, letting
you use one DB for multiple data types – but at some cost of graph query performance. All these are
open-source or have free versions, keeping costs down.
• Enterprise / High Scale Deployment: Need to handle large graphs, high throughput, or multi-region
data. For enterprises, Neo4j Enterprise (clustered) is a robust choice – it provides clustering,
monitoring, and enterprise security. Alternatively, Amazon Neptune is attractive if the infrastructure
is on AWS: it’s fully managed, scales well, and supports open query languages 17 , meaning minimal
ops effort. For organizations dealing with massive data (hundreds of millions of relationships) and
complex graph analytics, TigerGraph might be recommended due to its superior performance on
deep link analysis 20 , but it requires commitment to a proprietary stack. If an open-source but
distributed solution is preferred, JanusGraph with a backend like Cassandra can scale horizontally –
though the operational complexity is high, it has been used in scenarios with billions of edges. The
choice here may also depend on existing infrastructure: e.g., if the company already uses AWS,
Neptune integrates naturally; if they want cloud-agnostic and open, Neo4j or Janus on Kubernetes
might be better.
• Multi-tenant SaaS Platform: Isolate data per tenant and ensure scalability. A multi-tenant system
might leverage either Amazon Neptune (each tenant’s graph on a separate Neptune cluster or
separated by RDF named graphs) or a Neo4j AuraDB instance per tenant (Neo4j’s cloud service) for
strong isolation. Another approach is using a single cluster and partitioning the graph by tenant, but
that can complicate queries and security. If using PostgreSQL already for core data, Apache AGE on
PostgreSQL could be considered, creating a separate graph namespace per tenant within the
relational DB – this leverages existing infrastructure and ensures ACID consistency for each tenant’s
data. Key is to ensure one tenant’s queries can’t leak data from another; solutions with built-in multitenancy support or easy horizontal scaling (Neptune, Aura) are preferable. Cost considerations are

7

significant here: a shared cluster approach is cheaper but riskier, whereas per-tenant isolation via
managed services costs more but offers peace of mind.
In general, for our current project needs (LLM Commander integration), the graph will likely start
modest in size and be operated by a small team. Thus, the initial recommendation is to use Neo4j
Community Edition for development (ease of use, rich ecosystem), possibly switching to Neo4j AuraDB or
MemGraph in production depending on performance needs. We also keep an eye on the SQLite graph
extension progress – if it matures, it could enable an embedded, lightweight deployment perfectly aligned
with our existing SQLite-based RAG store, avoiding the need for additional servers.

4. System Architecture
The Knowledge Graph authority engine will be integrated into the existing LLM Commander architecture.
This section describes the high-level architecture and the specific components introduced or affected by the
KG integration.

4.1 High-Level Architecture Diagram
Below is a conceptual flow of how a user’s query will be processed in the new system, highlighting the role
of the Knowledge Graph alongside the Retrieval-Augmented Generation (RAG) pipeline:

User Query
↓
┌──────────────────────────────────────────┐
│

Query Classifier

│

│

- If fact-based query → use KG

│

- If context/explanation query → use RAG│

│

- If mixed/complex → use KG + RAG

│
│

└──────────────────────────────────────────┘
↓

↓

↓

┌─────────────┐

┌─────────────┐

┌─────────────┐

│ KG Query

│ RAG Query

│ Hybrid

│

│

│

│ (structured │

│ (unstructured│

│ (both KG & RAG) │

│

│

│

facts)

│

└─────────────┘
↓

context)

│

└─────────────┘

│

└─────────────┘

↓

↓

┌──────────────────────────────────────────┐
│

LLM Agent (Beatrice/Otto/Rem)

│

│

- Receives facts from KG (if any)

│

│

- Receives context from RAG (if any)

│

│

- Integrates both into final answer

│

└──────────────────────────────────────────┘
In this design: - A Query Classifier examines the user’s question to decide how to route it: - If it’s a
straightforward factual question (“What is the endpoint URL for NOAA RAP API?”), it will query the

8

Knowledge Graph only. - If it’s an open-ended or explanatory question (“How do I implement a Skew-T
diagram?”), it will use RAG (vector search over documentation/code) primarily, but also likely do a hybrid
retrieval (KG to gather required facts, RAG for examples and explanation). - Many real questions are hybrid:
e.g. “Explain how to use the NOAA API for atmospheric soundings.” The classifier might trigger both: use KG to
fetch the API endpoint and parameters, and RAG to fetch a code snippet or usage explanation. - The KG
Query path means hitting the graph database with a structured query (likely via Cypher or an API call) to
get entities/relationships that answer the question. - The RAG Query path means doing the usual vector
similarity lookup in our .rag/index.db (or via a vector store) to retrieve relevant text chunks. - The
Hybrid path will orchestrate both: first get relevant facts from KG, use those facts to formulate a better RAG
query (for example, including key entity names or IDs in the search), then retrieve additional context from
RAG. - The LLM Agent (one of our multi-agent ensemble, e.g. Beatrice using GPT-based model or Otto with
Claude) then receives a prompt that includes: - The factual results from the KG (e.g. “NOAA_RAP_API
has_endpoint https://nomads.ncep.noaa.gov/...; Skew-T requires atmospheric_sounding data format,
provided by NOAA_RAP_API…”) - The contextual paragraphs from RAG (e.g. a snippet from documentation
on how to fetch data, or code using D3.js to plot Skew-T) - The agent’s job is then much easier: it doesn’t
need to guess facts, and can focus on explanation or planning using the given information.
This architecture ensures the LLM’s output is grounded in both structured and unstructured
knowledge. By splitting queries appropriately, we avoid using expensive LLM calls for questions that have
deterministic answers, and we avoid feeding large chunks of text when a simple fact would do.

4.2 Component Diagram & Responsibilities
To implement this, several components (new or enhanced) are in play:
• Knowledge Graph Store: The graph database holding our knowledge graph. For example, a Neo4j
instance or an embedded graph DB. This stores nodes (entities) and edges (relationships) with
properties. It provides an interface (Cypher queries or equivalent API) to retrieve and update data.
We will design the schema (ontology) for this store in Section 5. The KG store is the backbone for
storing authoritative facts.
• Graph Query Engine: This is the layer that accepts queries (which could be natural language or a
structured query) and fetches data from the KG. It includes:
• A Natural Language to Graph Query Translator (if we allow agents or users to directly ask
questions that we then convert to Cypher or Gremlin queries).
• The ability to execute graph queries and return results in a structured format (objects, JSON) that the
agents can use.
• This component shields the rest of the system from the specifics of the graph database
(encapsulating whether it’s Neo4j, MemGraph, etc.).
• Query Classifier: Mentioned above, this is a lightweight component (could be rule-based or ML
classifier) that inspects the user query to determine if it’s asking for a fact (who/what/when/where
type questions, typically) or explanation/procedure (how/why, or code examples), or a mix. Our initial
implementation will likely use simple keyword heuristics (see Section 7.1) and can evolve to a ML
model if needed.

9

• LLM Orchestration (Commander) Enhancements: The orchestration layer (LLM Commander) will
be updated to incorporate KG queries in the agent workflow. Concretely:
• A given ticket or task to an agent may now include a step "Query the KG for X" as a deterministic tool
action (similar to how it uses MCP tools).
• Agents will have new abilities to call the KG interface. If using an LLM that supports function calling
or tools, we can implement a tool like get_fact(entity, property) or
find_related(entity, relation_type) that the agent can invoke.
• The multi-agent coordination (with anti-stomp checks) needs to consider facts: e.g., if Agent A
already fetched some fact from KG, it could attach it to the ticket context so Agent B doesn’t re-fetch
or ask again.
• Graph Population Service: A new service or batch process responsible for adding and updating
information in the KG. This includes scripts or pipelines that:
• Ingest data from documentation or APIs (via scraping or API calls).
• Possibly use an LLM or NLP pipeline to extract entities and relationships from text (automating
knowledge base construction).
• Listen for certain triggers – e.g., if a new version of an API is released, update the KG with the new
version number and mark the old one as deprecated.
• This service ensures the KG stays up-to-date and authoritative. (Details in Section 9.)
• Authority Conflict Resolver: Part of the “authority engine” concept, this component (could be just
logic within the orchestrator or KG engine) deals with situations where multiple sources provide
conflicting info. For example, the KG says API X endpoint = foo.com, but a live API call returns a
different endpoint. This component would enforce rules (trust KG more, or if live API is deemed
higher authority for real-time data, possibly update KG). It also logs conflicts for human review. (See
Section 8.2 for logic.)
• Integration with RAG and Cache: The existing RAG subsystem (vector DB and semantic cache) will
integrate with the KG:
• When the KG returns relevant entities/facts, those can be used to filter or enhance vector searches.
For example, if KG tells us the relevant API name is "NOAA RAP API", we can include that as a
keyword in the vector search query to get more targeted results.
• The semantic cache can store combined contexts (graph facts + text chunks) for a query, so repeated
similar queries skip redundant work.
• User Interface Components: Eventually, we plan a UI (the template-builder web UI and possibly an
admin console for the KG). These will allow:
• Viewing and editing the knowledge graph (for manual curation).
• Configuring the KG (like toggling it on/off, adjusting refresh intervals, etc., as per user controls in
Section 11).

10

• Visualizing relationships (which can help developers or users understand why the system gave a
certain answer based on connections).
These components work together as follows: a user query triggers classification; the appropriate retrieval
path (KG, RAG, or both) is taken; results are merged and fed to the LLM; the LLM generates an answer using
that evidence, and returns a final answer that is both contextually rich and factually correct.
In the next sections, we dive deeper into the design of the Knowledge Graph itself – including the schema
(ontology), how we populate and maintain it, and how we query it in practice.

5. Schema Design & Ontology
Designing the schema (ontology) for the knowledge graph is crucial. It defines how we represent various
domains of knowledge in a structured way. We need a flexible yet consistent schema that covers software
systems, product catalogs, weather data, code modules, and potentially more, without forcing everything
into one mold. We will use a property graph model (nodes with labels/types, relationships with types, and
both can have key-value properties), which is well-suited for our needs 5 .

5.1 Core Entity Types (Nodes)
We define several entity types to categorize nodes in the graph. These correspond to the major domains
we care about:
• Software Components: This includes libraries, modules, APIs, services, etc. Examples:
• Library (e.g., D3.js library, version 7.9.0)
• API (e.g., NOAA_RAP_API for weather data)
• Module/Tool (e.g., FreeFlight Weather Module, which might be a part of our system)
• Function (if we include code-level functions or classes as nodes for code relationships)
• Configuration Item (e.g., a specific configuration value or feature flag)
• Data/Format Entities: Represent data formats or data concepts especially in context of
requirements:
• DataFormat (e.g., “atmospheric_sounding” format)
• DataSource (e.g., a conceptual data source type like “weather data source” which could be provided
by some API)
• Dataset (if needed, for specific datasets or tables)
• Product Entities: For the WPSG product search context:
• Product (e.g., “Cairns_helmet” as a specific product)
• Category (e.g., “Firefighting” category)
• Brand (e.g., “Cairns” as a manufacturer/brand)
• Attribute (if we represent product attributes like weight, color, etc., though these might just be
properties on Product)
• Ontology/Taxonomy Nodes: Sometimes it’s useful to have abstract classification nodes:
• Type or Class nodes for grouping (for example, a node representing “PRIMARY_PRODUCT”
classification as mentioned)
• These can help model things like “Cairns_helmet is_a PRIMARY_PRODUCT” or category hierarchies if
needed.

11

• Miscellaneous: We may include nodes for any other concept that doesn’t fall into above, e.g.,
Concept or Term nodes for more abstract linkages (like linking the concept “Skew-T diagram” to
multiple components).
Each node will have a label (or type) indicating its entity type, and a set of properties (details in 5.3).

5.2 Relationship Types (Edges)
We identify common relationship types to link entities. Relationships are directed (with a source and target),
and can have their own properties (like a weight or confidence). Key relationship types include:
• requires – Indicates a dependency or requirement. For example, Skew-T diagram requires
atmospheric_sounding data. This is used when one entity cannot function or be implemented without
another. It’s a key relationship for understanding prerequisites (like a module requiring an API or
data).
• provides – Indicates that one entity provides something to another. E.g., NOAA_RAP_API provides
atmospheric_sounding data. Often used in conjunction with requires (if A requires some data, and
B provides that data, the graph can link A -> (requires) -> Data <- (provides) <- B).
• uses – Indicates usage or consumption. For example, FreeFlight_weather_module uses
NOAA_RAP_API. This is a more general relationship to show that a component uses a resource or
library. (Sometimes we might use a more specific relationship like calls or consumes , but
uses is a good generic one.)
• is_a – Denotes class membership or inheritance. E.g., Cairns_helmet is_a PRIMARY_PRODUCT. This
can also be used for taxonomies (a product is_a category) or for indicating something is an instance
of a concept.
• part_of – Composition relationship. E.g., FreeFlight_weather_module part_of FreeFlight_suite (if the
weather module is part of a larger suite or application). Or in product domain, if something is a
component of something else.
• has_category – Used in product context: Product has_category Category. E.g., Cairns_helmet
has_category Firefighting. This is similar to is_a but specifically for classification into categories.
• manufactured_by – In product domain: Product manufactured_by Brand. E.g., Cairns_helmet
manufactured_by Cairns.
• has_endpoint – A relationship to link an API to its endpoint URL (the endpoint could be stored as
a node or just as a property; but making it a node allows linking multiple APIs to perhaps common
endpoints or allowing endpoints to be versioned). E.g., NOAA_RAP_API has_endpoint "https://
nomads.ncep.noaa.gov/cgi-bin/filter_rap.pl". In practice, the endpoint could just be a property of the
API node, but we list this relationship type since it was noted.
• version_of (or has_version ) – If we need to model versions as separate nodes (e.g., Library
version relationships), we could use this. Alternatively, version is often just a property on an entity.
• renders_with – A specific relation from the example: Skew-T rendered_with D3.js (meaning Skew-T
diagram can be rendered with D3.js library). This is a specific kind of uses relationship.
• returns_format – From the example: NOAA_RAP_API returns_format atmospheric_sounding. Similar
to provides, indicating the format of data an API returns.
• weighted_override – This was mentioned in the WPSG context: Category weighted_override 1.5.
This seems like a way to override relevance weights (perhaps for search ranking). It could be
modeled as a relationship from a category node to a value node or as a property. Possibly better as a
property on the has_category relationship (like has_category could have a property

12

weight=1.5 for primary products). We can support it either way. If modeling as an edge:
PRIMARY_PRODUCT weighted_override 1.5 (as a literal node representing the weight), but likely it's
cleaner as a property.
We will likely use a combination of these. The schema will not be completely fixed – knowledge graphs can
evolve – but we will define an initial ontology so our data remains structured.

5.3 Properties on Nodes and Relationships
We will attach relevant attributes as properties. Some common ones:
Node Properties: - id – A unique identifier string for the node (could be a GUID or a human-readable
key). We might use something like a slug: e.g., "noaa_rap_api" or a GUID. - name – Human-readable name
or title (e.g., "NOAA RAP API", "Skew-T Log-P Diagram"). - type – The entity type (could be redundant if we
use labels, but sometimes storing type as property is handy, especially if multiple labels or for display). description – A brief description of the entity in natural language. - source – Provenance information
(where did this information come from? e.g., "NOAA documentation", or a URL to docs, or "manual_entry" if
added by dev). - last_updated – Timestamp of when this node (or its info) was last verified/updated. version – For versioned entities, store version string here (e.g., "v1" for an API, or "7.9.0" for a library). Additional domain-specific properties: - For APIs: endpoint (if not using has_endpoint relation), maybe
auth_required=true/false , etc. - For products: attributes like sku , price (if needed in KG), or flags
like is_primary=true (to denote primary product). - For data formats: maybe standard property or
unit info. - For functions/code: could have signature , etc.
Relationship Properties: - relationship_type – (Often the type is implicit by the relationship label
itself, so not needed as property.) - weight – applicable to relationships like weighted_override or if
we use weighted edges for relevance. E.g., has_category might have a weight. - confidence – If the
relationship was extracted automatically, we might store a confidence score (0.0 to 1.0) to indicate how sure
we are. Manual entries could default to 1.0. - source – Provenance of this relation (e.g., "extracted from
page 5 of NOAA.pdf on 2025-01-10"). - last_updated – If a relationship is subject to change (less
common, but e.g., if an API’s endpoint changes, the has_endpoint relation would update). - For temporal
relationships or version-specific, we could have valid_since / valid_until to denote if a fact was
only true during a time range (this is advanced versioning, may not need initially).
Ontology considerations: We should avoid overly rigid schema. The above properties cover generic needs;
specific attributes can be added as needed. Because we use a property graph, adding a new property to
some nodes doesn’t require a migration for all nodes (schema-less in that sense). However, we will maintain
an ontology document to track what each entity type and relationship type means, to avoid confusion or
duplicate representations (e.g., we decide once whether to represent an API endpoint as a property or
separate node).
We also have to consider naming conventions: e.g., use snake_case IDs, and possibly prefix IDs to avoid
collisions (like product ids vs function ids). But since the KG is relatively small, simple unique ids are fine.

13

5.4 Example Schema Snippets
To illustrate the schema, here is a concrete example using Cypher (as if we were populating a Neo4j or
MemGraph database) for the FreeFlight Weather Module / Skew-T use case described:

// Create entities (nodes)
CREATE (skewt:Visualization {
id: "skewt",
name: "Skew-T Log-P Diagram",
type: "visualization",
description: "Thermodynamic chart for atmospheric data (pressure vs
temperature)",
source: "domain_expert_manual",
last_updated: "2025-01-15"
});
CREATE (noaa:API {
id: "noaa_rap",
name: "NOAA RAP API",
type: "weather_api",
endpoint: "https://nomads.ncep.noaa.gov/cgi-bin/filter_rap.pl",
version: "v1",
source: "NOAA_documentation",
last_updated: "2025-01-15"
});
CREATE (sounding:DataFormat {
id: "atmospheric_sounding",
name: "Atmospheric Sounding",
type: "data_format",
description: "Vertical atmospheric profile (temp, humidity, etc.)",
source: "WMO_standard",
last_updated: "2024-12-01"
});
CREATE (d3:Library {
id: "d3js_v7",
name: "D3.js",
type: "javascript_library",
version: "7.9.0",
source: "npm_registry",
last_updated: "2025-02-10"
});
// Create relationships between them
CREATE (skewt)-[:REQUIRES]->(sounding);
CREATE (sounding)-[:PROVIDED_BY]->(noaa);

14

CREATE (skewt)-[:RENDERED_WITH]->(d3);
// Note: Could also indicate the API returns data in that format
CREATE (noaa)-[:RETURNS_FORMAT]->(sounding);
Explanation of the above: - We have a Visualization node for Skew-T (a kind of visualization/chart our
system wants to produce). - An API node for NOAA’s RAP API, including its endpoint as a property. - A
DataFormat node for “Atmospheric Sounding” data (the specific kind of data the Skew-T needs). - A
Library node for D3.js (which might be used to render the visualization). - Relationships: - Skew-T
REQUIRES atmospheric_sounding data. - That data is PROVIDED_BY the NOAA RAP API. - Skew-T can be
RENDERED_WITH D3.js library. - NOAA RAP API RETURNS_FORMAT atmospheric_sounding (essentially
indicating what kind of data it gives).
This subgraph would allow queries like: - “What does the Skew-T visualization require?” → Traverse
(:Visualization {name:"Skew-T"})-[:REQUIRES]->(dep) , which yields the DataFormat node
“Atmospheric Sounding”. - “Who provides Atmospheric Sounding data?” → Traverse

(sounding)-

[:PROVIDED_BY]->(provider) , yielding “NOAA RAP API”. - “What is the endpoint for the API that provides
Skew-T data?” → Multi-hop: Skew-T -> requires -> Sounding -> provided_by -> NOAA API -> get endpoint
property = URL. - “How do I render Skew-T?” → We see it’s rendered_with D3.js, so the agent might
incorporate that knowledge (and then retrieve a code example for D3.js usage via RAG, for instance).
Product Example: For WPSG product search, we could have:

CREATE (helmet:Product {
id: "cairns_880",
name: "Cairns 880 Traditional Helmet",
type: "product",
source: "product_catalog_db"
});
CREATE (firefighting:Category { id:"cat_fire", name:"Firefighting",
type:"category" });
CREATE (cairnsBrand:Brand { id:"brand_cairns", name:"Cairns", type:"brand" });
CREATE (helmet)-[:HAS_CATEGORY {weight: 1.5}]->(firefighting);
CREATE (helmet)-[:IS_A]->(:Category { name:"PRIMARY_PRODUCT", type:"category"});
CREATE (helmet)-[:MANUFACTURED_BY]->(cairnsBrand);
This shows a Cairns helmet product: - It HAS_CATEGORY Firefighting (with a weight override property 1.5
on that relation to boost it). - It also IS_A PRIMARY_PRODUCT (assuming we define that category
separately as a node). - And MANUFACTURED_BY the Cairns brand.
With such graph data, a query like “What category should Cairns helmets be in?” can be answered by finding
the product node and looking at its HAS_CATEGORY relationship leading to "Firefighting" 16 (and seeing
that it’s marked as a primary product via either an attribute or the IS_A PRIMARY_PRODUCT relation).

15

These examples illustrate how we model different domains in a unified graph. The ontology is flexible: new
node labels or relationship types can be added as needed, but we have a core set to cover our main use
cases.

6. Implementation Specification
Now we outline how to implement the knowledge graph within our system. This covers setting up the graph
database, providing programmatic interfaces to query/update it, translating natural language queries to
graph queries, populating the graph with data, and so on.

6.1 Graph Database Setup
We will start with Neo4j Community Edition as our graph database in development, given its maturity and
our familiarity with Cypher. In production, this choice might change to Neo4j Aura (cloud) or MemGraph or
the SQLite-based approach as discussed. But for concreteness, we describe setup with Neo4j:
• Installation/Deployment: We can use a Docker container for Neo4j for ease of deployment. A
simple docker-compose.yml can bring up a Neo4j instance. We should configure:
• Bolt port (7687) and HTTP port (7474 for browser) exposures.
• Set Neo4j to use plaintext auth for dev (or disable auth in a dev mode), and strong auth in prod.
• Allocate memory appropriately (our graph might be small, but ensure Java heap is enough for
indices).
• Initial Schema Load: Neo4j is schema-optional, but we might want to create indexes for
performance:
• e.g., CREATE CONSTRAINT FOR (n:API) REQUIRE n.id IS UNIQUE; (and similar for other key
labels) to ensure unique IDs and speed up lookups by id.
• Index properties like name on frequently looked-up entities if needed.
• Integration with App: We’ll add a configuration for the knowledge graph in our Node.js backend.
For example, using a Neo4j JavaScript driver to connect. (In the configuration snippet in Section 11,
we have a knowledgeGraph config where backend: "neo4j-community" could trigger using
the Neo4j driver). If we use SQLite+extension, integration would instead be via a SQLite client and
executing SQL queries (with Cypher embedded).
• Alternate Setup (MemGraph): If we opt for MemGraph (since it’s similar to Neo4j in Cypher usage
but in-memory), we can easily swap the driver to Memgraph’s and run a Memgraph Docker instead.
Memgraph would be suitable for faster, ephemeral graphs (like in-memory testing or fast analytics).
• Alternate Setup (Embedded): If using the SQLite graph extension, the setup is just loading the
extension library in our Python or Node environment. The benefit is no separate service; the cost is
the extension is alpha and we might need to compile it for our platform. But for completeness:
• Build the libgraph extension from [agentflare-ai/sqlite-graph] repo.
• In our app, open the SQLite ( index.db ) and run SELECT load_extension('libgraph'); to
enable graph features.
• Then we can run Cypher queries via an SQL function call interface provided by the extension (likely
something like SELECT * FROM cypher('MATCH ...') ). This keeps KG and RAG in one database
file, simplifying deployment.

16

• Security & Access: For Neo4j, create a user with proper permissions (read/write as needed). In
production if exposed, use encryption on the Bolt protocol. If multi-tenant, ensure separate graphs
or use an access control if on same instance.
• Connection Pooling: Use a connection driver (e.g., neo4j-driver for Node) with pooling to
handle concurrent queries from our agents.
In summary, initial setup involves minimal friction especially with a local Neo4j. Our focus will be on
building the graph content and the interfaces to use it, which we detail next.

6.2 Query Interface (API)
We will create a KnowledgeGraph interface in our application code (likely TypeScript, since the backend is
Node/TypeScript). This abstracts away the underlying graph database and provides convenient methods to
the rest of the system (especially the LLM agent orchestrator) for common operations: getting entities,
querying relationships, executing custom queries, etc.
Below is a conceptual interface definition:

interface KnowledgeGraph {
// Simple lookups
getEntity(id: string): Promise<Entity | null>;
getProperty(entityId: string, propertyName: string): Promise<any>;
// Relationship queries
getRelated(entityId: string, relationshipType?: string): Promise<Entity[]>;
// e.g., get all entities related to given entity, optionally filter by
relationship type.
findPath(fromId: string, toId: string, maxHops?: number): Promise<Path>;
// find shortest path between two nodes (for reasoning connections)
// Complex queries
query(naturalLanguage: string): Promise<QueryResult>;
// Accept a natural language question and internally translate to graph
query (calls translator).
queryCypher(cypherQuery: string): Promise<QueryResult>;
// Directly execute a Cypher query (for more complex or specific queries).
// Graph traversal / subgraph
getNeighborhood(entityId: string, depth: number): Promise<Subgraph>;
// e.g., fetch the subgraph of all nodes within N hops of the given node.
findSimilar(entityId: string, limit: number): Promise<Entity[]>;
// Find similar entities, possibly via vector embeddings of graph nodes or
structural similarity.
// Maintenance operations
addEntity(entity: Entity): Promise<void>;

17

addRelationship(fromId: string, toId: string, type: string, properties?:
Record<string, any>): Promise<void>;
updateEntity(id: string, updates: Partial<Entity>): Promise<void>;
deleteEntity(id: string): Promise<void>;
// (We can also have removeRelationship etc.)
}
interface Entity {
id: string;
labels: string[]; // e.g., ["API","Service"] if multiple
properties: Record<string, any>;
relationships?: Relationship[]; // possibly include edges if fetched
}
interface Relationship {
type: string;
target: Entity; // or targetId if not populated
properties?: Record<string, any>;
}
interface Path {
nodes: Entity[];
relationships: Relationship[];
// Could also include distance, etc.
}
interface QueryResult {
entities: Entity[];
// main entities returned (e.g., from a MATCH query)
relationships: Relationship[]; // if the query returns edges or paths
paths?: Path[];
// for path-finding queries
raw?: any;
// raw result if needed (e.g., for aggregate queries)
metadata: {
queryTime: number;
resultCount: number;
};
}

This is a high-level design; actual implementation might differ (for instance, the Neo4j driver returns
records that we transform). But essentially: - We provide methods for common tasks like getting an entity
by id, or retrieving related entities. - We allow natural language queries by providing a
query(naturalLanguage) method – this will use the translation approach in 6.3. - We also allow directly
sending a Cypher query (for internal use when we have a specific query to run). - The interface can be
implemented for different backends: - For Neo4j: implement these methods using Cypher via Bolt. - For
SQLite: implement using appropriate SQL (with the extension). - The rest of the system uses the interface
without worrying about which DB is underneath.

18

This interface will be used by our Tool layer for the LLM (for example, an agent might call
KnowledgeGraph.getProperty("noaa_rap", "endpoint") to get the endpoint URL). It will also be
used by population scripts (e.g., addEntity when seeding data).

6.3 Natural Language to Graph Query Translation
While agents could directly call specific methods as above, we also want the flexibility to handle arbitrary
natural language queries by translating them into graph queries. This is essentially enabling the system (or
even end-users, via the LLM) to ask questions of the KG without hardcoding each type of query.
We can leverage an LLM (paradoxically) to do this translation – but since it’s deterministic (we can verify the
query), it’s a safe use of the LLM.
Pseudo-code for translation:

async function translateToGraphQuery(naturalLanguage: string): Promise<string> {
// We will prompt an LLM (like GPT-4 or our local model) with a prompt that
instructs it on our schema and asks for Cypher.
const prompt = `
You are an assistant converting natural language questions into Cypher graph
queries against a knowledge graph.
Knowledge Graph Schema:
- Node types: Library, API, DataSource, Product, Category, Brand, Visualization,
etc.
- Relationships: requires, provides, uses, is_a, part_of, has_endpoint,
has_category, manufactured_by, rendered_with, etc.
- Properties: nodes have 'name', 'id', 'type', etc. APIs have 'endpoint'.
Convert the following question into a Cypher query. Only provide the Cypher
query without explanation.
Question: "${naturalLanguage}"
`;
const cypherQuery = await llm.generate(prompt);
// Basic validation to avoid any malicious content in query
if (!cypherQuery.toLowerCase().startsWith("match")) {
throw new Error("LLM did not return a Cypher query");
}
return cypherQuery.trim();
}
// Examples of usage:
translateToGraphQuery("What API provides atmospheric soundings?")

19

// -> "MATCH (api:API)-[:PROVIDED_BY]-(data:DataFormat {name: 'Atmospheric
Sounding'}) RETURN api"
translateToGraphQuery("What does the Skew-T require?")
// -> "MATCH (vis:Visualization {name:'Skew-T Log-P Diagram'})-[:REQUIRES]>(dep) RETURN dep"
translateToGraphQuery("List all weather data sources")
// -> "MATCH (s:DataSource) RETURN s"
This approach uses a prompt template. In practice, we'd integrate this into our system so that when an
agent or user asks a question that we identify as factual and suitable for KG, we do: 1. Call
translateToGraphQuery(question)
to
get
a
Cypher
query.
2.
Call
KnowledgeGraph.queryCypher(query) to execute it. 3. Take the results and format them for the
agent’s use.
We must ensure the LLM knows the schema or we provide it. We can maintain a prompt snippet with the
ontology definition (like the relationships above). Over time, a fine-tuned model could do this more reliably.
We’ll also write unit tests for this translation (e.g., give known questions and ensure the Cypher is correct).
Validation: Because we don’t want arbitrary Cypher execution (security!), we will implement some checks: Only allow read queries (e.g., disallow DELETE or schema writes from this interface). - Possibly whitelist
certain patterns or use parameterized queries where possible.
However, since this is an internal tool (the user of this function is our system, not an external user), the risk
is low.
This NL->Cypher translator essentially allows dynamic querying of the KG without us pre-programming
every question. It empowers the LLM to use the KG effectively by asking in natural terms and getting a
structured answer.

6.4 Graph Population Pipeline
One of the challenges is populating and updating the knowledge graph with accurate facts. We expect to
gather data from: - Documentation (e.g., API docs, technical specs) - Live APIs or system introspection Existing databases (product catalog) - Developer knowledge (manual input)
We will use a combination of manual curation and automated extraction.
Manual Curation: For initial bootstrap, developers will manually add key nodes/edges via either Cypher
commands or a simple admin UI. This ensures critical facts are in place and correct (e.g., we manually enter
the NOAA RAP API endpoint as we trust the official docs).
Automated Extraction from Text: We can build a pipeline that reads documentation (maybe from our
.rag knowledge base or external docs) and extracts structured facts. This can be done by an LLM or by
classical NLP: - Use Named Entity Recognition (NER) to find entities (like names of APIs, library names,

20

etc.) 24 . - Use Relation Extraction to find sentences that imply a relationship (e.g., "Skew-T requires
atmospheric sounding data" in a doc could be turned into a triple (Skew-T, requires,
atmospheric_sounding)) 24 . - There are off-the-shelf tools (SpaCy with custom patterns) or we can prompt
GPT-4 in a smart way to output JSON triples.
For example, using an LLM for extraction:

async function extractEntitiesAndRelationships(text: string):
Promise<ExtractionResult> {
const extractionPrompt = `
Extract facts from the following text for our knowledge graph.
Identify entities and relationships among them.
Output JSON with two keys:
"entities": list of {name, type, description (if available)},
"relationships": list of {source: entity_name, target: entity_name, type:
relationship_type}.
Text:
\"\"\"
${text}
\"\"\"
`;
const result = await llm.generate(extractionPrompt);
return JSON.parse(result);
}
This is a rough approach. We might need to refine prompts or use smaller chunks of text at a time to keep
the LLM consistent. Microsoft’s GraphRAG actually does something similar by using LLM to extract a graph
from each text chunk 25 .
We will then take the output and call

KnowledgeGraph.addEntity

and

addRelationship

accordingly:

async function populateGraphFromDoc(docPath: string) {
const text = await fs.promises.readFile(docPath, 'utf8');
const { entities, relationships } = await
extractEntitiesAndRelationships(text);
for (const ent of entities) {
// Ensure no duplicate:
if (!await kg.getEntity(ent.name.toLowerCase())) {
await kg.addEntity({
id:
generateId(ent.name), // some function to create a unique id, e.g., slugify
labels: [ent.type],

21

properties: {
name: ent.name,
description: ent.description || "",
source: docPath,
last_updated: new Date().toISOString()
}
});
}
}
for (const rel of relationships) {
await kg.addRelationship(generateId(rel.source), generateId(rel.target),
rel.type.toUpperCase(), { source: docPath });
}
}

We will have to be careful about entity resolution – the same entity might be mentioned in multiple docs
with slightly different names. Part of the ontology design is to have a unique id or a way to detect
duplicates (maybe using synonyms or linking via an alias map). This could be an ongoing maintenance task
(merging duplicate nodes).
API Scraping: For dynamic info like the latest versions: - Write a script to call external APIs. E.g., hitting an
npm registry API for the latest version of D3, or NOAA’s endpoint for supported dataset list. - Update the
graph with new nodes or properties from the API response. - Similarly, for our product catalog, we might
directly ingest from the product database: e.g., run through all products and add them as nodes, with
category relationships.
Incremental Updates: We will schedule periodic jobs to refresh certain info (described more in Section 9.2).
For instance: - Daily job to check if any library version in KG is outdated by comparing with an online source.
- Weekly job to re-scrape docs if needed or check if any new documentation is available.
By combining these methods, the KG will be both comprehensive and current. Initially, we’ll focus on a few
high-value areas (our known problem areas): - The FreeFlight weather example (Skew-T needs NOAA data,
etc.) - The WPSG product categories (to fix search relevance issues) - Core APIs and libraries we use (so that
their endpoints and versions are recorded and not hallucinated)
As confidence grows, we can expand to more areas.
Below is a simplified code pipeline example putting it together:

// Master function to build KG from various sources
async function buildKnowledgeGraph() {
// 1. Manual seeds
await kg.addEntity({ id:"skewt", labels:["Visualization"], properties:
{name:"Skew-T Log-P Diagram", ...} });
// ... add known things like NOAA_RAP_API, etc.

22

// 2. Import from documentation
for (const doc of ["DOCS/NOAA_API.txt", "DOCS/FreeFlight_design.md"]) {
await populateGraphFromDoc(doc);
}
// 3. Import from databases
const products = await fetchAllProductsFromDB();
for (const p of products) {
await kg.addEntity({ id: `prod_${p.id}`, labels:["Product"], properties:
{name: p.name, ...} });
// add category rel
await kg.addRelationship(`prod_${p.id}`, `cat_${p.categoryId}`,
"HAS_CATEGORY", { source: "product_db" });
// etc.
}
// 4. Derive additional relationships by inference if possible (optional step)
}

This gives an idea. In practice, we will iterate on the population step as we learn where the gaps are.

7. Integration with Existing Systems
One of the strengths of this design is that it doesn’t replace our existing RAG and caching systems – it
complements them. Integration points include query handling, multi-stage retrieval, and caching. We detail
how the KG works in concert with RAG and our multi-agent setup.

7.1 Hybrid KG + RAG Retrieval Flow
As outlined in the architecture, we will implement logic to decide how to use the KG for a given query. A
straightforward approach is a query classifier function that uses keywords or ML to categorize queries
into: - Fact lookup (KG), - Contextual/info lookup (RAG), - Hybrid (both).
Here's a simple implementation using keywords (in practice we might refine this logic or use an ML classifier
trained on question types):

type QueryType = "FACT_LOOKUP" | "CONTEXT_LOOKUP" | "HYBRID";
function classifyQuery(query: string): QueryType {
const q = query.toLowerCase();
const factKeywords = ["what is", "who is", "when", "where", "endpoint",
"version", "API", "ID", "number"];
const contextKeywords = ["how to", "how do i", "example", "explain", "why",
"guide", "tutorial"];

23

const isFact = factKeywords.some(kw => q.includes(kw));
const isContext = contextKeywords.some(kw => q.includes(kw));
if (isFact && !isContext) return "FACT_LOOKUP";
if (isContext && !isFact) return "CONTEXT_LOOKUP";
return "HYBRID";
}
Then the retrieval function:

async function retrieveForQuery(query: string): Promise<{facts?: QueryResult,
context?: string[]}> {
const type = classifyQuery(query);
let factsResult: QueryResult | undefined;
let contextResult: string[] | undefined;
if (type === "FACT_LOOKUP" || type === "HYBRID") {
// Query KG
factsResult = await KG.query(query); // this uses NL->Cypher internally
}
if (type === "CONTEXT_LOOKUP" || type === "HYBRID") {
// If hybrid, we might enrich the query with info from KG facts:
let modifiedQuery = query;
if (factsResult && factsResult.entities.length > 0) {
const entityNames = factsResult.entities.map(e => e.properties.name ||
e.id);
// e.g., append entity names to query as keywords
modifiedQuery = query + " " + entityNames.join(" ");
}
// Query RAG (vector similarity search)
contextResult = await RAG.retrieve(modifiedQuery);
}
return { facts: factsResult, context: contextResult };
}

In practice, our RAG system might have a function like rag.search(query) returning top-k passages. We
would pass the possibly modified query (embedding the entities or keywords from KG to focus the search).
For example, if the user asked "How do I implement Skew-T?" the KG might return that Skew-T requires the
NOAA RAP API and D3.js. We then append "NOAA RAP API D3.js" to the original question before vector
search. This way, the retrieval is guided to documentation that includes those terms, likely increasing
relevance.

24

The result is that we get: - facts from KG: structured data we can present or include in the prompt as
facts. - context from RAG: unstructured text (like explanation or code example).
We then compose the final context for the LLM. Likely, we’ll craft a prompt section that enumerates the facts
(perhaps in a bullet list or a structured format) followed by the usual retrieved passages as context. The
agent’s system prompt or instructions will be updated to say "You have access to the following verified facts
and reference text. Use them to answer...".
This hybrid retrieval ensures that the LLM sees the factual answers explicitly rather than having to guess
or pick them out from a text passage.

7.2 Multi-Stage Retrieval Integration
Our existing retrieval pipeline already contemplates multi-stage retrieval (with iterative querying, agentic
refinement, etc.). The KG can augment multiple stages: - Stage 1: Entity Extraction Stage. An LLM could
first attempt to identify key entities in the user query (this is similar to the classifier idea). If we identify
entities (like "Skew-T" or "Cairns helmet") in the query, we first hit the KG to gather all immediate facts
about them. These facts effectively form an “entity card” or profile. - Stage 2: Context Retrieval Stage.
Using those facts, form a better query for the RAG vector search (as described). Also, possibly filter out
irrelevant documents: e.g., if the KG tells us the user’s query is about weather and D3.js, maybe we restrict
RAG to the weather module docs and D3 docs. - Stage 3: Synthesis Stage. The LLM then gets both sets of
info. At this point, the LLM’s job is to synthesize an answer. If any part of the answer requires a fact, it can
directly quote the fact from KG. For example, instead of saying "the API endpoint might be X", it will know it
is X from KG. If it needs explanatory text, it uses the RAG passages.
We also plan to incorporate validation: After the LLM drafts an answer, we could have a step where it
verifies facts against the KG again. If we implement this, an agent (or a function call) could extract any
factual claims from the answer and double-check with KG. However, if we trust that we injected correct
facts, the LLM should have used them. Still, an extra validation step could catch if the LLM ignored the KG
info and hallucinated something new.

7.3 Integration with Semantic Caching
Our semantic caching (30-40% hit rate currently) can be extended: - KG Query Caching: Results of KG
queries (which are often small JSON outputs) can be cached keyed by the query or by the graph pattern. For
example, if 10 users ask about "NOAA RAP API endpoint", we don’t need to hit Neo4j each time – we can
cache that result. (Though Neo4j is quick for single lookups, caching is still beneficial, especially if using a
remote graph DB.) - Hybrid Result Caching: We can cache the combination of facts+context for a given
query or for a given set of key entities. For instance, we might cache that for "implement Skew-T", the
relevant KG subgraph (Skew-T, Sounding, NOAA API, D3) plus the top 3 retrieved docs are X, Y, Z. Then if a
similar query comes or the user follows up, we reuse those. - Invalidation: The cache needs to be aware of
graph updates. If we update a fact in the KG (say NOAA changed an endpoint), any cached entries
containing that fact should be invalidated. We’ll implement a simple strategy: bump a version number or
timestamp for the KG, and have the cache entries tagged. On a KG update, either flush relevant cache
entries or mark them stale.

25

We will measure how often queries truly repeat. It might be that many user queries are unique, but certain
tasks (like “What is the NOAA API endpoint?”) could recur often, making caching very useful.
In summary, the integration ensures the KG is not an isolated component but woven into the query
understanding and retrieval fabric of the LLM system. Agents effectively get a new "sense": in addition to
reading documentation (RAG) and writing code, they can now consult a knowledge base like asking an
expert for the exact fact, which they then use in their reasoning.

8. Authority Engine Pattern and Conflict Resolution
The Knowledge Graph is a central piece of our Authority Engine approach. Here we detail how the system
enforces the hierarchy of information sources and handles conflicts or discrepancies between sources.

8.1 Hierarchy of Authority Levels
We define an enum of authority levels for sources:

enum AuthorityLevel {
KNOWLEDGE_GRAPH = 1,
LIVE_API = 2,
RAG_DOCUMENTATION = 3,
outdated)
LLM_OWN_KNOWLEDGE = 4
}

// Highest authority: curated facts
// Next: direct from official sources
// Then: from documentation or files (could be
// Lowest: model's internal/hallucinated info

Lower number = higher trust. The idea is that whenever a factual question arises, we attempt sources in
order until we get an answer: 1. KG: If the KG has the answer, use it and trust it fully. 2. Live API/DB: If not
in KG, call an external API or database (for example, fetch the actual current value). E.g., if asked "current
weather in X", KG might not store that (because it's dynamic), so we call a weather API (which we consider
authoritative for real-time data). Another example: if asked for "latest version of D3.js", we might call npm
registry API. - Optionally, after getting this data, we might insert it into the KG for future queries (with a
timestamp). 3. RAG: If the above fail, fall back to searching documentation via RAG. If found in docs, it’s less
guaranteed (the doc might be old), but it's something. We might then include it with a note that "According
to docs (from 2021) the value is ...". - We can also update the KG with this fact if we trust it enough, marking
it with source and maybe lower confidence. 4. LLM: Only if none of the above provide an answer should the
LLM attempt to answer from its own training/inference. If it does, we will tag that answer as potentially
unreliable. Ideally, the LLM should simply say "I don't know" rather than hallucinate, but if we are forcing an
answer, we label it.
We can implement a resolver function to encapsulate this:

interface FactResult { value: string; source: string; authority:
AuthorityLevel; }
async function getAuthoritativeFact(query: string): Promise<FactResult> {

26

// 1. Try KG
const kgRes = await KG.query(query);
if (kgRes.entities.length > 0) {
const val = extractValueFromEntity(kgRes.entities[0]); // assume the query
was for a property
return { value: val, source: "KG", authority:
AuthorityLevel.KNOWLEDGE_GRAPH };
}
// 2. Try Live API (if applicable)
const apiRes = await tryLiveAPIs(query);
if (apiRes) {
// We got an answer from an external API
// Optionally, update KG:
// await KG.addEntity(...);
return { value: apiRes.value, source: apiRes.source, authority:
AuthorityLevel.LIVE_API };
}
// 3. Try RAG documentation
const ragRes = await RAG.retrieve(query);
const extracted = ragRes ? extractPotentialFact(ragRes) : null;
if (extracted) {
return { value: extracted.value, source: extracted.source, authority:
AuthorityLevel.RAG_DOCUMENTATION };
}
// 4. Fallback to LLM's own reasoning (not desirable, but in worst case)
const llmAnswer = await llm.generate(query);
return { value: llmAnswer, source: "LLM_generation", authority:
AuthorityLevel.LLM_OWN_KNOWLEDGE };
}

This pseudo-code tries each source in order. The extractValueFromEntity is a helper to get the actual
fact from the KG result – e.g., if the query was "what is NOAA_RAP_API endpoint", the KG query might return
the API node including an endpoint property, so we extract that property value.
For tryLiveAPIs , we’d have some mapping of question patterns to API calls: - If query contains
"weather" or "NOAA", call our weather API integration. - If query is about "latest version of X library", call
npm or GitHub. - etc. This could be expanded as needed.
When using a live API, we consider it authoritative (they are primary sources of truth). However, live calls can
fail or be slow, so we use them sparingly and possibly asynchronously.

8.2 Conflict Resolution
Conflicts can arise if, say, the KG has one value and a live API returns another (meaning our KG is outdated
or wrong), or if documentation says one thing but another source says different.

27

We implement a conflict resolver that, given multiple FactResults, chooses the highest authority one, and
logs the incident:

function resolveConflict(fact: string, options: FactResult[]): FactResult {
options.sort((a, b) => a.authority - b.authority);
const top = options[0];
if (options.length > 1) {
const second = options[1];
if (top.value !== second.value) {
// Conflict detected between top two sources
logConflict({ fact, chosen: top, other: second, timestamp: new Date() });
// Optionally, we could notify a human or mark KG entry as needing review
}
}
return top;
}

In practice, because our getAuthoritativeFact tries in order and returns the first found, we normally won’t
have multiple options at the same time. However, consider we have an existing KG value and we decide to
refresh from a live API periodically: - If we find discrepancy, we update KG with the new value, but also keep
a history (maybe an old version attached or an audit log). - The conflict resolver is more conceptual here.
Another scenario is if two different documentation sources disagree; we would treat that as RAG-level
conflict and likely trust none fully until confirmed.
Provenance and Logging: Every fact in the KG has a source property (like "NOAA documentation
2024-01" or "Manual entry by J.Doe"). We will maintain that. When updating a fact, we might add a new
property or relationship indicating it supersedes a prior fact. In a sophisticated setup, one could model this
with an Evidence node or attach multiple sources to a fact node, but that complexity might not be needed
initially.
The system will keep logs of: - When the KG was consulted and what it returned. - When a conflict was
found (which triggers either an automatic update or a flag for review). - Use these logs to improve the
knowledge ingestion (for example, if we repeatedly find KG is outdated for library versions, we might
schedule more frequent updates or find a better source).
In summary, conflict resolution is about ensuring the KG remains the top source of truth. When it’s wrong,
we correct it (and thus next time it will be right). Over time, this feedback loop will make the KG very robust.
Example: Suppose KG says D3.js latest version = 7.8.0 (source: some old data). A user asks “What is the latest
D3.js version?”. Our pipeline might call npm view d3 version (live API), which returns 7.9.0. That is
higher authority than our KG (which was outdated). The system responds "7.9.0" (and perhaps also updates
the KG’s version property to 7.9.0, with source "npm_registry on 2025-02-10"). It logs that a conflict was
resolved (KG had 7.8.0, updated to 7.9.0). Next time, the KG itself would have 7.9.0.

28

By enforcing these rules strictly, we aim to stop hallucinations completely for factual queries – the LLM
will always either give an answer from a trusted source or say it doesn’t know if even the KG lacks it (which
should be rare as the KG grows).

9. Graph Population & Maintenance
Building the KG is not a one-time task. It requires ongoing maintenance to stay accurate and useful. We
outline how to populate initially and how to keep the graph updated and clean over time.

9.1 Initial Population Strategies
As mentioned in section 6.4, initial population will combine manual and automated methods:
• Manual Seeding: We identify critical facts that are frequently needed and prone to LLM error. E.g.:
• API endpoints and keys (NOAA RAP API endpoint, other service URLs).
• Important configuration constants (perhaps certain file paths, IDs).
• Relationships between internal modules (which developer knows but may not be documented).
• Key product-category mappings that have been problematic.
These we enter by hand using either Cypher queries or a simple script. This gives us a core KG to start with.
• Import from Existing Data Sources: For example:
• Load all products from the WPSG product DB and their categories. This can be done via a script that
reads the SQL DB and writes to the KG via addEntity calls. This instantly gives us a product
knowledge subgraph.
• If we have any existing spreadsheets or JSON of facts (sometimes teams maintain a "constants" file
or internal wiki), we can parse those and add to KG.
• Documentation Mining: Use the extraction pipeline on the most relevant docs. For instance, run it
on the FreeFlight weather module design spec. If that spec mentions "Skew-T requires atmospheric
sounding from NOAA", the extractor will create the triples accordingly. Also run on any API
documentation we have in text form (if NOAA has a text or HTML docs, we can parse them).
• We may use the RAG index as a source: since .rag/index.db might contain chunks of documents,
we could iterate over those chunks and apply extraction. That leverages what we already ingested
for RAG.
• Consolidation and Cleanup: After initial automated extraction, we likely need to review the graph:
• Check for duplicates (the same entity with slightly different name added twice). We might merge
nodes manually or tweak our extraction to use consistent naming (like everything lower-case id).
• Remove any erroneous relationships that don't make sense (LLM extraction can have false positives).
• Add any missing crucial links (if automated missed something obvious).
This initial phase results in a baseline knowledge graph.

29

9.2 Automated Refresh and Update
The world changes and so will our knowledge: - APIs get updated or deprecated. - New products are added.
- Configurations change.
To handle this: - Scheduled Jobs: We will set up a background job (could be a cron or a Node scheduled task
or an external service) to periodically refresh certain parts of the graph: - API Metadata Refresh: For each
API node in KG, call a known endpoint for metadata if available (for NOAA, maybe a "capabilities" endpoint
or just check if the current endpoint is alive). For libraries, query a package registry for the latest version.
Example pseudo-code:

async function refreshAPIs() {
const apis = await
KG.queryCypher("MATCH (api:API) RETURN api.id, api.version, api.endpoint");
for (const api of apis.entities) {
const latest = await fetchLatestVersionFromSource(api.properties.name);
if (latest && api.properties.version !== latest.version) {
await KG.updateEntity(api.properties.id, { version: latest.version,
last_updated: new Date().toISOString() });
}
// possibly also validate endpoint by pinging it.
}
}

For libraries:

async function refreshLibraries() {
const libs = await KG.queryCypher("MATCH (lib:Library) RETURN lib.id,
lib.version");
for (const lib of libs.entities) {
const npmName = lib.properties.name; // assuming name matches package name
const latestVersion = await fetch(`https://registry.npmjs.org/${npmName}/
latest`).then(res => res.json()).then(d => d.version);
if (latestVersion && lib.properties.version !== latestVersion) {
await KG.updateEntity(lib.properties.id, { version: latestVersion,
last_updated: new Date().toISOString() });
console.log(`Updated ${npmName} version to ${latestVersion} in KG.`);
}
}
}
These would run maybe daily or weekly, as needed.

30

• Webhook/Triggers: In some cases, we can hook directly into events:
• For example, if our product catalog is internal, whenever a product is updated or added, we fire an
event that triggers updating the KG for that product (ensuring it’s never stale). This might be an
integration with the product service.
• Similarly, if code is deployed with a new module, a CI/CD step could update the KG with new module
relationships (this is more advanced CI integration).
• Staleness Monitoring: We can maintain a last_verified property for facts and periodically
attempt to verify them:
• E.g., the endpoint URL – we can attempt a simple HTTP GET (non-destructive) to see if it returns 200.
If not, flag that endpoint as potentially stale.
• If an entity hasn’t been updated in a long time and is critical, maybe prompt a dev to review it.
• Automated Conflict Detection: Building on Section 8, if at runtime we ever find the KG was wrong
(via a conflict with API or user correction), we update it. Logging those events allows improvement.
Over time, these updates will reduce further conflicts.

9.3 Manual Curation and Editing Tools
While automation is great, human oversight remains important: - We will provide an Admin UI or
procedure to allow knowledge engineers (which could be ourselves, the developers) to easily browse and
edit the graph. This might be as simple as enabling Neo4j Browser for developers or a small custom web UI.
- The UI should list all entities by type, allow filtering/search by name, and show details and relationships.
One could click “Edit” on a node to change its properties (e.g., update description or correct a name). Relationships should be editable: add a missing link or remove an incorrect one. - Bulk Import/Export: The
UI or tooling should allow importing a set of triples (e.g., from a CSV) and exporting parts of the graph for
backup or analysis. - Visualization: A graph visualization of neighbors would be extremely helpful for
understanding and verifying the knowledge graph. Using an existing tool (Neo4j Bloom or an OSS like
GraphExplorer) could suffice. Even a simple D3-based viewer could be integrated into an admin page.
• Review Workflow: If automated extraction adds facts with low confidence, we might mark them as
"unverified". The UI should highlight these so a human can verify and mark as verified or remove
them. For instance, any relationship with confidence < 0.8 could be shown in a "To Review" list.
The combination of automated updates and manual curation ensures the KG remains accurate,
comprehensive, and trustworthy. We essentially treat the KG like a codebase: it has version control (via
logs), it gets updates, and sometimes manual patches. Just as code has tests, our KG-backed answers will be
“tested” every time they’re used in an LLM conversation – if something is off, it will become apparent, and
we fix the KG.

31

10. Performance & Cost Analysis
Introducing a knowledge graph will have implications on system performance and cost. We analyze these to
ensure the benefits outweigh the overhead.

10.1 Query Performance
Graph databases are generally very fast for point lookups and reasonably fast for local traversals, but we
should consider expected query patterns: - Simple fact lookup: e.g., find the value of a property for a given
entity (like endpoint for NOAA API). With an index on id or name , this is essentially O(log N) or O(1) with
index – negligible latency (on the order of milliseconds). We expect < 5-10 ms for such a query on a small
graph (thousands of nodes) 13 . - One-hop relationships: e.g., find all categories a product has, or find
what an API provides. This involves an index lookup to the starting node, then traversing its relationships –
typically still very fast (< 10 ms, maybe 1-2 ms if in memory). - Two-hop queries: e.g., from a product find its
category then find all other products in that category (a simple recommendation query). This might take
slightly longer but for small graphs likely under 50 ms. - Larger traversals (multi-hop): If we did a 4-5 hop
traversal or a path search, performance can drop depending on graph density. But given our domains, the
graph is not extremely dense. We can also impose limits in queries. Expect in worst typical cases maybe
50-200 ms for more complex multi-hop reasoning queries (still acceptable given LLM calls are seconds
long). - Subgraph fetch: If we retrieve a whole neighborhood (say all nodes within 2 hops of X), that could
be dozens of nodes – perhaps 100s of ms if not optimized, but we can optimize by specifying subgraph
patterns and using appropriate indexes.
We will also monitor query times via the driver’s telemetry. Neo4j provides query profiling if needed, but
likely our usage is light.
The key is that KG queries (a few ms) are vastly cheaper than an equivalent LLM token-generating process
(which might be 500 tokens = ~1 second with an API call). So even adding a KG step yields net savings in
time for the user’s answer, especially when it cuts down LLM reasoning needed.

10.2 Storage and Memory Overhead
Graph data for our usage is relatively small: - If we have, say, 1000 nodes and each with a few properties,
that’s negligible – a few MB of data. - Each relationship is an edge record. 5000 relationships also minimal
(maybe a few MB). - Indices on those might add overhead but again small scale.
Even at a larger estimate: - 10k nodes, 50k relationships: maybe tens of MB on disk (Neo4j’s footprint
might be ~100 MB including index overhead). - 100k nodes, 500k relationships: possibly on the order of 1
GB on disk at most 19 . - If using an embedded solution (SQLite), these sizes would fit easily in memory/
disk.
Memory: Neo4j on JVM may allocate a baseline (e.g., 512MB heap by default) which is fine. MemGraph or
others will allocate based on data size (MemGraph being in-memory might use a couple hundred MB to
hold a moderate graph, which we have to budget for).

32

Given our system already runs local models (which might use GBs of memory), the graph’s overhead is
minor.

10.3 Cost Considerations
We aim for open-source or low-cost solutions: - Neo4j Community: Free to use, self-hosted. Our cost is just
the VM/host we run it on (which we might already have). So essentially, no direct license cost. - Neo4j Aura
(cloud): If we scale or need a managed service, their smallest tier ~ $65/month for up to 3 million nodes/
relationships 26 . That might suffice for us if we go cloud, which is not trivial but not huge either. MemGraph: Free community version. Enterprise features cost money but we may not need them. Amazon Neptune: This has an hourly cost ~ $0.10/hour for a minimal instance 18 plus storage (maybe
another few cents per GB-month). For 24/7 that’s ~$72/month. If our usage is spiky, we could stop it when
not needed or use serverless (Neptune has a serverless pricing model too). But likely, if we’re already in AWS
and need high reliability, we consider this cost. (However, given the small size of our KG, Neptune is a bit
heavy unless we foresee scaling). - SQLite extension: Free, and no separate server – just the cost of our
app’s runtime. This is cheapest but as noted, currently alpha quality. - ArangoDB / JanusGraph /
TigerGraph: These can be self-hosted on our machines to avoid license costs. TigerGraph free edition is
limited in data size, but we likely fall within that limit. JanusGraph is free but requires managing Cassandra
etc (cost = more devops time, which is a form of cost). - Hardware cost: If running on the same server as
other components, it might require a memory upgrade or so. But likely negligible.
Conclusion on cost: Starting with Neo4j community on our existing server keeps monetary cost at $0. Over
time, if it proves valuable, spending a bit on a managed graph DB or a larger instance is justifiable given the
improved capabilities.

10.4 Token and Time Savings
The driving force for this project is to reduce token usage and improve response time accuracy: Eliminating redundant Q&A cycles: Earlier, an agent might ask the user or itself "Do we have the NOAA
endpoint?" requiring either stored memory or searching context. Now, it’s a direct lookup. Each avoided
sub-query could save hundreds of tokens (a question and an answer). - Avoiding hallucinated corrections:
Sometimes LLMs guess wrong and then the user has to correct them, leading to long dialogues. With
authoritative answers, we preempt that. - Token count example: - Before KG: Agent sees a question about
NOAA API, it doesn’t remember, it searches docs (embedding search uses tokens but behind scenes), finds
some context, then composes an answer with maybe 100-200 tokens of "Perhaps the endpoint is X (not
sure)". Round-trip ~500 tokens. - After KG: Agent calls KG tool, gets answer in 0 tokens (tool doesn’t
consume from context window). It then just includes that in answer directly. Maybe answer is 50 tokens and
it's correct the first time. - Multiply this by many questions; we can quantitatively track how many times KG
answered something and estimate the saved tokens. - We predicted perhaps a 20-30% reduction in token
usage on fact-heavy queries. If, say, 30% of our queries per month are fact queries and we cut those tokens
by 90%, that’s a huge cost savings if using API-based LLMs. - Also, by trimming irrelevant context from RAG
(because we now target the search better), we reduce the amount of text we stuff into the prompt. Our
token compression numbers (65% reduction) might improve further with KG filtering.
Finally, user-perceived latency could improve: KG lookups are negligible time, and they might reduce the
need for the LLM to think hard (less tokens to generate). So responses might come faster.

33

We will instrument the system to measure: - Average tokens per response before vs after KG introduction. Frequency of factual errors before vs after. - Query latency average before vs after. We expect improvements
in all areas.

11. Configuration & User Controls
We will add configuration options and controls to make the KG integration flexible and tunable, particularly
in our template-builder UI or config files. This allows enabling/disabling and adjusting the knowledge graph
features as needed.

11.1 Configuration Settings (JSON Example)
In the template-builder configuration (possibly a JSON file or a UI form), we’ll introduce a section for
the Knowledge Graph. For example:

{
"knowledgeGraph": {
"enabled": true,
"backend": "neo4j-community",
// or "memgraph", "sqlite-graph",
"neo4j-aura"
"connection": {
"uri": "bolt://localhost:7687",
"user": "neo4j",
"password": "****"
},
"autoPopulate": true,
// if true, enables automated population
from docs
"refreshInterval": 86400,
// in seconds, e.g., 86400 sec = 1 day
"conflictResolution": "highest-authority", // strategy for conflicts
("manual-review" possible option)
"useCache": true,
// whether to cache KG query results
"queryClassifier":
"heuristic",
// could be "heuristic" or "ml_model" for query routing method
"nl2cypher": true,
// enable natural language to Cypher
translation
"ui": {
"enableGraphExplorer": true,
"port":
7474
// e.g., if Neo4j browser is to be exposed or custom UI
port
}
}
}
Explanation: - enabled : Master switch to turn KG usage on or off. If off, the system should behave as
before (pure RAG + LLM). This is useful for fallback or A/B testing. - backend : Allows switching the graph

34

database backend. We’ll support at least the ones we seriously consider: "neo4j-community", "neo4j-aura",
"memgraph", "sqlite-graph", "postgres-age". Each would trigger appropriate connection logic. connection : Credentials/URIs if needed for external DBs (Neo4j, etc.). For SQLite, maybe a file path and
extension lib path. - autoPopulate : If true, the system will attempt to auto-extract knowledge from
ingested docs (possibly run on upload or periodically). If false, only manual or explicit population happens. refreshInterval : Controls how frequently the automated refresh jobs run (0 to disable periodic
refresh). - conflictResolution : Strategy if conflicting info arises. "highest-authority" (auto choose top
source) vs "manual-review" (flag and require human to resolve) could be options. In most cases, we’ll use
highest-authority with logging. - useCache : If true, enable caching layer for KG queries and combined
retrievals. -

queryClassifier : Option to choose the method to classify queries (just in case we

implement an ML classifier, we can toggle). - nl2cypher : If false, it means we don’t allow the LLM to
dynamically query KG with arbitrary questions — we’d rely on specific tool calls. If true, we enable the
translation capability. - ui sub-object: Controls for any UI components. We might embed a Neo4j Browser
or provide our own. For now, it might just indicate whether to show a "Knowledge Graph" section in the
template-builder UI and maybe an internal port if needed to serve a visualization.
These configurations can be exposed to the user (developer user, not end-user) to tune how the KG
integration behaves.

11.2 Runtime Controls and Overrides
At runtime or via the UI, we also want some manual controls: - Enable/Disable KG for a specific query:
Perhaps a debug feature where one can ask a question and force not using KG to see difference (maybe by
a special prefix or a UI toggle "Trust Knowledge Graph for this question"). This is useful for testing the
impact. - Force KG Update: A button or API that triggers the refresh jobs immediately (rather than waiting
for schedule), in case we know something changed and we need the latest fact now. - Clear or Rebuild KG:
For troubleshooting, an option to wipe the KG and rebuild from sources (if our population can be
automated, this is feasible). - Query Timeout Settings: If a graph query is complex or if the DB is slow, we
might set a max time (like 2 seconds); if exceeded, we fallback to not using that result to not stall responses.
So a config for KG query timeout might be included (though not in example JSON above). - Authority
Thresholds: We might allow configuring that, for example, we prefer not to answer at all (or ask user) if the
best source is below a certain authority. E.g., if something is only found via RAG (authority 3), maybe we
decide either to use it but with a disclaimer or not to use it without human verification. This could be
configured. But likely overkill for now since user would prefer some answer rather than none. - Logging
and Debug Mode: Config to log all KG queries and results, which could be turned on to debug or off to
reduce noise in production logs.
All these knobs ensure that the introduction of KG can be controlled and doesn’t become a black box. We
will likely iterate on these settings as we learn usage patterns.
From a user’s perspective, after implementing this, there might be new UI elements: - Perhaps a
"Knowledge" panel showing which facts were used from KG for the answer. - Possibly an ability to click and
see the source of that fact (like “source: NOAA documentation”). - But careful: we don’t want to overload
end-users. These might remain developer-facing features.

35

12. Testing Strategy
Testing the Knowledge Graph integration is essential to ensure it works correctly and indeed improves the
system. We outline how we will test at unit, integration, and system levels, as well as some benchmarks.

12.1 Unit Tests
We will write unit tests for the following components: - Graph Interface Methods: Simulate a small inmemory or test instance of the graph and test addEntity , addRelationship , getEntity , etc. For
example, add a node and then fetch it to see if it returns correctly. If using Neo4j, we might use a Neo4j test
harness or a Docker container for tests. - NL to Cypher Translation: Provide some known examples to the
translation function and verify it outputs the expected Cypher (or at least one that yields the correct result).
We might stub the LLM with a fake that returns a predetermined query. E.g., for input "What does Skew-T
require?" expect the output query to contain MATCH and REQUIRES . Also test that it handles edge cases
like if asked something out of scope (should maybe throw or return a default). - Query Classifier: Test
various query strings to ensure they are categorized correctly. E.g., "What is the API key?" -> FACT_LOOKUP,
"How to use API?" -> CONTEXT_LOOKUP, "Explain the Skew-T diagram." -> likely CONTEXT, "What and
how ..." (mixed) -> HYBRID. - Conflict Resolver: Create dummy FactResult with different authorities and
values, feed into resolveConflict and ensure it picks the highest authority and logs conflict if values differ.
Also test scenario where top two have same value (no conflict to log). - Cache logic: If we implement a
cache class, test that a query result gets cached and is returned from cache on second call, and invalidation
works (maybe simulate an update triggering cache clear). - Graph Population functions: This is trickier to
test via unit, but we can simulate extraction. For example, feed a known text snippet to
extractEntitiesAndRelationships (we might need to stub the actual LLM call and instead use a
sample JSON we expect) and ensure the function returns the correct structured data. Or if using spaCy,
ensure our patterns extract the right triples.
We should also test error conditions: e.g., if KG.queryCypher gets an invalid query or connection is down,
does it throw and is it handled upstream (perhaps falls back to RAG gracefully).

12.2 Integration Tests
These tests involve the system components working together: - End-to-End Query Answering: Spin up a
test environment with a known small KG (seed it with a few facts). Feed a query to the system and check the
final answer uses the KG fact. For example: - Put in KG: Node API(id:noaa, endpoint:"http://..."). - Ask the
system (perhaps via the API or a function call): "What is the endpoint of NOAA API?" - The expected answer
from LLM agent should contain that exact URL, and ideally come with no hallucinated text. We assert the
answer string contains the URL. - We can also check logs or internal state that KG was queried (maybe
through a mock or flag). - Hybrid Retrieval Test: For a question that needs both facts and context, e.g.,
"How do I use the NOAA RAP API for soundings?" - Ensure the KG provides the endpoint (fact) and RAG
provides an example (like an excerpt from docs). - The final answer should include both (e.g., it should
mention the endpoint URL and also show a usage snippet). - Without KG, the answer might have missed or
guessed the endpoint; we can compare. - Cache/Performance Test: Simulate repeated queries in a loop for
a known fact and see that after first time, subsequent answers are faster or at least hitting cache (maybe
increment a counter in cache to verify). - Multi-Agent Interaction Test: If applicable, test that agents
coordinate properly. For instance, if one agent is responsible for fetching facts and another for composing,
ensure the fact is passed in the ticket. This is more of a system test with the multi-agent framework which

36

may be harder to automate. But we can simulate a scenario where agent A tool-use gets a fact and see if
agent B's prompt includes it. - Update Propagation: Change a fact in the KG (simulate an admin updating
the endpoint). Then ask the question and ensure the new value is used. This ensures no stale data is
hanging in memory or cache.

12.3 Benchmarks
We will benchmark key metrics: - Query Latency: Time from user query to answer with and without KG.
Particularly measure the KG lookup overhead: - Single fact query: e.g., "What's X?" how many ms does KG
retrieval add vs old method? - Complex query with hybrid: does adding KG slow it or speed it? (It might
speed the LLM’s answer formulation, but we measure overall).
We should test at different KG sizes (maybe artificially inflate node count) to ensure our chosen DB scales
for our foreseeable needs.
• Token Usage: We can replay a set of user queries (if we have logs or sample questions) on the old
system vs new and count tokens consumed. This will directly show reduction. Particularly look at
repetitive ones.
• If possible, automate it: have a script feed the same list of questions to both configurations and
measure the total tokens used.
• Accuracy Improvement: We can create a QA dataset of factual questions (with known correct
answers) that the old system often got wrong due to hallucination. Run it through old vs new and
see how many are answered correctly. For example:
• "What category is Cairns 880 helmet in?" (Expect "Firefighting" from KG, whereas an LLM without
might not know or might guess).
• "What is the NOAA RAP API endpoint?" (Expect correct URL vs hallucination).
• "What version of D3.js are we using?" (If KG stored it, we expect an exact answer, vs an LLM might
not know our project's version).
We measure the accuracy (% correct). We aim for 100% on those known fact questions after KG.
• Conflict Handling: Intentionally introduce a conflict scenario in a test (like have KG with outdated
info and see if the system updates it from a simulated API). Ensure it resolves properly and measure
the time it took.
• Scalability Test (if needed): Populate large dummy graph (e.g., 100k nodes) and run some heavy
queries to see if latency is still acceptable. If we find some queries slow beyond threshold, we might
optimize or limit those kinds of queries in practice.
• Resource Usage: Monitor memory and CPU when KG is under load vs baseline. E.g., running 100 KG
queries concurrently – does the DB handle it within resource limits?

37

• For Neo4j, it can handle concurrent queries well up to certain threads; for SQLite extension,
concurrency might be limited by GIL in Python or so. We'll ensure our usage (likely low QPS) is fine,
but good to test maybe with a multi-thread script hitting KG.
All these tests and benchmarks will be conducted in a staging environment to validate performance and
stability before full deployment.

13. Migration & Rollout Plan
We will integrate the knowledge graph in phases to minimize risk and allow iterative improvements:

13.1 Phased Deployment
• Phase 1: Prototype & Internal Testing. Implement the KG data model and basic integration locally.
Manually seed a few facts (like the NOAA API info, a couple of product categories). Enable it for a
subset of agent queries in a dev environment. We’ll test using our own queries to ensure it works
(using the strategies in section 12).
• Outcome: a working vertical slice (someone asks, e.g., "What's NOAA API endpoint?" and the system
answers instantly from KG).
• This phase also includes building any needed admin UI for us to inspect and edit the graph, plus the
NL->Cypher translator development.
• Phase 2: Integrate with RAG in staging. Expand the KG content a bit (cover the main use cases
we've identified: FreeFlight weather and WPSG products, plus any other glaring needs). Deploy the
updated system to a staging environment or a limited user group.
• Here we turn on hybrid retrieval. We might do some A/B comparison: for half the queries use KG, for
half don't, to measure difference (if we have enough traffic).
• Focus on ensuring the combined answers are good – tune prompt format for LLM to properly
incorporate the facts (the LLM might need instructions like "Prefer the provided facts for any factual
questions").
• Phase 3: Automated Population & Expansion. Start hooking up automated extraction pipelines to
feed more info into KG. For example, ingest all relevant docs and codebase info. Also, enable the
periodic refresh jobs. In this phase, the graph grows and we test that performance remains fine.
• We also implement the conflict resolution and authority logic fully here, including live API calls for
certain known data points.
• Possibly at this stage, we integrate semantic caching with KG results to ensure efficiency.
• Phase 4: Full Deployment & Monitoring. Roll out the knowledge graph integration to production
(or to all users if there's not a separate prod). Because we have the ability to disable KG via config, we
keep a kill-switch ready if any issues arise.

38

• We closely monitor metrics: any errors in graph queries, any slowdowns, token usage, etc., to verify
the benefits.
• We gather user feedback indirectly: are we seeing fewer follow-up questions asking for clarifications
(a sign that answers are clearer and more factual)?
• Also monitor the conflict log: if we see frequent conflicts from certain domains, we may need to
adjust those areas.
During rollout, communication with the team/users is key: highlight that the system now has this
“Knowledge brain” and that they should expect more precise answers for factual queries. Encourage them
to report if any fact seems wrong.

13.2 Backward Compatibility
We design the integration such that if the KG is disabled, the system still works as before. This means: - The
orchestrator should always check if knowledgeGraph.enabled is true. If false, it just skips any KG steps
and uses RAG + LLM only. - All prompts and agents should not become dependent on KG presence beyond
an optional tool. For instance, an agent might have a tool "KG.search" which if not available, it should still
handle it (maybe the tool just returns null or the agent knows to proceed without it). - The system should
not degrade answers if KG is off – they might just be less accurate, but the process flows should still
complete.
We will maintain support for operating without a graph to allow smooth fallback or if we want to test
differences.
Data Migration: If we have existing data that can feed the KG, that’s one migration: e.g., migrating product
data into KG. That’s more of a one-time import than migration. It doesn’t affect existing systems (they still
keep their data; KG is an add-on).
If we decide to incorporate KG strongly, in the future we might phase out some of the large prompt
knowledge we currently supply. But initially, we will probably still keep providing some important info in
prompts as redundancy until KG is proven. Slowly, we can remove those redundancies.
Finally, if we decide in the future to switch graph backends (say from Neo4j to MemGraph or to Neptune),
that would involve exporting the data and importing to the new store, but our interface abstraction should
minimize code changes. That is a different kind of migration (backend migration) which we are prepared for
by not tying the entire code to a specific DB library too strongly.

14. Monitoring & Observability
To ensure the Knowledge Graph engine is functioning well, we will add monitoring around its usage and
effects. Key things to monitor:

14.1 Metrics to Track
• KG Query Rate: How many knowledge graph queries (or lookups) are being performed per hour.
This includes both direct queries and NL->Cypher calls. This helps see utilization. If it's very low,
maybe system isn’t using KG as much as expected (maybe misclassification of queries).

39

• KG Query Latency: The average and percentile (p95) time spent on KG queries. If this starts rising,
maybe the DB needs tuning or is under-resourced.
• Cache Hit Rate: If we implement caching for KG results, measure hits vs misses. A high hit rate
means we save repeated computations – good. If low, maybe our queries are too unique.
• Token Savings: We can instrument a counter for tokens used by LLM per query, and specifically
measure those that used KG vs those that didn’t. Over time, this can be aggregated into how many
tokens (and cost) were saved thanks to KG. E.g., “This week, 200 queries were answered via KG with
no LLM cost, saving ~100k tokens”.
• Answer Accuracy (proxy): Hard to directly measure, but we can track how often users re-ask the
same question or correct the assistant. If our system has a feedback or if user asks “are you sure?” or
something. Also, we could periodically run an evaluation script (like ask a set of known questions and
verify answers). But in live monitoring, perhaps treat any conversation where user says "No, that's
wrong" as an error – check if that was a fact KG should have had.
• Graph Size Growth: Number of nodes and relationships over time. This is to catch uncontrolled
growth (maybe a runaway ingestion duplicating tons of nodes). It also helps planning capacity. We
might push these counts daily to monitoring.
• Conflict occurrences: Each time a conflict is logged (i.e., we found KG had a different value than live
API or doc), count it. If conflicts spike, maybe our update frequency is insufficient or something’s off.
• Agent fallback rate: If we have a measure when KG fails to answer and LLM had to guess, track
that. We want this to approach zero for targeted domains.

14.2 Dashboard and Alerts
We will create a dashboard (using whatever monitoring stack – could be Grafana, CloudWatch, etc.)
showing: - Live KG query throughput and latency. - KG hit vs RAG usage – maybe a pie chart or ratio of how
many queries are classified as FACT vs CONTEXT vs HYBRID. If the majority remain CONTEXT, maybe fine,
but if some are misclassed. - Token usage chart: one line for tokens per query average now vs historical
baseline. - Knowledge Graph size chart. - Also a panel listing recent conflict logs (for devs to review, maybe
integrated with a logging system where each conflict is an event we can inspect). - Possibly a sample of
cached facts usage.
Alerts: - If KG query latency goes above a threshold (say >500ms average or many timeouts), alert – maybe
the DB is down or slow. - If conflict count suddenly jumps (like 100 conflicts in a day vs usual 5), perhaps a
data source changed (maybe an API updated a lot of values). - If KG query rate goes to zero unexpectedly
(perhaps the KG integration broke and no one is using it), alert to check the system. - If any error in KG
subsystem (failed to connect to DB, query errors) happens frequently, definitely alert.
Logs: We will log important events at INFO level: - Each time a KG query is executed (maybe log the query
and time taken). - If NL->Cypher translation is used, log the NL question and the resulting query for
debugging correctness (especially early on). - Conflict logs as mentioned with details of sources. - Warnings
if any inconsistent data or if an automated update changed a critical fact.
Since the KG is critical, we might also implement a health check for it: - E.g., an endpoint /health/kg that
tries a simple query (like MATCH (n) RETURN count(n)) to see if the DB responds, and integrate that into our
overall health checks.

40

All these observability measures will ensure we can maintain the KG and quickly react if something goes
wrong (like the graph DB service goes down, or data becomes stale).

15. Future Enhancements
Once the Knowledge Graph is in place, there are several powerful enhancements and extensions we can
consider to further improve our system:

15.1 Graph Embeddings for Similarity & Recommendation
We can compute graph embeddings for entities, which are vector representations capturing the graph
structure/context of each node 27 . Techniques like Node2Vec, GraphSAGE, TransE, ComplEx, RotatE
could be used to embed nodes in a vector space where similarity implies relatedness 28 29 . - Use cases: Finding analogous entities: If a user asks "Is there an API like NOAA for European weather?" we could find
similar nodes to NOAA_RAP_API in the embedding space (maybe it surfaces another weather API if in KG). Product recommendations: Given a product node, find nearest neighbor products (this could complement or
replace some Algolia full-text search logic with knowledge-based similarity). - Context expansion: If an agent
is working on something (say Skew-T), we could fetch not just direct neighbors but also entities with similar
relationship patterns (e.g., other visualizations that also require sounding data). - We would likely use an
existing library or the Neo4j Graph Data Science plugin (if available) to generate these embeddings.
MemGraph also has some graph algorithms built-in. - These embeddings could also feed into our vector
RAG system: we might combine or compare them with text embeddings for a more holistic similarity search
(one could imagine a Hybrid search that ensures two pieces of code that operate on similar entities are
found even if wording differs).

15.2 Inference Rules and Reasoning
Beyond storing explicit facts, we can encode domain logic: - Transitive reasoning: For example, if A
requires B and B requires C, we can infer A indirectly requires C (maybe as a suggestion). We could
implement a rule that automatically creates a requires (transitive) relationship or at least can
answer that query via pathfinding. Neo4j can do variable-length path queries or we could materialize some
transitive closures for speed. - Rule-based inference: Using technologies like rule engines or even
something like Cypher or Gremlin queries as rules. E.g., a rule: "If a product is PRIMARY_PRODUCT and
has_category X, then mark that category as high_priority for search." This could reflect in data by setting a
property or relationship weight. - Constraints: Possibly ensure data integrity: e.g., if an API node has an
endpoint property, enforce format (we can do this in code or via constraints if possible). - Deduction:
Identify implicit relationships: e.g., if we know "Library X is part of Framework Y" and "Framework Y is
required by Module Z", we deduce "Module Z uses Library X" (maybe not directly stated but logically true). The risk with automated inference is introducing noise. We should implement carefully and perhaps tag
inferred edges differently or with lower confidence.

15.3 Multi-Modal Knowledge Graph
Our current KG deals with text-based facts primarily. In future: - Images/Diagrams: We could attach images
to certain nodes (like an image of the Skew-T diagram, or product images). The KG could store a URL or
reference to an image file. Our system could then retrieve and even display it if a user asks (embedding
images in answer). This merges into multi-modal responses. - We could have a node type "Diagram" or

41

"Figure" related to an entity. E.g., Skew-T node has_diagram -> [file reference]. If user asks "Show me a Skew-T
diagram", the agent can fetch that. - Geospatial or other data: If some knowledge is geospatial (maybe not
in our immediate use cases, but e.g., if we had locations in KG), we could integrate location-based
reasoning. - Temporal data: We might incorporate timeline info (like when certain versions were released,
etc.), enabling questions like "When did version 2.0 release?" answered from KG.
Multi-modality could also mean using the KG to orchestrate calling different types of tools: - e.g., if a
question involves an image concept that is stored in KG, the system might decide to retrieve an actual
image from a repository and show it.

15.4 Federated and External Knowledge
Our KG might not exist in isolation. We can leverage external KGs: - Wikidata/DBpedia integration: These
are large public knowledge graphs. For general world knowledge questions (outside our project’s scope),
our system could query Wikidata. For instance, if asked "Who developed D3.js?" our internal KG might not
store that, but Wikidata might. We could integrate a lookup: either dynamically (an API call to Wikidata
SPARQL endpoint) or by having imported relevant parts into our KG. - Cross-organization knowledge: If
this system scales in an enterprise environment, perhaps each project or team has its own subgraph, and
the authority engine might aggregate them or switch context based on project. - SaaS Multi-tenancy: If
offering this as a service, each client might have their knowledge graph. A future enhancement is to allow a
unified query across a global graph plus tenant-specific graphs with proper access control.
• Web Knowledge & LLM synergy: Another advanced idea is to use the KG to ground web browsing.
For example, if the agent has to search the web (like browsing tool), it can use KG to formulate better
queries or to verify info from web pages. Conversely, when the agent finds new info on the web, it
could feed it into the KG (with validation) to remember it for next time.

16. Alternative Approaches Considered
We considered other approaches to solve the “authority” problem without a full graph system:
16.1 Status Quo: Pure RAG (no structured KG) – This would mean continuing to rely on vector search over
documentation to fetch facts. - Pros: Simpler, no new system to maintain. LLM finds answers in docs if
present. - Cons: Unreliable for pinpoint facts. If the doc snippet isn't retrieved or doesn’t exist, the LLM
hallucinates. Also, multi-hop reasoning is hard (LLM has to piece together bits across docs – high chance of
error). - Pure RAG doesn't fundamentally solve hallucinations; at best it reduces them by providing text, but
if text is absent or ambiguous, the LLM still guesses. Our experience of 67% retrieval accuracy shows it's not
sufficient for 100% correctness.
16.2 LLM with Tool Functions or Plugins (but no persistent KG): For instance, using the new functioncalling capability of LLMs to call an “API lookup” or directly connect to external sources on the fly. - Pros:
Offloads factual queries to curated APIs (e.g., a weather API, a documentation Q&A API, etc.). You could
implement numerous small tools (like one function for each known fact domain). - Cons: Doesn’t scale well –
you need a specific tool for each type of fact, and you still need to maintain those endpoints. Also, the
results aren’t stored, so the LLM might call the same function repeatedly (unless you cache at conversation
level). - Example: An LLM plugin could be made to answer "software version queries" by searching a

42

database. But you'd end up building a mini knowledge base anyway, just accessed differently. And each tool
covers one slice of knowledge whereas a KG is unified and can handle new query types more flexibly.
16.3 Use a Relational Database (SQL) to store facts: Essentially, treat it like storing facts in tables and use
SQL queries via an LLM. - Pros: We could leverage existing SQLite (which we already have for RAG) with
some structured tables for facts. SQL is familiar and many tools exist. The LLM could even generate SQL
queries to get info. - Cons: Harder to model complex relationships without many join tables. SQL queries for
multi-hop relationships get complex (or require recursive CTEs). The flexibility to add new types of nodes/
relations is lower – you'd have to alter schema (unless you use a generic EAV schema which becomes
clunky). Also, the semantics of a graph (paths, centrality) are not naturally expressed in SQL. - Indeed,
property graphs and SPARQL exist because relational models weren’t convenient for these tasks. We
anticipate many queries will be "what is related to what" – doable in SQL but not as elegantly or quickly as a
native graph query.
16.4 Embeddings only (no symbolic KG): Another approach is to rely on embedding vectors for entities to
answer factual similarity. e.g., vector search can sometimes be used for Q&A: "NOAA API endpoint" might
vector-match a snippet containing it. - Pros: We somewhat do this in RAG; no need for discrete symbols or
curation. - Cons: It doesn’t guarantee exact matches and can be fooled by semantic closeness that isn’t an
actual answer. Also cannot easily do multi-hop reasoning (embedding two hops away might not be near in
vector space). - We already saw limitations as RAG struggled with multi-hop questions 8 , which is why we
moved beyond just embeddings.
Given these alternatives, the Knowledge Graph approach stands out as the one offering deterministic
accuracy and structured multi-hop reasoning. It requires more initial setup but provides a foundation
that can grow and adapt to our needs (and as we’ve seen, can incorporate those alternative approaches as
needed, e.g., we still use embeddings and we still call live APIs – just under the KG’s guidance).
Therefore, we concluded that implementing a Knowledge Graph as described is the best path forward to
achieve our goals of eliminating hallucinations and making our LLM system more efficient and reliable.

17. References & Citations
Below are references and sources that informed this design, including industry practices and research on
combining knowledge graphs with LLMs:
• Microsoft Research – GraphRAG: Combining Knowledge Graphs with RAG: Demonstrates building
an LLM-generated KG for private data to improve complex question answering 3 7 .
• Neo4j News (2023) – Knowledge Graphs Are Making LLMs Less Dumb: Discusses how KGs reduce
hallucinations and provide up-to-date, connected context for LLMs 6 .
• NVIDIA Technical Blog – LLM + Knowledge Graph Integration: Confirms that augmenting RAG with
structured knowledge improves reasoning accuracy and reduces hallucination 4 1 . Also outlines
traditional vs LLM-based extraction techniques 24 30 .
• Cambridge Intelligence Blog (2025) – Graph Database Comparison: Compared Neo4j, TigerGraph,
JanusGraph, Neptune, ArangoDB, etc., highlighting differences in model (property vs RDF),
performance, and features 31 32 .

43

• Linkurious Blog (2025) – Choosing the Best Graph DB: Provided practical notes on each database
(MemGraph in-memory speed 33 , Arango multi-model ease 16 , JanusGraph scalability with more
setup 19 , TigerGraph deep traversal performance 20 ).
• AgentFlare SQLite Graph Extension (2023): Open-source project adding Cypher support to SQLite
22 , indicating possibility of embedding the graph store.
• Apache AGE Documentation: Details on bringing graph querying to PostgreSQL 23 , which
influenced our consideration of Postgres-based solutions.
• Medium Article – “Solving Hallucination with Knowledge Graphs” by James Stakelum:
Emphasizes how structured knowledge prevents LLM confusion by providing clear factual context
2 .
• Knowledge Graph Embedding Research: TransE, RotatE, ComplEx models for representing KGs in
vector space, useful for future similarity search improvements 28 29 .
• Neo4j Documentation and Cypher Reference: Used for crafting schema and query examples in
Cypher.
• W3C RDF/OWL Standards: Considered for ontology but decided on property graph for flexibility;
RDF’s subject-predicate-object model noted as an alternative 5 .
These references support the decisions and strategies laid out in this SDD, demonstrating that our
approach aligns with state-of-the-art techniques and practical experiences in the field of knowledge-infused
LLM systems. Each citation in the document (formatted as 【source†lines】) points to the exact source for
verification of facts and claims. The design synthesized this research to tailor a solution optimal for our LLM
Commander project’s needs.

1

4

9

10

11

12

24

27

30

Insights, Techniques, and Evaluation for LLM-Driven Knowledge Graphs |

NVIDIA Technical Blog
https://developer.nvidia.com/blog/insights-techniques-and-evaluation-for-llm-driven-knowledge-graphs/

Solving the Hallucination Problem Once and for all using Smart Methods | by James Lee Stakelum |
Medium
2

https://medium.com/@JamesStakelum/solving-the-hallucination-problem-how-smarter-methods-can-reduce-hallucinationsbfc2c4744a3e
3

7

8

Welcome - GraphRAG

https://microsoft.github.io/graphrag/
5

13

16

17

18

19

20

21

31

32

How To Choose A Graph Database: We Compare 8 Favorites

https://cambridge-intelligence.com/choosing-graph-database/
6

Knowledge Graphs Are Making LLMs Less Dumb

https://neo4j.com/news/knowledge-graphs-are-making-llms-less-dumb/
14

15

33

Choosing the best graph database: A practical guide

https://linkurious.com/blog/choosing-the-best-graph-database/
22

GitHub - agentflare-ai/sqlite-graph: SQLite Graph Extension

https://github.com/agentflare-ai/sqlite-graph
23

apache/age: Graph database optimized for fast analysis ... - GitHub

https://github.com/apache/age

44

25

GraphRAG Explained: Enhancing RAG with Knowledge Graphs | by Zilliz | Medium

https://medium.com/@zilliz_learn/graphrag-explained-enhancing-rag-with-knowledge-graphs-3312065f99e1
26

Best Graph Databases for 2025: Top 10 Reviewed - Galaxy

https://www.getgalaxy.io/learn/data-tools/best-graph-databases-2025
28

29

Knowledge graph embedding - Wikipedia

https://en.wikipedia.org/wiki/Knowledge_graph_embedding

45


