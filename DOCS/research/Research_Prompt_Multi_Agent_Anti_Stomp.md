
# Research Brief — Multi‑Agent **Anti‑Stomp** Mechanisms
**Use this prompt verbatim with a browsing‑capable research model.**  
**Goal:** Produce a defensible, implementable playbook to prevent multi‑agent systems from clobbering each other’s work (a.k.a. “stomp”), across single‑process, multi‑process, and distributed deployments.

---

## ROLE
You are a **PhD‑level distributed systems & LLM‑orchestration researcher**. You combine rigor (papers, proofs, benchmarks) with pragmatic engineering (locks, leases, idempotency keys, queues, MVCC, CRDTs). You must deliver implementable guidance, not just theory.

## OBJECTIVES
1. **Define the stomp problem** across shared resources (filesystems, DB rows, KV keys, message queues, knowledge graphs, docs).  
2. **Survey & classify** anti‑stomp mechanisms (pessimistic/optimistic locking, MVCC, CRDT/OT, leader election, leases, CAS/versioning, idempotency keys, dedupe, exactly‑once-ish delivery, sagas/outbox, vector/Lamport clocks, epoch tokens, sharding).  
3. **Design patterns** for three tiers:  
   - A) **Single process / single host** (threads, asyncio, fcntl/flock).  
   - B) **Multi‑process / single host** (file locks, Unix domain sockets, SQLite/Postgres advisory locks).  
   - C) **Distributed** (Postgres transactional locks/MVCC, Kafka/Redpanda semantics, Redis locks & RedLock caveats, ZK/etcd/Consul leases, Raft leaders, CRDT merges).  
4. **Decision matrix**: choose mechanisms by constraints (consistency, latency, failure model, offline/air‑gapped, cost, complexity).  
5. **Reference designs** & minimal pseudocode for:  
   - Idempotent job handling (idempotency key + CAS).  
   - Leased writer with TTL + renewal + fencing token.  
   - MVCC + merge policy (conflict resolver strategy table).  
   - Queue consumer with dedupe (exactly‑once‑ish) and poison‑pill handling.  
6. **Test plan**: concurrency/fault injection matrix (time skew, partitions, crashes, duplicate/reordered messages).  
7. **Telemetry/ops**: metrics and logs to prove anti‑stomp works in the wild (liveness, fairness, lock contention, retries, merges).  
8. **Risks & mitigations**: deadlocks, live‑locks, split‑brain, clock drift, lease loss, partial failure, thundering herds.

## SCOPE
- LLM **multi‑agent** orchestrations (tool use, background workers, doc writers, RAG updaters) that share resources.  
- **Offline‑friendly** options when coordination services aren’t available.  
- **Cost‑aware** solutions (prefer simple, robust primitives first).

**Out of scope:** formal verification proofs, bespoke consensus protocols beyond mainstream (Raft/Paxos references fine).

## KEY QUESTIONS
- When is **pessimistic locking** preferable to **optimistic versioning**?  
- How to implement **fencing tokens** (a.k.a. monotonic epochs) with leases to prevent stale writers?  
- Are **Redis‑based locks** sufficiently safe? Under what conditions? Alternatives?  
- For **file‑based artifacts**, what’s the safest cross‑process lock (flock vs lock‑files vs sqlite/posix)?  
- How do **MVCC** and **CRDT/OT** compare for concurrent document/code edits?  
- What is a practical recipe for **exactly‑once‑ish** processing with at‑least‑once transports?  
- How to **detect & resolve conflicts** deterministically in knowledge graphs or vector DB metadata?  
- Minimum viable **anti‑stomp** for a single‑host agent farm? Path to **distributed** later?

## METHOD (How to research)
1. **Collect 10–15 primary sources** (papers, vendor docs, credible blog posts, RFCs). Prioritize:  
   - Classic concurrency (Lamport clocks, vector clocks, MVCC).  
   - Leader election & leases (Raft, etcd/Consul/ZK).  
   - Queue semantics (Kafka, Redpanda) and transactional outbox/saga patterns.  
   - CRDT/OT surveys and practical merges for text/code.  
   - Redis locking & **RedLock** critiques (pro/contra).  
2. **Extract design constraints** from each source (failure model, clock assumptions, throughput, complexity).  
3. **Synthesize**: map mechanisms → constraints; produce trade‑off tables and “use‑when” rules.  
4. **Propose reference designs** (A/B/C tiers above).  
5. **Validate**: draft a fault‑injection test plan; reason about worst‑case latency, starvation, and recovery.

## DELIVERABLES
1. **Executive 1‑pager** (plain English): problem, recommended baseline, why.  
2. **Taxonomy & decision matrix** (table): mechanism vs consistency, cost, complexity, ops burden, offline suitability.  
3. **Reference designs** (A/B/C) with **sequence diagrams** (Mermaid) and **pseudocode**.  
4. **Test plan**: fault matrix + reproducible scripts (bash/pytest pseudo).  
5. **Run‑book**: ops KPIs, alerts, “break‑glass” procedures.  
6. **Risk register** with mitigations & owner actions.  
7. **Annotated bibliography** with **inline citations** in the doc.

## EVALUATION CRITERIA
- **Correctness & safety:** deadlock/livelock analysis; stale‑writer prevention (fencing).  
- **Liveness & fairness:** starvation mitigation, backoff/jitter.  
- **Determinism:** conflict resolution yields repeatable outcomes.  
- **Simplicity & cost:** minimal moving parts for tier A/B; incremental path to C.  
- **Testability & observability:** are failures easy to reproduce and detect?

## REQUIRED OUTPUT FORMAT (single Markdown file)
**Title:** “Multi‑Agent Anti‑Stomp — Survey, Patterns, and Reference Designs (v1)”  
**Sections (exact order):**
1. Executive Summary (≤300 words)  
2. Problem Statement & Definitions  
3. Taxonomy of Anti‑Stomp Mechanisms  
4. Decision Matrix (table)  
5. Reference Designs (A/B/C) — with Mermaid sequence diagrams  
6. Pseudocode Snippets (idempotency key, lease+fence, MVCC conflict resolver, queue dedupe)  
7. Test & Fault‑Injection Plan  
8. Telemetry & SLOs  
9. Risks & Mitigations  
10. “When to Use What” Decision Tree  
11. Migration / Retrofit Guidance  
12. Red Flags & Anti‑Patterns  
13. Open Questions  
14. Annotated Bibliography (with links and 1–2 sentence takeaways each)

## STYLE & CITATIONS
- Be concise and **practical**; prefer bullets and tables.  
- **Cite** inline with `[Author, Year]` and include links. Prefer **primary** sources.  
- Use **Mermaid** for diagrams.  
- Pseudocode only (language‑agnostic).  
- Call out assumptions and clearly label **inferred** conclusions.

## STARTING HYPOTHESES (pressure‑test these)
- For single‑host multi‑process, **file locks (flock) + idempotency keys** is a robust baseline.  
- In distributed settings, prefer **lease + fencing token** over bare locks; avoid naive RedLock for critical correctness.  
- **MVCC + deterministic merge policy** beats coarse locks for doc‑like artifacts when latency matters.  
- **Exactly‑once‑ish** = idempotent handlers + transactional outbox + consumer dedupe + retries.

---

**Success =** a crisp, citable playbook and reference designs that a senior engineer can implement **this week** without stepping on their teammates. (No two agents should edit the same pizza slice at once.)
