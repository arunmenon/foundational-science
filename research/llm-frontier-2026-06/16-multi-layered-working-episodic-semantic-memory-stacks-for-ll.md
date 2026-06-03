# Multi-Layered Working/Episodic/Semantic Memory Stacks for LLM Agents

**Research window:** April 2026 – June 2026 (compiled 2026-06-03)
**Domain lens:** PayPal Fraud & Risk (real-time scoring, entity memory, agentic investigation, auditability)

## Executive Summary

In the April–June 2026 window, a coherent design pattern crystallized across multiple independent groups: agent memory is no longer treated as a single retrieval-augmented store but as an explicit *stack* of layers — bounded **working memory**, accumulating **episodic** session summaries, and structured **semantic / entity-level** memory — coordinated by adaptive retrieval gating and stabilized by retention regularization or principled forgetting. The most concrete experimental anchor is *Multi-Layered Memory Architectures for LLM Agents* (arXiv:2603.29194, Tiwari & Fofadiya), which reports 0.618 overall / 0.594 multi-hop F1, 56.9% six-period retention, a 5.1% false-memory rate, and 58.4% context usage on LOCOMO/LOCCO. Production-oriented systems — **MemMachine** (arXiv:2604.04853) and **Memori** (arXiv:2603.19935) — operationalize the same working/episodic/profile-semantic split with graph + vector + SQL backends, while a wave of surveys (externalization review arXiv:2604.08224; memory-security survey arXiv:2604.16548; mechanisms survey arXiv:2603.07670) and forgetting papers (arXiv:2604.02280, FadeMem arXiv:2601.18642) converge on the same taxonomy. The honest caveat: the headline numbers come largely from a single author pair on lexical-overlap metrics that the field itself (arXiv:2602.19320) is actively criticizing, and no published system yet covers full memory *governance* (write-gating, verifiable deletion) — precisely the properties a regulated fraud deployment would require.

## What's New in the Window

The window features a tight cluster of primary work plus framing surveys. Dates and IDs below are as published on arXiv.

**Core architecture / experimental papers (the frontier claim):**
- **Multi-Layered Memory Architectures for LLM Agents: An Experimental Evaluation of Long-Term Context Retention** — arXiv:[2603.29194](https://arxiv.org/abs/2603.29194), Sunil Tiwari & Payal Fofadiya (late March 2026, central to the window's narrative). Formalizes the working/episodic/semantic stack with adaptive gating + retention regularization. This is the source of the 0.618 F1 / 56.9% retention / 5.1% FMR headline metrics.
- **Novel Memory Forgetting Techniques for Autonomous AI Agents: Balancing Relevance and Efficiency** — arXiv:[2604.02280](https://arxiv.org/abs/2604.02280), Payal Fofadiya & Sunil Tiwari (submitted 2026-04-02). The companion "forgetting" paper from the same authors: an adaptive budgeted-forgetting framework using relevance-guided scoring (recency + frequency + semantic alignment). Reports the LOCOMO/LOCCO degradation (0.455 → 0.05 across stages) and MultiWOZ 78.2% acc / 6.8% FMR figures that the multi-layer paper improves upon.

**Production / systems papers:**
- **MemMachine: A Ground-Truth-Preserving Memory System for Personalized AI Agents** — arXiv:[2604.04853](https://arxiv.org/abs/2604.04853) (April 2026). Open-source ([github.com/MemMachine/MemMachine](https://github.com/MemMachine/MemMachine)) three-tier memory (short-term / long-term episodic / profile-semantic) over pgvector + Neo4j + SQLite, with a REST v2 API, Python SDK, and MCP server. Featured at NODES AI 2026 (Neo4j).
- **Memori: A Persistent Memory Layer for Efficient, Context-Aware LLM Agents** — arXiv:[2603.19935](https://arxiv.org/abs/2603.19935) (March 2026, productized in the window). Persistent layered store that abstracts interactions into retrievable structures rather than replaying raw logs.

**Surveys / framing (the "convergence" evidence):**
- **Memory Externalization in LLM Agents** (review) — arXiv:[2604.08224](https://arxiv.org/html/2604.08224v1). Frames externalization as the unifying principle; proposes a four-dimensional taxonomy: working context, episodic experience, semantic knowledge, personalized memory.
- **A Survey on the Security of Long-Term Memory in LLM Agents: Toward Mnemonic Sovereignty** — arXiv:[2604.16548](https://arxiv.org/html/2604.16548v1), Lin, Li & Chen (MemTensor, 2026-04-17). Treats writable memory as its own attack surface; six-phase lifecycle threat model.
- **Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers** — arXiv:[2603.07670](https://arxiv.org/abs/2603.07670) (2026-03-08). Formalizes a write–manage–read loop and a 3-D taxonomy (temporal scope × representational substrate × control policy).
- **Anatomy of Agentic Memory: Taxonomy and Empirical Analysis of Evaluation and System Limitations** — arXiv:[2602.19320](https://arxiv.org/html/2602.19320v1). The skeptic's paper: argues benchmarks are saturating and lexical metrics mislead.

**Adjacent mechanism papers (just before / spanning the window):**
- **SYNAPSE: Empowering LLM Agents with Episodic-Semantic Memory via Spreading Activation** — arXiv:[2601.02744](https://arxiv.org/abs/2601.02744) (Univ. of Georgia). Models memory as a dynamic graph with spreading activation, lateral inhibition, and temporal decay; triple-hybrid retrieval (geometric embeddings + activation-based graph traversal).
- **FadeMem: Biologically-Inspired Forgetting for Efficient Agent Memory** — arXiv:[2601.18642](https://arxiv.org/abs/2601.18642). Differential exponential decay over a dual-layer hierarchy; claims to outperform Mem0 with 45% less storage.

## Technical Deep-Dive

### The standardized three-layer stack

The window's defining contribution is that several groups now describe the *same* layering with compatible formalism. Using the notation from arXiv:2603.29194:

- **Working memory** — bounded token-level encoding of the current session, `φ_w(S_t)` with fixed window size *k*. Preserves recent utterances without distant interference. Maps to MemMachine's "short-term memory" and the externalization review's "working context."
- **Episodic memory** — a recursively updated session-summary state: `M_t^(e) = α·M_{t-1}^(e) + (1-α)·ψ(S_t)`, where `ψ` produces compact session summaries and `α ∈ [0,1]` controls cross-session retention decay. This is an exponential-moving-average over summaries — cheap, bounded, and the core of "accumulating episodic summaries."
- **Semantic memory** — derived from episodic memory via a transformation `A(·)` that maps summaries into **structured entity-event graphs**, deduplicating while preserving stable attributes. This is the layer directly relevant to per-entity risk memory.

### Adaptive retrieval gating

Rather than always concatenating all layers, retrieval is a softmax-weighted mixture (Eq. 7 in 2603.29194):

```
R_t = Σ_i γ_i · M_t^(i),   γ_i = softmax_β( sim(x_t, M_t^(i)) )
```

`sim(·)` is semantic relevance, `β` is a temperature controlling how sharply the gate concentrates on one layer. The fused representation `z_t = f(x_t, R_t)` integrates the query with retrieved memory via cross-attention. The practical effect is the reported drop in context usage (58.4% vs 64.98% baseline): the gate avoids stuffing all three layers into the prompt every turn.

### Retention regularization (the anti-drift term)

The mechanism that distinguishes this line from generic RAG is an explicit penalty on semantic-memory drift (Eq. 9):

```
L_ret = Σ_t || E(M_t^(s)) − E(M_{t-1}^(s)) ||²₂
L     = L_gen + λ·L_ret
```

`E(·)` projects semantic memory to entity embeddings; `λ` weights the stability constraint against the generation objective. Conceptually this is a temporal-consistency regularizer on the entity layer: it discourages an entity's stored representation from lurching between sessions, which the ablations tie directly to the lower false-memory rate. Algorithm 1 adds capacity-projection operators `Π_C` to enforce bounded memory size and an entropy bound during fusion.

### Alternative mechanisms exploring the same space

- **SYNAPSE (2601.02744)** replaces precomputed links with *spreading activation* over a memory graph: relevance emerges dynamically from activation propagation, with lateral inhibition and temporal decay highlighting relevant sub-graphs and suppressing interference ("Contextual Tunneling"). Borrowed directly from Collins & Loftus (1975).
- **MemMachine (2604.04853)** takes a *ground-truth-preserving* stance: instead of per-message LLM extraction (the Mem0 pattern, which can accumulate "factual drift"), it stores **raw episodes indexed at sentence granularity** (four stages: sentence extraction → metadata augmentation → relational mapping → embedding). Retrieval is staged (STM → long-term vector → "episode-cluster" contextualization that expands nucleus episodes with neighbors). It reserves LLM calls for summarization/abstraction, claiming ~80% fewer input tokens than Mem0. A "Retrieval Agent" tackles the multi-hop "late-binding problem" via ChainOfQuery (iterative, ≤3 iters) and SplitQuery (parallel decomposition).
- **FadeMem (2601.18642)** and the forgetting paper (2604.02280) replace "store-everything" with adaptive decay modulated by semantic relevance, access frequency, and temporal patterns — explicitly the inverse operation of retention regularization (controlled *forgetting* rather than controlled *stability*).

**What changed vs prior art (MemGPT, Reflexion, Mem0, MemoryOS, GraphRAG):** earlier systems, per the externalization review (2604.08224) and mechanisms survey (2603.07670), either (a) improved efficiency without stabilizing retention, or (b) improved recall without constraining drift. The window's contribution is *jointly* optimizing bounded context, cross-session retention, and false-memory suppression, with measured metrics on multi-session benchmarks — plus a semantic/entity layer treated as a first-class, regularized object rather than an emergent byproduct of retrieval.

## Evidence & Benchmarks

### Headline results (arXiv:2603.29194, LOCOMO / LOCCO)

LOCOMO setup: ~588 avg turns, ~27 sessions/conversation, ~16.6k tokens/dialogue. LOCCO: 3,080 dialogues, 100 users, retention across 6 temporal periods.

| Metric | MLMF (full) | Baseline |
|---|---|---|
| Success rate | 46.85% | 42.00% |
| Overall F1 | 0.618 | 0.583 |
| Multi-hop F1 | 0.594 | 0.550 |
| BLEU-1 | 0.632 | 0.599 |
| Context usage | 58.40% | 64.98% |
| 6-period retention | 56.90% | 48.25% |
| False-memory rate | 5.1% | 6.8% |
| Throughput | 10.4× | 9× |

### Ablations (which layer matters)

| Variant removed | F1 | 6-period retention | FMR |
|---|---|---|---|
| No semantic layer | 0.591 | 50.84% | 6.4% |
| No episodic consolidation | 0.602 | 52.13% | 6.1% |
| No retention loss | 0.608 | 53.27% | 6.9% |
| No adaptive gating | 0.604 | 52.98% | 6.5% |
| **Full MLMF** | **0.618** | **56.90%** | **5.1%** |

The two load-bearing components are clear: removing the **semantic layer** causes the largest retention collapse, and removing **retention regularization** drives the false-memory rate highest (6.9%). This is the strongest internal evidence that the entity-semantic layer plus its stability term — not just "more layers" — is what produces durable, low-hallucination memory.

### Production-system numbers (different benchmarks, not directly comparable)

MemMachine (2604.04853) reports LoCoMo 91.69% (gpt-4.1-mini overall), LongMemEval-S 93.0%, HotpotQA-hard 93.2%, 2WikiMultiHop 92.6%, and a LoCoMo 0.8747 (gpt-4o-mini) vs Mem0 0.6688 gap attributed to sentence-level indexing and ground-truth preservation. Its LongMemEval ablation gains (retrieval depth +4.2%, context formatting +2.0%, search-prompt +1.8%, query-bias correction +1.4%, sentence chunking +0.8%) are reported as *independent* dimensions — interaction effects unstudied.

### Limitations, open questions, and contested claims (be skeptical here)

- **Single-source headline metrics + metric validity.** The 0.618/56.9%/5.1% numbers and the companion forgetting framework both come from the same two authors (Tiwari & Fofadiya). Meanwhile *Anatomy of Agentic Memory* (2602.19320) argues lexical/F1 metrics "fail to capture the strengths of abstractive memory systems" (penalizing paraphrase, ignoring logical coherence) and advocates LLM-based semantic evaluation. So the F1-based gains should be read cautiously.
- **Benchmark saturation.** 2602.19320 proposes a "Context Saturation Gap" — comparing memory-augmented vs full-context baselines — and warns that growing context windows make external memory unnecessary on many current benchmarks (meaningful only when Δ >> 0). The mem0.ai and ByteRover commentary similarly notes LoCoMo scores are now clustered in the low-90s, suggesting headroom is shrinking.
- **Cross-system comparability.** MemMachine itself flags that its comparisons mix re-run and published numbers, are sensitive to eval-model/prompt versions (provider updates shift scores), and that it trails Memobase on the LoCoMo *temporal* category (0.7352 vs 0.8505) — temporal reasoning remains weak.
- **Silent failures with weaker backbones.** 2602.19320 reports structured-memory architectures suffer format errors during memory updates with smaller models (e.g., Qwen-2.5-3B) that "corrupt long-term state despite short-term fluency" — a reliability concern for cost-constrained deployment.
- **The "Agency Tax."** Latency/maintenance overhead is real: MemoryOS is cited at 32-second retrieval latencies — disqualifying for interactive (let alone real-time) use without redesign.
- **No empirical false-memory data in the surveys.** The externalization review (2604.08224) acknowledges contamination risk conceptually ("poisoned or conflicting memories embed incorrect premises") but provides no measured FMR; retention policies remain "largely heuristic-driven."

## Maturity Assessment

**Research-only vs production-ready — a split field:**
- The *architecture* papers (2603.29194, 2604.02280, SYNAPSE) are **research-stage**: single-group results, limited reproducibility detail in the provided text (no released code/seeds surfaced), lexical-metric evaluation under active criticism.
- The *systems* (MemMachine, Memori) are **early-production**: MemMachine is open-source with REST/SDK/MCP interfaces and standard backends (PostgreSQL+pgvector, Neo4j, SQLite), which is the most deployable artifact in the window. Maturity is "usable framework," not "battle-tested at scale."

**Compute / data requirements:** The core mechanisms are cheap relative to the LLM itself — episodic EMA summaries, a softmax gate, an L2 retention penalty, and capacity projections. The dominant cost is the LLM summarization/abstraction calls; MemMachine's whole thesis is minimizing these (~80% token reduction vs per-message extraction). No specialized training is required beyond the optional retention-loss fine-tuning. Storage scales with raw-episode retention (MemMachine) — the tradeoff FadeMem's 45%-less-storage forgetting directly targets.

**Reproducibility:** Mixed-to-weak. Benchmark sensitivity to eval-model/prompt versions, mixing of re-run vs published baselines, and the absence of standardized memory-specific metrics (per 2603.07670 and 2602.19320) all make cross-paper claims hard to verify. The systems papers are more reproducible by virtue of released code.

**Security/governance maturity (critical for regulated use):** Immature. The mnemonic-sovereignty survey (2604.16548) concludes **no published memory architecture covers all governance primitives** — write-gate validation and post-deletion verification are *unimplemented across all examined systems*, and the Store and Forget/Rollback lifecycle phases are each ~5% of the literature. For a regulated environment this is the single biggest gap.

## PayPal Fraud/Risk Implications

The layered stack maps unusually cleanly onto fraud/risk needs, but each benefit comes with a latency or governance caveat.

**1. Persistent per-entity risk memory (the strongest fit).** The semantic/entity layer (`A(·)` → entity-event graph) is a natural home for cross-session, per-entity risk state: an account, device, IP, or merchant carries a structured, queryable record across investigations. Concretely, an episodic+semantic entry can encode "account X triggered a chargeback dispute via device Y in session Z," surviving across sessions as a *citable* fact rather than a buried embedding. The entity-centric memory category in the agentic-memory taxonomy (2602.19320) — attribute-value records keyed on explicit entities — is exactly the substrate PayPal already thinks in (accounts/devices/IPs/merchants graph).

**2. Explainability and auditability for regulators.** The 5.1% false-memory rate (2603.29194) is an *auditable, reportable* metric — a regulator-facing number for "how often the system fabricates entity history." The retention-regularization term provides a defensible mechanism story ("entity representations are constrained against drift"). MemMachine's ground-truth preservation (raw sentence-level episodes) gives investigators a verbatim provenance trail, avoiding the "factual drift through accumulated extraction errors" that pure-extraction systems risk — important when a decline decision must be explained.

**3. Agentic case review.** SYNAPSE's spreading activation and MemMachine's ChainOfQuery/SplitQuery directly support multi-hop investigative reasoning — e.g., traversing from a flagged transaction to the device to other accounts on that device to a merchant — which is the "fraud ring" pattern external commentary (Taktile) cites LLMs as good at surfacing. The episodic layer of "prior runs, decision points, tool calls, failures" (externalization review) is effectively a case-history log for investigator agents.

**4. Latency — the hard constraint.** Real-time scoring needs sub-100ms; the memory-stack work targets multi-turn conversational latency, and cited systems show 32s outliers (MemoryOS). Realistic deployment: use the memory stack for the **investigative/case-review and offline entity-profiling** path, **not** the inline scoring path. The bounded working layer + adaptive gating (lower context usage) could, however, reduce per-call cost for near-real-time agentic triage.

**5. Adversarial robustness — a double-edged sword.** Persistent writable memory is a *new attack surface*. The mnemonic-sovereignty survey (2604.16548) and MemoryGraft (poisoned-experience retrieval, arXiv:2512.16962) show fraudsters could deliberately poison entity memory — e.g., grooming an account's history so future sessions treat it as low-risk, with poisoned entries propagating across hundreds of sessions. For PayPal this means: (a) write-gate validation and provenance tagging before any entity-memory write, (b) trust-aware retrieval, and (c) verifiable deletion are *prerequisites*, not nice-to-haves — and the survey says none of these are fully implemented yet. Retention regularization may even *help adversaries* by stabilizing a poisoned representation, so it must be paired with anomaly detection on memory writes.

**6. Drift handling.** Adaptive forgetting (2604.02280, FadeMem) aligns with evolving fraud patterns: stale behavioral memories should decay while confirmed-fraud entity facts persist (FadeMem's slow-decay long-term layer for high-importance facts). This gives a principled knob for "how long does a chargeback stay on an entity's risk memory."

**Net read:** The layered memory stack is a credible architecture for PayPal's **entity-memory and agentic-investigation** layer, with auditability advantages. It is *not* ready for inline sub-100ms scoring, and its security/governance story is the gating risk for any regulated deployment — adopt the architecture, but require write-gating, provenance, trust-aware retrieval, and verifiable deletion that the current literature admits are missing.

## Sources

- Multi-Layered Memory Architectures for LLM Agents — https://arxiv.org/abs/2603.29194 ; HTML: https://arxiv.org/html/2603.29194 ; PDF: https://arxiv.org/pdf/2603.29194
- Novel Memory Forgetting Techniques for Autonomous AI Agents — https://arxiv.org/abs/2604.02280 ; PDF: https://arxiv.org/pdf/2604.02280
- MemMachine: A Ground-Truth-Preserving Memory System — https://arxiv.org/abs/2604.04853 ; HTML: https://arxiv.org/html/2604.04853v1 ; code: https://github.com/MemMachine/MemMachine ; NODES AI 2026: https://neo4j.com/videos/nodes-ai-2026-memmachine-agents-that-learn-memory-that-lasts/
- Memori: A Persistent Memory Layer — https://arxiv.org/abs/2603.19935 ; PDF: https://arxiv.org/pdf/2603.19935
- Memory Externalization in LLM Agents (review) — https://arxiv.org/html/2604.08224v1
- A Survey on the Security of Long-Term Memory in LLM Agents: Toward Mnemonic Sovereignty — https://arxiv.org/html/2604.16548v1
- Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers — https://arxiv.org/abs/2603.07670 ; HTML: https://arxiv.org/html/2603.07670v1
- Anatomy of Agentic Memory: Taxonomy and Empirical Analysis — https://arxiv.org/html/2602.19320v1
- SYNAPSE: Episodic-Semantic Memory via Spreading Activation — https://arxiv.org/abs/2601.02744 ; HTML: https://arxiv.org/html/2601.02744v3
- FadeMem: Biologically-Inspired Forgetting for Efficient Agent Memory — https://arxiv.org/abs/2601.18642
- MemoryGraft: Persistent Compromise via Poisoned Experience Retrieval — https://arxiv.org/pdf/2512.16962
- LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory — https://arxiv.org/pdf/2410.10813
- State of AI Agent Memory 2026 (Mem0) — https://mem0.ai/blog/state-of-ai-agent-memory-2026 ; AI Memory Benchmarks 2026 — https://mem0.ai/blog/ai-memory-benchmarks-in-2026
- ByteRover 2.0 LoCoMo leaderboard — https://www.byterover.dev/blog/benchmark-ai-agent-memory
- Taktile: LLMs as investigative partners in fintech fraud detection — https://taktile.com/articles/llms-investigative-partners-fraud-detection
