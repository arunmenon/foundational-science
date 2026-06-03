# GAAMA: Graph-Augmented Associative Memory for Multi-Hop Agent Recall

## Executive Summary

GAAMA ("Graph Augmented Associative Memory for Agents," arXiv:2603.27910) is a long-term memory system for multi-session conversational agents that replaces flat vector retrieval with a *concept-mediated* knowledge graph and a hybrid retrieval scheme combining cosine kNN with edge-type-aware Personalized PageRank (PPR). Its central design choice is to avoid the "mega-hub" pathology of entity-centric graphs (where person nodes accumulate 400–500+ edges) by routing traversal through topic-level *concept* nodes, yielding graphs roughly 30x sparser. On LoCoMo-10 it reports 79.1% mean reward (79.2% with its GRAFT repair layer), about +4.2 points over a tuned flat-RAG baseline, with its biggest gains on temporal (+16.1 pp) and multi-hop (+4.9 pp) questions; on the newer agentic MemoryArena benchmark it matches or modestly beats full-context baselines with advantages that grow with dialogue length. The work is a small-team, single-developer-grade research artifact (3 authors, MIT-licensed GitHub repo with ~8 commits, SQLite-based — notably *not* a heavyweight graph database), reproducible on GPT-4o-mini + text-embedding-3-small, but it is honest that most of its remaining errors come from graph *construction* (over-generic and near-duplicate concepts) rather than the retrieval algorithm, and it provides no hard latency/cost numbers. For PayPal Fraud/Risk, the interesting transfer is not the conversational use case per se but the *concept-mediated traversal pattern* applied to fraud's natively graph-structured entities (accounts–devices–IPs–merchants), enabling multi-hop investigative recall across sessions.

---

## What's New in the Window

The research window is April–June 2026 (today: 2026-06-03). The relevant primary artifacts:

- **GAAMA: Graph Augmented Associative Memory for Agents** — arXiv:2603.27910. Authors: Swarna Kamal Paul, Shubhendu Sharma, Nitin Sareen. **v1: 2026-03-29; v2: 2026-05-13.** The v2 revision is the in-window update and is the version this report analyzes. ([abs](https://arxiv.org/abs/2603.27910), [html v2](https://arxiv.org/html/2603.27910v2), [pdf](https://arxiv.org/pdf/2603.27910)). The discovery note's "v2 May 14" is within a day of the recorded 2026-05-13 revision date.
- **GitHub reference implementation** — `swarna-kpaul/gaama`, MIT license, 100% Python, SQLite + sqlite-vec + FTS5 backend, GPT-4o-mini extraction, text-embedding-3-small embeddings, LoCoMo evaluation scripts. ~6 stars, 1 fork, ~8 commits, no tagged releases at time of review. ([repo](https://github.com/swarna-kpaul/gaama))

Companion/related works cited in the discovery context (all v1, submitted just before the window but framing the same problem space):

- **"Knowledge Access Beats Model Size: Memory Augmented Routing for Persistent AI Agents"** — arXiv:2603.23013, submitted 2026-03-24. Authors: Xunzhuo Liu, Bowei He, Xue Liu, Andy Luo, Haichen Zhang, Huamin Chen. Shows an 8B model + retrieved memory recovers ~69% of a 235B model's F1 at ~96% lower cost; combines verbatim turn-pair memory, hybrid dense+BM25 retrieval, and confidence-based (log-prob threshold τ=0.50) escalation routing. ([html](https://arxiv.org/html/2603.23013v1))
- **"Did You Check the Right Pocket? Cost-Sensitive Store Routing for Memory-Augmented Agents"** — arXiv:2603.15658, submitted 2026-03-18. Author: Madhava Gaikwad. Treats *which memory store to query* as a cost-sensitive routing decision rather than searching all stores. ([pdf](https://arxiv.org/pdf/2603.15658))

Key evaluation substrate (referenced, not authored by the GAAMA team):

- **MemoryArena: Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks** — arXiv:2602.16313, submitted 2026-02-18. Lead author Zexue He et al. (14 authors incl. Yejin Choi, Alex Pentland). Tasks are interdependent and multi-session: agents acquire memory through environment interaction and must reuse it for later actions. Crucially, it reports that systems near-optimal on LoCoMo "perform poorly in our agentic setting." ([abs](https://arxiv.org/abs/2602.16313))

**Honesty note on the IDs:** the `2603.*` arXiv identifiers correspond to a March 2026 submission cycle (YYMM = 2603), and the GAAMA v2 revision lands inside the April–June window. All numbers below are from the v2 HTML.

---

## Technical Deep-Dive

### Problem framing and the core bet

Prior agent-memory designs fall into two camps: (1) **flat RAG** over conversation chunks, which loses structural relationships needed for multi-hop and temporal reasoning, and (2) **entity-centric knowledge graphs** (e.g., HippoRAG style), which in conversational data create *mega-hubs* — a single person or "user" node accumulating 400–500+ edges — that dilute PPR mass and make traversal uninformative. GAAMA's bet is that **topic-level concept nodes** (e.g., `pottery_hobby`, `camping_trip`), explicitly *not* person names or generic terms, give cross-cutting thematic traversal paths while keeping the graph ~30x sparser than entity-centric designs.

### Three-step graph construction

1. **Episode preservation (no LLM).** Each conversation turn is stored verbatim as an *episode* node; episodes in a session chain via `NEXT` edges (temporal order). Linear time, no LLM calls.
2. **Fact + concept extraction (LLM).** An LLM extracts *facts* (atomic assertions, with relative dates resolved to absolute dates, linked to source episodes via `DERIVED_FROM`) and *concepts* (topic labels). Episodes link to concepts via `HAS_CONCEPT`; facts link via `ABOUT_CONCEPT`.
3. **Reflection synthesis (LLM).** A second pass generates *reflections* — higher-order insights spanning multiple facts (generalized patterns/preferences), linked to supporting facts via `DERIVED_FROM_FACT`.

**Schema — 4 node types, 5 edge types:**

| Node types | Edge types (source → target) | base transition weight |
|---|---|---|
| Episode, Fact, Reflection, Concept | `NEXT` (Episode→Episode) | 0.8 |
| | `DERIVED_FROM` (Fact→Episode) | 0.8 |
| | `HAS_CONCEPT` (Episode→Concept) | 0.8 |
| | `ABOUT_CONCEPT` (Fact→Concept) | 0.8 |
| | `DERIVED_FROM_FACT` (Reflection→Fact) | 0.5 |

### Hybrid retrieval (no LLM calls at query time)

A five-step pipeline fuses semantic similarity with graph structure:

1. **kNN candidate pool + seed selection.** Retrieve `2B` nodes by cosine similarity (`B = max_facts + max_reflections + max_episodes`); top `k=40` become PPR seeds with weight `w_seed(n) = sim(n,q)`, normalized into a teleport distribution.
2. **Graph expansion.** From seeds, traverse to depth `d=2`, collecting local-subgraph edges; graph-discovered nodes absent from the kNN pool are fetched in.
3. **Edge-type-aware transitions.** Each edge gets effective weight `w̃_ij = w_base(t)` (table above), normalized per-source: `P_ij = w̃_ij / Σ_k w̃_ik`. **Hub dampening** scales down outgoing weights for high-degree nodes: `w̃_ij^damped = w̃_ij · min(1, θ/deg(i))` with threshold `θ=50`.
4. **Personalized PageRank.** Iterate `r_j^(t+1) = (1−α)·v_j + α·Σ_i r_i^(t)·P_ij + α·S^(t)·v_j` with damping `α=0.6`, sink-mass redistribution `S^(t) = Σ_{deg(i)=0} r_i^(t)`, tolerance `1e-6`, max 200 iterations.
5. **Additive scoring.** `score(n) = b(n) · (w_ppr · ppr(n) + w_sim · sim(n,q))` with `w_ppr = 0.1`, `w_sim = 1.0`. The deliberately small `w_ppr` means **graph signal augments, never overrides, semantic relevance** — a conservative design choice that also caps how much the graph can help. `b(n)=1.0` for extraction-time nodes, `0.85` for GRAFT-created facts.

This is the key architectural distinction vs prior art: PPR over a *sparse concept-mediated* graph with *edge-type-weighted* transitions and *hub dampening*, rather than uniform PPR over a dense entity graph (HippoRAG) or no graph at all (RAG/Mem0/A-Mem).

### GRAFT: post-retrieval graph repair

GRAFT ("Graph Repair by Augmenting Facts & Topology") is a six-phase corrective layer that activates only when retrieval looks insufficient: (1) LLM **sufficiency scoring**; (2) **decomposition** into 1–3 analysis questions; (3) **graph exploration** for each; (4) **root-cause diagnosis** (missing fact vs missing concept connection) proposing minimal `CREATE_FACT`/`CREATE_CONCEPT` edits; (5) **verification gate** filtering edits; (6) **execution** with near-duplicate rejection (cosine >0.90) and hedging-phrase blocking. It is an *online graph self-repair* mechanism — conceptually distinct from one-shot construction — but in practice it fired on only **3.1% of LoCoMo-10 queries** (47 questions, 81 edits).

### What changed vs prior art

- vs **flat RAG**: adds multi-abstraction hierarchy (episode/fact/reflection) + graph traversal; hierarchy alone is worth +2.9 pp, graph adds +1.2 pp.
- vs **HippoRAG** (entity KG + PPR): swaps entity nodes for concept nodes to kill mega-hubs (~30x sparser), adds edge-type-aware transitions and hub dampening.
- vs **Mem0 / A-Mem / Nemori**: keeps verbatim episodes as provenance anchors rather than destructive summarization/ADD-UPDATE-DELETE, and adds self-repair (GRAFT).

---

## Evidence & Benchmarks

### LoCoMo-10 (1,540 questions, 10 multi-session conversations; GPT-4o-mini generation + LLM-as-judge fractional reward)

| System | Multi-hop | Temporal | Open Domain | Single Hop | Overall |
|---|---|---|---|---|---|
| A-Mem | 44.7 | 37.4 | 50.0 | 51.5 | 47.2 |
| Nemori | 49.4 | 45.0 | 36.8 | 57.4 | 52.1 |
| Mem0 | 51.2 | 55.5 | 72.9 | 67.1 | 62.1 |
| HippoRAG | 61.7 | 67.0 | 67.7 | 74.1 | 69.9 |
| RAG baseline (tuned) | 67.5 | 59.0 | 44.6 | 86.9 | 74.9 |
| **GAAMA** | **72.4** | **75.1** | 47.3 | 86.6 | **79.1** |
| **GAAMA + GRAFT** | 74.7 | 72.0 | 48.2 | 86.9 | **79.2** |

Headline gains over the strongest comparator (tuned RAG): Temporal +16.1 pp, Multi-hop +4.9 pp, Overall +4.2 pp. The paper's framing is "consistent across all categories, matching the best competitor in each, whereas every competitor degrades in at least one category."

**Ablations.**
- Hierarchy alone (no graph): 77.8% (+2.9 pp over flat RAG).
- Adding PPR (w_ppr=0.1): 77.8% → 79.0% (+1.2 pp); largest sub-gain Temporal +4.0 pp.
- On Multi-hop, PPR shows a −1.6 pp *net* score despite adding answer-relevant items 5x more often than it removes them — the regression is attributed to LLM generation variance on counting tasks, not retrieval. This is a contestable attribution worth flagging.

**GRAFT.** Net +0.1 pp overall (it *helps* multi-hop +2.5 pp and open-domain +1.0 pp but *hurts* temporal −2.7 pp). On the 47 triggered questions, reward rises 51.8% → 54.6% (+2.8 pp). So GRAFT is approximately neutral globally and currently more proof-of-concept than production lever.

### MemoryArena (vs full-context baseline)

| Task | GAAMA | Full-Context | Δ | Length trend |
|---|---|---|---|---|
| Group Travel Planner (1,869 Q) | 71.0 | 70.6 | +0.4 | grows: −0.8 early → +1.7 late |
| Web Shopping (900 Q) | 72.5 | 69.1 | +3.4 | stable across length |
| Progressive Search (1,641 Q) | 76.0 | 75.3 | +0.7 | front-loaded (+1.0 early) |

The most credible signal here is **monotonic improvement with dialogue length** on Group Travel: structured memory pays off as context grows beyond what full-context handles well — consistent with MemoryArena's own finding that LoCoMo-strong systems can be agentically weak.

### Limitations, open questions, contested claims

- **Most errors are construction errors, not retrieval errors** (the authors say so explicitly): over-generic concepts (`personal_growth`, `travel_experience`) are non-discriminative for PPR; near-duplicate concepts (singular/plural) fragment the graph and split PPR mass.
- **Small absolute graph gains.** With `w_ppr=0.1`, the graph contributes ~+1.2 pp; most of GAAMA's lift over flat RAG is the *hierarchy*, not the *traversal*. The "graph-augmented multi-hop" headline is partly carried by multi-abstraction memory, not PPR.
- **No latency/cost numbers.** The paper asserts "no LLM calls at query time → low latency" but reports no measured latency, throughput, or token-cost breakdown. GRAFT's six phases add LLM calls on its (3.1%) triggered subset.
- **Scale unproven.** Evaluated on 10 conversations / a few hundred MemoryArena entries; hierarchical partitioning and incremental PPR for "hundreds of sessions" are future work.
- **Single model family.** All results use GPT-4o-mini + text-embedding-3-small; no cross-model generalization study.
- **Judge generosity.** Fractional reward "does not penalize extra information," which favors high-recall systems and complicates direct comparison.

---

## Maturity Assessment

**Stage: research prototype, reproducible, not production-hardened.**

- **Team/artifact size.** 3 authors; MIT-licensed reference implementation with ~8 commits, ~6 stars, no releases. This is an early academic artifact, not a maintained framework.
- **Backend reality check.** Despite the "graph" branding, the implementation uses **SQLite (sqlite-vec + FTS5)**, not Neo4j or a graph DB. The "graph" is a logical structure with PPR computed in-process over a local subgraph. That is good for portability and low-dependency reproduction, but it has not been demonstrated at graph-DB scale or under concurrent write load.
- **Compute/data requirements.** Modest. Construction is dominated by LLM extraction calls (GPT-4o-mini, temperature 0) and embeddings (1536-dim). Memory budget is small (≤60 facts, ≤20 reflections, ≤80 episodes, ~1000-word context). PPR runs on a depth-2 local subgraph with ≤200 iterations — cheap per query.
- **Reproducibility.** Strong relative to typical agent-memory papers: public code, named scripts (`run_create_ltm.py`), explicit hyperparameters (α=0.6, d=2, θ=50, k=40, w_ppr=0.1), LoCoMo eval harness. Caveat: results depend on a proprietary API model (GPT-4o-mini) and judge, so exact numbers are not fully hermetic.
- **Operational gaps for production.** No latency SLO data, no incremental/streaming graph updates demonstrated, no multi-tenant or concurrency story, no canonicalization for concept dedup (the acknowledged top error source), GRAFT coverage at 3.1%.

Verdict: a promising, honest, low-cost design with a defensible core idea (concept-mediated sparse graph + edge-typed PPR + hub dampening), but the *graph* contribution is currently small and the *engineering* is early.

---

## PayPal Fraud/Risk Implications

Fraud is natively a graph problem (accounts–devices–IPs–merchants–transactions), so the *mechanism* transfers more naturally to fraud than to its original conversational setting. Concrete, specific mappings:

1. **Multi-hop investigative recall across sessions/cases.** GAAMA's depth-2 edge-typed PPR is exactly the primitive an investigative agent needs to answer "is this account linked, via a shared device fingerprint, to a merchant flagged 3 sessions ago?" Map GAAMA's schema onto fraud: *episodes* → case-review events / transaction logs; *facts* → atomic risk assertions (device X seen on account Y on date Z); *reflections* → analyst-style generalizations (this device cohort exhibits velocity-abuse pattern P); *concepts* → fraud typologies / rings / campaigns. Concept nodes become the cross-cutting traversal hubs that surface *rings* rather than individual links.

2. **Mega-hub control is directly relevant.** Fraud graphs have brutal hubs — a shared data-center IP, a popular device model, a high-volume merchant — that dominate naive PPR and produce false links. GAAMA's **hub dampening** (`min(1, θ/deg(i))`) and **edge-type-aware transition weights** are precisely the levers needed to down-weight non-discriminative hubs (shared IP) while keeping discriminative edges (same device fingerprint + same funding instrument). This is the single most transferable idea.

3. **Latency posture is favorable but unproven.** GAAMA does *no LLM calls at query time*; PPR over a depth-2 subgraph is cheap. That is compatible in spirit with sub-100ms real-time scoring — but the paper provides zero latency measurements, and fraud graphs are far larger/denser than 10 conversations. The realistic placement is **near-real-time investigative/agentic case review and offline ring detection**, not the synchronous sub-100ms authorization decision, until incremental PPR and graph-DB-scale latency are demonstrated.

4. **Long-horizon entity memory across sessions** is the headline fit. GAAMA's monotonic-gain-with-length result on MemoryArena suggests structured memory beats brute-force context as history grows — exactly the regime of an entity (account/device) observed across months. This strengthens long-horizon behavioral memory for ATO and bot detection where the signal is cross-session.

5. **Explainability / auditability.** Provenance edges (`DERIVED_FROM`, `DERIVED_FROM_FACT`) give a literal traceable chain from a flagged conclusion back to source events — valuable for regulatory review and SAR narratives. An investigator (or auditor) can follow the PPR path: flagged merchant → concept (ring) → fact (shared device) → episode (the originating event). This is a meaningful advantage over opaque embedding similarity.

6. **Adversarial robustness — mixed.** The graph structure can *harden* against some evasion (a fraudster changing one signal still leaves multi-hop links via shared concepts), but the acknowledged weakness — construction errors from over-generic/near-duplicate concepts — becomes an *attack surface*: adversaries could exploit concept fragmentation to avoid co-locating in the same ring concept. Concept **canonicalization** (the paper's own future work) is a prerequisite before trusting this in an adversarial setting.

7. **Cost-sensitive routing companions** (2603.23013 confidence-based escalation; 2603.15658 store routing) map cleanly to fraud's cost asymmetry: route most events to a cheap memory-augmented small model and escalate only low-confidence/high-value cases — a plausible path to lower scoring cost without accuracy loss.

**Net read for PayPal:** adopt the *pattern* (concept-mediated sparse graph + edge-typed PPR + hub dampening + provenance edges) for **agentic investigation, ring detection, and cross-session entity memory**, not the literal artifact. Treat latency/scale claims as unverified and require canonicalization before adversarial deployment.

---

## Sources

- GAAMA paper (abstract): https://arxiv.org/abs/2603.27910
- GAAMA paper (HTML v2): https://arxiv.org/html/2603.27910v2
- GAAMA paper (PDF): https://arxiv.org/pdf/2603.27910
- GAAMA on alphaXiv (overview): https://www.alphaxiv.org/overview/2603.27910v1
- GAAMA reference implementation (GitHub): https://github.com/swarna-kpaul/gaama
- Memory Augmented Routing ("Knowledge Access Beats Model Size"), arXiv:2603.23013: https://arxiv.org/html/2603.23013v1
- Cost-Sensitive Store Routing ("Did You Check the Right Pocket?"), arXiv:2603.15658: https://arxiv.org/pdf/2603.15658
- MemoryArena benchmark, arXiv:2602.16313: https://arxiv.org/abs/2602.16313
- MAGMA (related multi-graph agentic memory), arXiv:2601.03236: https://arxiv.org/html/2601.03236v1
