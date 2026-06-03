# SAECache: Semantic-Aware, Token-Type-Weighted Prefix-Cache Eviction

**Research window:** April 2026 – June 2026 | **Compiled:** 2026-06-03

## Executive Summary

SAECache (paper title: *"Not All Tokens Are Worth Caching: Learning Semantic-Aware Eviction for LLM Prefix Caches,"* arXiv:2605.18825v1, submitted 12 May 2026 by Shaoke Fang, Ziang Li, Wenfei Wu, Jiatong Ji, Qingsong Liu, and Ruizhi Pu) attacks a blind spot in LLM-serving prefix caches: the default Least-Recently-Used (LRU) eviction policy in systems like vLLM treats every cached KV block identically, ignoring that different *semantic* token types have radically different probabilities of being reused. The authors measure a reuse-rate spread of roughly **42x between token types** (system prompts reused 92.3% of the time vs. chain-of-thought tokens at 2.2%) and report up to **756x** when combining intra- and inter-conversation reuse. SAECache exploits this by routing KV blocks into a small set of semantic queues and computing a per-block retention score from an online-learned token-type weight, a queue-level hit-efficiency weight, and a queue-specific survival-probability decay — all updated continuously from eviction feedback with no offline-trained external predictor. Reported gains: **1.4x–2.7x TTFT improvement** over production baselines and **4.8–5.9 percentage-point hit-ratio gains** over the strongest baseline, while the multi-turn predictor uses ~1.1M parameters (vs. ~118M for the LPC e5-small baseline, ~94x fewer) and runs ~8.8x faster. The work is **research-grade and small-scale** (single NVIDIA A40, Qwen2.5-1.5B-Instruct, trace-driven injection), with honest reported regressions on low-multi-turn workloads. For PayPal Fraud/Risk, the most credible applicability is in agentic case-review and entity-memory systems whose prompts carry large, highly reused structured prefixes (risk policy, entity history, graph context) alongside throwaway reasoning — exactly the heterogeneity SAECache is designed to exploit.

---

## What's New in the Window

**Primary release**
- **SAECache** — *Not All Tokens Are Worth Caching: Learning Semantic-Aware Eviction for LLM Prefix Caches.* arXiv:2605.18825v1, submitted **12 May 2026**. Authors: Shaoke Fang, Ziang Li, Wenfei Wu, Jiatong Ji, Qingsong Liu, Ruizhi Pu. HTML: https://arxiv.org/html/2605.18825v1.
  - First eviction policy to make prefix-cache eviction explicitly **token-type / semantically aware** and to learn token-type reuse value **online from eviction feedback** (no external embedding model).

**Closely related contemporaneous work (same window, useful for positioning)**
- **IndexMem** — *Learned KV-Cache Eviction with Latent Memory for Long-Context LLM Inference.* arXiv:2605.25475, submitted **25 May 2026**. Combines a learnable importance indexer with a latent-memory module that compresses evicted tokens to provide "residual readouts," reporting up to +25 points under aggressive eviction on RULER / NIAH / LongBench. Distinct problem: *intra-prompt* attention-token eviction for long context, not *cross-request prefix-block* eviction.
- **RelayCaching** — arXiv:2603.13289 (one of the discovery-phase "known sources"; March 2026). *Accelerating LLM Collaboration via Decoding KV Cache Reuse.* Training-free reuse of decode-phase KV across collaborating agents. Note: the discovery brief labeled 2603.13289 as "LPC" — it is in fact RelayCaching; **LPC (Learned Prefix Caching, Yang et al. 2026) is a different, separately cited baseline** inside the SAECache paper.
- **SABlock** (arXiv:2510.22556) and **EvicPress** (arXiv:2512.14946, joint compression+eviction) and **"Learning to Evict from Key-Value Cache"** (arXiv:2602.10238) — adjacent KV-eviction work, all targeting intra-sequence attention eviction rather than cross-request prefix reuse.

**Why SAECache is the frontier item:** it is the only one in the window operating at the **prefix-cache-block** granularity (cross-request reuse for serving throughput/TTFT) while being **semantically typed** and **online-adaptive without a heavyweight learned model**.

---

## Technical Deep-Dive

### The problem with LRU / recency-only eviction
vLLM's default prefix cache uses LRU, which keys eviction purely on recency. SAECache's core empirical claim is that recency is a poor proxy for future reuse because reuse is dominated by *what kind of token* a block holds. Measured reuse rates (Table 1):

| Token type | Reuse rate |
|---|---|
| System prompt | 92.3% |
| User prompt | 30.8% |
| Model response | 27.8% |
| Tool output | 23.0% |
| Chain-of-thought (CoT) | 2.2% |

The system/CoT ratio is ~42x at the per-type level; the abstract's headline **756x** figure is the combined intra- + inter-conversation reuse spread. An LRU policy will happily evict a high-value system-prompt block because it has not been touched recently, while retaining low-value CoT blocks that were just generated and will essentially never be reused.

### Multi-queue architecture
SAECache routes each KV block into one of four queues by semantic role:
1. **Evict-First Queue** — decode blocks and low-reuse untemplated prefill blocks; drained first.
2. **Structural Queue** — templated single-turn prefill blocks (shared prompt structure across many requests).
3. **Chat Queue** — multi-turn conversational blocks with session-local temporal reuse.
4. **Agentic Queue** — multi-turn tool-use / agent blocks, which have different timing characteristics than chat.

Token types tracked for weighting: system prompts, user queries, tool outputs, model responses, and CoT reasoning.

### Retention-priority score
Each block `b` gets a global retention priority:

```
P(b) = α_q · w_τ(b) · p_q(b) / Δt_b
```

where
- **α_q** — queue-level hit-efficiency weight (how productive this queue's retained blocks have been),
- **w_τ(b)** — token-type weight for block `b`,
- **p_q(b)** — queue-specific local survival probability,
- **Δt_b** — elapsed time since last access (the recency term LRU uses, here demoted to one factor among several).

The survival probability is parameterized differently per queue:
- **Multi-turn (chat / agentic):** `p_q(b) = 1 − F_LN(Δt_b; μ_q, σ_q)` — one minus the log-normal CDF of inter-access gaps, with learned `μ_q, σ_q`. Log-normal captures the heavy-tailed "burst then long silence" access pattern of conversational sessions.
- **Structural:** `p_q(b) = 1 − (o_b / o_max)^γ` — a **position-decay** term where `o_b` is block position/order and `γ` is learned online. Earlier (shared-prefix) positions decay slower, matching the intuition that the head of a templated prompt is reused across many requests.

### Online learning of token-type weights
Token-type weights are updated by EWMA toward a feedback target:

```
w_target = 1.0 + r_miss · 5.0 + r_reuse · 2.0
w_new    = (1 − η) · w_old + η · w_target
```

- **r_miss** — miss-after-eviction rate: direct feedback signal that a block of this type was evicted and then immediately requested again (an eviction mistake). Weighted heavily (×5).
- **r_reuse** — overall cache hit rate for the token type (×2).
- Statistics are kept in a sliding window with decay factor 0.99; updates fire every `K` evictions at constant overhead.

Crucially, the learning signal is the cache's own miss/hit telemetry — **no external embedding model, no offline labels**. This is the key architectural difference from LPC (Learned Prefix Caching), which uses an e5-small encoder (~118M params) to embed/score prefixes. SAECache's multi-turn session predictor is a three-layer MLP (256→64 hidden), **~1.1M parameters**, ~44 MB, doing ~1,137 predictions/sec vs. LPC's 129/sec — hence the ~8.8x throughput and ~94x parameter-reduction claims.

### Fully adaptive online schema
All meta-parameters — log-normal `(μ_q, σ_q)`, position-decay `γ`, queue hit-efficiency `α_q`, token-type weights `w_τ`, and timing — are updated online with no manual tuning. The paper shows that **fixed-parameter** variants degrade by up to **2.7x** under workload mismatch, which is the central argument for adaptivity over a tuned-once heuristic.

### What changed vs. prior art
- **vs. LRU (vLLM default):** recency becomes one factor (`1/Δt_b`) rather than the whole policy; eviction is semantically and queue-aware.
- **vs. LPC (Yang et al. 2026):** replaces a 118M-param learned prefix encoder with online-learned per-type statistics — far cheaper and serving-loop-native, integrated as a drop-in vLLM `Cache Evictor`.
- **vs. IndexMem / SABlock / EvicPress:** those evict *within* a sequence's attention KV for long-context quality; SAECache evicts *prefix blocks across requests* for serving throughput/TTFT. Different granularity and objective.

---

## Evidence & Benchmarks

**Setup:** NVIDIA A40 GPU; Qwen2.5-1.5B-Instruct as the primary serving model; vLLM v0.8.5 with SAECache as a drop-in Cache Evictor. Trace-driven request injection at intervals of 0.02–0.08s to *induce cache pressure* (the authors note low concurrency rarely fills the KV cache, so benefits only appear under load). LLAMA-8B used for long-context comparison; Qwen3-32B used in the LPC comparison.

**Workloads:** Real traces — ShareGPT (74% multi-turn), LMSys (33% multi-turn), Chatbot-Arena (12% multi-turn) — plus synthetic mixes: tool_use, multi_turn_dominant, balanced, single_turn_dominant.

**Headline results:**
- **TTFT:** 1.4x–2.7x improvement over production-style baselines.
- **Hit ratio:** +4.8 to +5.9 percentage points over the strongest baseline across 12 dataset-interval configurations.
- **Predictor efficiency:** ~1.1M params / ~44 MB / 1,137 pred/s vs. LPC e5-small 118M / ~472 MB / 129 pred/s (≈8.8x faster, ≈94x fewer params).

**Ablations (Appendix D), contribution to improvement over a Fixed-Param baseline:**
- Queue-weight learning: **+39%**
- Token-type weight learning: **+23%**
- Log-normal timing learning: **+14%**
- Position-decay learning: **+12%**
- Combined: **+88%**

The ablation ordering is itself informative: the largest single contributor is *queue-weight* learning (the routing/queue structure), with token-type weighting second — i.e., much of the value is structural, not solely from the per-type reuse table.

**Limitations / contested points (stated by the authors):**
- **Regression on low-multi-turn workloads:** Chatbot-Arena (12% multi-turn) shows **12–34% TTFT degradation** — the predictor/queue bookkeeping overhead exceeds savings when there is little cross-turn reuse to exploit. SAECache helps where reuse is structured and high; it can hurt where it is not.
- **Heavy-tail underestimation:** EWMA-style updates underestimate σ in heavy-tailed inter-access distributions (Appendix B), which can mis-rank long-dormant-but-valuable blocks.
- **Single-turn dominance:** predictor overhead reduces or eliminates benefit in single-turn-dominated traffic.

**Open questions / things to verify independently:**
- All numbers come from a **single v1 preprint** on a **1.5B model / single A40**; no third-party reproduction yet found in the window. Treat magnitudes as indicative, not settled.
- The 756x vs. 42x framing is easy to over-read: 42x is the clean per-token-type ratio; 756x bundles intra+inter-conversation effects and should be cited carefully.
- No reported results on truly large models under multi-GPU/cluster serving (authors flag cluster-level as future work).

---

## Maturity Assessment

**Stage: research / single-lab preprint (v1).** Strengths for adoption are real: it is implemented as a **drop-in vLLM v0.8.5 Cache Evictor** (low integration friction), the predictor is tiny (~44 MB, runs on CPU-class compute alongside serving), and it requires **no offline training data or external model** — it learns from the serving loop's own telemetry. Compute/data requirements are therefore modest; the barrier is engineering integration and validation, not training cost.

**Reproducibility:** The paper gives explicit formulas, queue definitions, hyperparameters (decay 0.99, target weights 5.0/2.0, MLP 256→64), and a concrete benchmarking harness, which is encouraging. However, evaluation is confined to one small model on one GPU with trace-driven injection, and no independent replication is yet visible. The honest reporting of negative results (Chatbot-Arena regression, heavy-tail σ bias) raises credibility but the scale is small.

**Net:** Promising, well-specified, cheap to try, but **not yet production-validated at scale.** A realistic path is a shadow/canary integration in a vLLM-based serving stack with workloads that genuinely exhibit structured prefix reuse, measuring TTFT and hit-ratio before trusting the published multipliers.

---

## PayPal Fraud/Risk Implications

The applicability hinges on one precondition: **does the serving workload carry large, highly reused, semantically structured prefixes?** Several PayPal Fraud/Risk surfaces plausibly do.

1. **Agentic case-review / investigation workflows (best fit).** An investigative agent prompt typically concatenates: a large, near-static **risk-policy / SOP system prompt** (very high reuse across cases), **per-entity history and graph context** (reused across the turns of a single investigation), **tool outputs** (transaction pulls, device/IP lookups — moderate reuse), and **chain-of-thought reasoning** (essentially single-use). This is precisely SAECache's target distribution. Keeping policy and entity-context KV resident while aggressively evicting CoT could cut TTFT on each agent step and reduce prefill recompute — directly lowering investigation latency and GPU cost at PayPal volume. The paper's Agentic Queue and tool-output token type map cleanly onto this.

2. **Latency for interactive/near-real-time scoring.** SAECache targets TTFT, not per-token decode throughput, so it helps where a long structured prompt must be prefilled before any output. For sub-100ms *transaction* scoring, LLM-in-the-loop is usually too slow regardless; SAECache is more relevant to the **second-tier, LLM-driven** layers (narrative risk summaries, alert triage, analyst copilots) than to the hot real-time path. Be skeptical of claims that prefix caching meaningfully helps the sub-100ms scorer.

3. **Long-horizon entity memory.** Where a system maintains an evolving per-entity prefix (behavioral summary, prior-case notes) that is reused across sessions, the token-type weighting plus log-normal timing model is a natural fit for keeping that high-value KV resident across the heavy-tailed gaps between an entity's appearances — though the paper's own Appendix-B caveat about underestimating σ in heavy tails is directly relevant to "entity reappears after a long dormancy."

4. **Graph / sequence signals.** If graph context (account–device–IP–merchant neighborhoods) or behavioral sequences are serialized into the prompt as a shared, slowly-changing block, treating them as a high-reuse token type would keep them cache-resident. SAECache does not model graph structure itself — it only changes *what stays in cache* — so the benefit is latency/cost, not detection accuracy.

5. **Adversarial robustness — a caution, not a benefit.** The miss-after-eviction learning signal (`r_miss`) is workload-driven and therefore **manipulable in principle**: an adversary who can shape request patterns might bias token-type weights or pollute queues to degrade cache efficiency (a cache-thrashing / timing side-channel concern). Any deployment in an adversarial fraud setting should bound weight excursions, monitor for anomalous eviction churn, and treat the online learner as an attack surface.

6. **Explainability / auditability.** SAECache is a serving-infrastructure optimization; it does **not** change model outputs or scores, so it is largely orthogonal to regulatory explainability. The one audit-relevant note: because eviction decisions are now learned and dynamic, you may want logging of queue weights and token-type weights over time for operational reproducibility (so a given latency profile can be explained), but this is ops hygiene, not model-decision auditability.

**Honest bottom line for PayPal:** the credible, near-term win is **lower TTFT and prefill cost for agentic/investigative and LLM-assistant workloads with large shared prefixes**, contingent on those workloads actually exhibiting high structured reuse. It does not improve detection accuracy, does not help the sub-100ms scorer, introduces a manipulable online learner that warrants adversarial review, and is backed by a single small-scale preprint — so pilot-and-measure before relying on the published 1.4x–2.7x numbers.

---

## Sources

- SAECache (primary): *Not All Tokens Are Worth Caching: Learning Semantic-Aware Eviction for LLM Prefix Caches*, arXiv:2605.18825v1 — https://arxiv.org/abs/2605.18825 ; https://arxiv.org/html/2605.18825v1
- IndexMem: *Learned KV-Cache Eviction with Latent Memory for Long-Context LLM Inference*, arXiv:2605.25475 — https://arxiv.org/abs/2605.25475
- RelayCaching: *Accelerating LLM Collaboration via Decoding KV Cache Reuse*, arXiv:2603.13289 — https://arxiv.org/abs/2603.13289
- SABlock: *Semantic-Aware KV Cache Eviction with Adaptive Compression Block Size*, arXiv:2510.22556 — https://arxiv.org/html/2510.22556v1
- EvicPress: *Joint KV-Cache Compression and Eviction for Efficient LLM Serving*, arXiv:2512.14946 — https://arxiv.org/abs/2512.14946
- *Learning to Evict from Key-Value Cache*, arXiv:2602.10238 — https://arxiv.org/pdf/2602.10238
- vLLM Automatic Prefix Caching (design docs) — https://docs.vllm.ai/en/v0.8.5/design/v1/prefix_caching.html ; https://docs.vllm.ai/en/stable/design/prefix_caching/
- *vLLM Prefix Caching vs. LMCache: Benchmarking KV Reuse Tradeoffs* (Apr 2026) — https://levelup.gitconnected.com/vllm-prefix-caching-vs-lmcache-benchmarking-kv-reuse-tradeoffs-944fbaf98b56
- Ceph.io: *KV Caching with vLLM, LMCache, and Ceph* — https://ceph.io/en/news/blog/2025/vllm-kv-caching/
