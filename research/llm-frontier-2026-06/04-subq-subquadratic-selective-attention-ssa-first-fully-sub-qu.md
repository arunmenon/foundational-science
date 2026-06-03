# SubQ / Subquadratic Selective Attention (SSA): The First "Fully Sub-Quadratic" Frontier LLM

## Executive Summary

On May 5, 2026, a Miami-based startup called **Subquadratic** (founders Justin Dangel, CEO, and Alexander Whedon, CTO) launched **SubQ**, marketed as the first commercial frontier-class LLM built on a "fully subquadratic" attention mechanism it calls **Subquadratic Selective Attention / Sparse Attention (SSA)**. The central technical claim is that SSA performs *content-dependent* token selection in which **the selection (indexer) path itself is non-quadratic**, directly addressing the failure mode of prior sparse-attention systems such as DeepSeek's Sparse Attention (DSA), whose "lightning indexer" still scored all O(n²) query-key pairs before sparsifying. Subquadratic reports a **native 12-million-token context window**, **~52x faster attention than FlashAttention-2 at 1M tokens** (7.2x at 128K, ~23x at 512K), roughly **1/62.5 the attention FLOPs at 1M** and ~1,000x reduction at 12M, plus competitive quality on RULER, MRCR, and SWE-Bench. **None of this is independently reproduced.** As of early June 2026 there is no technical report, no released weights, benchmarks were single-run, the base model is widely believed to be a sparse-attention fine-tune of an open model (Kimi or DeepSeek V3.2), and named researchers have called the numbers "cherry-picked" and "suspiciously perfect." The architecture is genuinely relevant to PayPal Fraud/Risk because a truly linear-scaling, content-routed indexer would enable persistent, ever-growing per-entity event logs as live model context, but adoption should be gated strictly on internal benchmarking of the vendor claims.

---

## What's New in the Window (April–June 2026)

### The launch (May 5, 2026)
- **SubQ** announced by **Subquadratic** with a **$29M seed round** (SiliconANGLE, May 5, 2026). Investors: Javier Villamizar (ex-SoftBank Vision Fund), Justin Mateen (Tinder co-founder / JAM Fund), Grant Gittlin (Lasagna), Jaclyn Rice Nelson (Coalition Operators), plus angels who were early backers of Anthropic, OpenAI, Stripe, and Brex.
- **Team:** CEO Justin Dangel (five-time founder); CTO Alexander Whedon (ex-Meta engineer, former Head of Generative AI at TribeAI). Research team described as ~11 PhDs from Meta, Google, Oxford, Cambridge, ByteDance, Adobe, and Microsoft. Company reportedly developed the technology over ~5 years.
- **Products (all private beta / waitlist as of launch):**
  - **SubQ API** — OpenAI-compatible endpoints, streaming, tool/function calling, up to 12M-token context.
  - **SubQ Code** — CLI coding agent that loads an entire codebase into one context window.
  - **SubQ Search** — long-context deep-research tool (land-and-expand, initially free).
- **Traction:** ~12M views on X and >30,000 waitlist signups in the first 24 hours (Refresh Miami).
- **No open weights, no arXiv paper.** A technical report is described as "forthcoming." This is the single most important caveat for the entire body of claims.

### Primary and secondary coverage in-window
- Official launch post: **subq.ai/introducing-subq** (vendor primary source).
- Trade press: SiliconANGLE (5/5), The New Stack (5/5, "The context window has been shattered"), eWeek, VentureBeat ("researchers demand independent proof"), Refresh Miami ("now comes the hard part").
- Analytical / skeptical: the **cozypet "subq-field-map"** (a strong third-party complexity analysis framing the "attention trilemma"), Firethering ("If It's Real"), DataCamp, explainx.ai, felloai.

### Relevant prior art that SSA explicitly positions against (context, not in-window)
- **Native Sparse Attention (NSA)**, DeepSeek-AI, arXiv:2502.11089 (Feb 2025) — hardware-aligned, natively trainable sparse attention; coarse block compression + fine-grained selection.
- **DeepSeek Sparse Attention (DSA)** in DeepSeek-V3.2 / V3.2-Exp (Sept–Dec 2025; arXiv:2512.02556) — "Lightning Indexer" (FP8 scorer) + fine-grained token selection, reducing core attention from O(L²) to O(Lk) but with the indexer itself still touching every pair.
- Long line of subquadratic sequence models: **Mamba / SSMs, RWKV, Hyena, S4** — repeatedly showed linear scaling but historically hit a quality wall at frontier scale.

---

## Technical Deep-Dive

### The problem SSA claims to solve: the "attention trilemma"
The clearest technical framing comes from the third-party "subq-field-map." Efficient attention must trade off three properties, and prior approaches achieve at most two:

1. **Subquadratic compute** — cost scaling better than O(n²).
2. **Content routing** — deciding *what* to attend to based on semantic content, not fixed positions.
3. **Arbitrary position retrieval** — recovering specific info from anywhere in the sequence.

Mapping prior art onto the trilemma:
- **Sliding-window attention (e.g., Mistral):** subquadratic + arbitrary retrieval (via stacking), but routing is *positional* — it decides where to look before knowing what to look for. No content routing.
- **State-space models (Mamba):** subquadratic + content routing (selective gating), but a fixed-capacity recurrent state causes **recall decay** over long distances. Weak arbitrary retrieval.
- **Hybrids (Jamba):** content routing + arbitrary retrieval, but "the cost curve still bends quadratically — it bends later, but it bends."
- **DeepSeek DSA:** appears subquadratic, but the **Lightning Indexer scores every query-key pair** (a cheaper op per pair, but still O(n²)). The quadratic term is "moved, not removed," and at ~1M tokens it dominates again. Core sparse attention is O(nk); the indexer remains O(n²).

### What SSA claims to do differently
SubQ's claim is that the **selector reaches the relevant positions without ever scanning all of them** — i.e., the indexer path itself is subquadratic. The launch materials and analyses point to three candidate mechanisms (the exact implementation is unpublished):
- **Hash-based lookup** (approximate nearest-neighbor / LSH-style retrieval over keys),
- **Hierarchical / clustering-based selection** (group tokens into clusters, reason at the cluster level, then "zoom in" to individual tokens), and
- **Learned routing** (a trained router that emits candidate positions directly).

Mechanically, for each query token the model:
1. Uses the sub-quadratic selector to nominate a small candidate set of positions (top-k, k « n),
2. Computes **exact** attention only over those positions, and
3. Mixes in local attention to preserve adjacency structure while retaining global reach.

### Complexity comparison (as reported)
| Mechanism | Indexer / selection cost | Attention cost | Net asymptotic |
|---|---|---|---|
| Dense (FlashAttention) | n/a | O(n²) | O(n²) |
| DeepSeek DSA | **O(n²)** (lightning indexer scores all pairs) | O(nk) | **O(n²)** (indexer dominates) |
| **SubQ SSA (claimed)** | **sub-quadratic** (no all-pairs scan) | O(nk) | **~O(n) / O(n·k)** |

This is the crux of the novelty and also the crux of the doubt: the selection step is exactly where prior "sparse" systems quietly remained quadratic. SubQ asserts it breaks the trilemma — subquadratic **and** content-routed **and** arbitrary-retrieval simultaneously. Whether that holds under independent scrutiny is unresolved.

### Training recipe (as described, partial)
- Built on an **open-weight base model** (CTO confirmed they "do not train from scratch"; widely speculated to be DeepSeek V3.2 or Kimi family), then **post-trained** by Subquadratic to install the sparse-attention behavior.
- Pipeline described as: long-context pre-training/continued-training → supervised fine-tuning for reasoning/code → RL to exploit global attention across the full sequence.
- No disclosed model size, token budget, or training compute.

### Note on the naming inconsistency
Sources alternately expand "SSA" as **Selective** Attention and **Sparse** Attention, and the marketing oscillates between O(n·k) (sparse) and near-O(1)-per-step (recurrent-like) language. DataCamp flags that O(n·k) at the claimed quality would not by itself obviously justify the headline 12M / 1,000x figures, suggesting either additional mechanisms (caching, compression) or marketing rounding. The unpublished report is needed to resolve this.

---

## Evidence & Benchmarks

### Efficiency (vendor-reported, FlashAttention-2 on B200)
| Context | Speedup vs FA-2 | Attention FLOPs vs dense |
|---|---|---|
| 128K | **7.2x** | ~1/8 |
| 512K | **23.0x** | — |
| 1M | **52.2x** | ~1/62.5 |
| 12M | (extrapolated) | ~**1/1000** |
- Launch post also states SSA is "52x faster than FlashAttention while requiring 63% less compute."

### Quality (vendor-reported; comparison baselines disputed)
| Benchmark | SubQ | Comparators (as cited by vendor / press) |
|---|---|---|
| **RULER 128K** | 95.0–95.6% | Claude Opus 4.6: 94.8% |
| **MRCR v2 (8-needle, 1M)** | research 83 / **production 65.9** | Opus 4.6: 32.2 (marketing) **vs 78.3 (Opus tech report)**; GPT-5.5: 74.0; Gemini 3.1 Pro: 26.3; DeepSeek V4: 83.5 |
| **SWE-Bench Verified** | 81.8% | Opus 4.6: 80.8; Opus 4.7: 87.6; GPT-5.5: 88.7; DeepSeek 4.0 Pro: 80.0 |
| **Needle-in-haystack @ 12M** | >90% (cited 92.1%) | — (no comparator exists at this length) |
- **Cost anecdote:** RULER 128K at 95% for **~$8**, vs Claude Opus ~94% for ~**$2,600** (≈300x cheaper on that single run).

### Contested claims, ablations, and open questions
- **The MRCR red flag (most important).** Subquadratic compared against Opus 4.6 at **32.2** on MRCR while Anthropic's own technical report lists **78.3** for the same model. Using the lower number flatters SubQ. Multiple analysts (Firethering, DataCamp) call this out as a significant cherry-pick.
- **The ~17-point research-vs-production MRCR gap** (83 → 65.9) is unexplained; the headline numbers come from a configuration users cannot access.
- **Single-run benchmarks.** Per The New Stack, each model was run only once "due to inference cost," with no confidence intervals — meaningful variance risk. Whedon described SubQ as "way smaller than the big labs."
- **Narrow benchmark surface.** Essentially three evals, all in SubQ's home turf (long-context retrieval + coding). No broad reasoning, math, multilingual, safety, or short-context numbers — and sparse attention often *underperforms* dense attention at short context.
- **No independent reproduction.** "Third-party verified, according to the company" ≠ independent replication. No external lab "that Subquadratic doesn't pay" has reproduced the speedups or the 12M retrieval.
- **Researcher reactions (named):** Stepan Goncharov — "very interesting cherry-picked benchmarks"; others — "suspiciously perfect." Will Depue suggested it is likely "a sparse-attention finetune of Kimi or DeepSeek." Countervailing: John Rysana — "just subquadratic attention done well, which is very meaningful for long-context workloads." Dan McAteer summed up the polarization: "either the biggest breakthrough since the Transformer… or it's AI Theranos."
- **Historical prior:** Mamba, RWKV, Hyena, S4 all showed clean linear scaling on benchmarks before hitting a quality wall at frontier scale; the burden of proof is high.

---

## Maturity Assessment

**Status: research/early-commercial preview, not production-validated.**

- **Reproducibility: low.** No weights, no technical report, no independent reproduction (as of early June 2026). Single-run, narrow benchmarks with at least one demonstrable comparator cherry-pick. This is the dominant risk.
- **Productization: partial.** API (OpenAI-compatible), CLI coding agent, and search tool exist but are private-beta/waitlist. The headline 12M context is a "research model"; the broadly available preview targets ~1M.
- **Compute/data requirements:** Undisclosed. They build on an open base rather than training from scratch, which lowers their cost but means the *foundation* capability is inherited; the claimed contribution is the attention mechanism plus post-training. If true, that is also good news for adopters: the technique may be portable onto other open bases.
- **Architecture-level novelty plausibility:** The trilemma framing is sound, and a sub-quadratic *indexer* is the correct thing to attack (it is precisely where DSA stayed quadratic). A learned/hash/cluster router that avoids all-pairs scoring is technically credible in principle (LSH and ANN retrieval are well established). The open question is whether it preserves frontier-grade quality and arbitrary retrieval at 1M–12M without recall decay — exactly the wall that prior subquadratic methods hit.
- **Commercial precedent caution:** Magic.dev (2024) made comparable ultra-long-context claims with limited subsequent real-world adoption despite large funding.
- **Net:** Treat as a *promising, unverified* architecture. Do not build production-critical dependencies until (a) a technical report or weights enable replication, or (b) you reproduce the efficiency and long-context retrieval claims internally on your own data.

---

## PayPal Fraud/Risk Implications

If — and only if — the linear-scaling, content-routed indexer is real and quality holds, SSA-class attention is unusually well matched to several Fraud & Risk needs. Concrete angles:

### 1. Long-horizon entity memory (the strongest fit)
- A genuinely linear indexer lets you keep an **ever-growing per-entity event log** (account, device, IP, merchant) as **live model context** rather than collapsing it into hand-engineered aggregates or a fixed recurrent state. Mamba-style SSMs cannot do this well (recall decay); dense transformers cannot afford it (quadratic blow-up).
- **Slow-burn fraud** is the target use case: account farming, **synthetic-identity aging**, dormant-then-activated mules, and merchant bust-out. These play out over months/years of events — exactly the regime where 1M–12M token context with arbitrary retrieval (find the one anomalous event amid millions) could outperform RAG/aggregate pipelines that lose the needle.
- Content-dependent selection means the model can attend to the *semantically relevant* historical events for a given query (e.g., prior chargebacks, device changes) rather than only recent or positionally near ones.

### 2. Latency and cost at scoring time
- Real-time risk scoring needs **sub-100ms**. The reported speedups are for **long context**; at the short contexts typical of a single transaction decision, sparse attention can be *no faster or slower* than dense. The efficiency win is for **long-context** decisions — e.g., investigative scoring over a full account history, batch re-scoring, or agentic case review — not necessarily the hot-path 100ms decision.
- Where it could help the hot path: amortizing a large persistent entity context with a prefilled/cached selective-attention KV state, so per-event marginal cost stays low even as history grows. This needs internal latency benchmarking; vendor numbers do not address tail latency or sub-100ms SLAs.

### 3. Sequence + graph + multimodal signals
- Fraud signals are tabular + text + event-sequence + graph (accounts/devices/IPs/merchants). A 12M-token window could ingest **linearized neighborhoods of a transaction graph** plus raw event sequences plus dispute text in one prompt, letting the model do content-routed cross-referencing that today requires separate GNN + sequence + tabular models stitched together. This is speculative but architecturally plausible.

### 4. Adversarial robustness / drift
- **Cuts both ways.** Longer memory could improve robustness to slow adversarial drift (the model "remembers" an entity's long baseline). But **learned content-based selection is itself an attack surface**: an adversary who understands the router could craft events that cause the selector to *ignore* the incriminating history (selection evasion / context-poisoning). Any deployment must red-team the indexer specifically. Class imbalance and adversarial evolution also mean the narrow, retrieval-flavored benchmarks SubQ published say little about fraud-relevant precision/recall under attack.

### 5. Agentic investigation / case review
- SubQ Code / SubQ Search-style agents over a full case file (entire account history, linked entities, prior investigator notes) is a natural fit for **investigative/agentic case workflows**. Loading a complete case into one context for an analyst-assist agent is exactly the "entire codebase in one window" pitch, repurposed for fraud cases.

### 6. Explainability / auditability (a concern, not a win)
- Regulatory review demands explainable, auditable decisions. Sparse, content-routed attention does expose **which positions/events were selected**, which could become an attribution signal ("the model attended to these 8 historical events"). But the selection mechanism is proprietary and unpublished, single-run-benchmarked, and not reproducible — **unacceptable as-is for regulated model risk management**. Internal, white-box reimplementation of the technique on owned models would be the only defensible path.

### Adoption recommendation for Fraud/Risk
- **Do not** adopt the hosted SubQ API for production risk decisions on the current evidence (no reproducibility, regulatory auditability gaps, vendor-only benchmarks, base-model provenance uncertainty).
- **Do** treat SSA as a research signal worth internal investigation: prototype a sub-quadratic-indexer long-context model on owned open weights, and benchmark specifically on (a) long-horizon slow-burn fraud recall, (b) selection-evasion adversarial tests, and (c) tail latency under persistent entity context. Gate any rollout on internal reproduction, not vendor claims.

---

## Sources

- Subquadratic, "Introducing SubQ: The First Fully Subquadratic LLM" (vendor primary) — https://subq.ai/introducing-subq
- SiliconANGLE, "Subquadratic launches with $29M to bring 12M-token context windows to AI" (2026-05-05) — https://siliconangle.com/2026/05/05/subquadratic-launches-29m-bring-12m-token-context-windows-ai/
- The New Stack, "The context window has been shattered: Subquadratic debuts a 12-million-token window" — https://thenewstack.io/subquadratic-12-million-context-window/
- cozypet, "subq-field-map" / "Every Transformer Is Quadratic. SubQ Claims It Isn't." (attention-trilemma technical analysis) — https://cozypet.github.io/subq-field-map/ and https://github.com/cozypet/subq-field-map/blob/main/article.md
- Firethering, "SubQ's 12M Token Model Could Change How AI Handles Long Context. If It's Real." — https://firethering.com/subq-12m-token-context-llm-subquadratic-attention/
- DataCamp, "SubQ AI Explained: How Good Is the 12M Context Window LLM?" — https://www.datacamp.com/blog/subq-ai-explained
- explainx.ai, "SubQ: SSA sparse attention, 12M context, and long-context evals" — https://explainx.ai/blog/subq-ssa-sparse-attention-12m-context-2026
- VentureBeat, "Miami startup Subquadratic claims 1,000x AI efficiency gain with SubQ model; researchers demand independent proof" — https://venturebeat.com/technology/miami-startup-subquadratic-claims-1-000x-ai-efficiency-gain-with-subq-model-researchers-demand-independent-proof
- Refresh Miami, "Subquadratic raised $29M on the idea that it has cracked AI's biggest math problem. Now comes the hard part." — https://refreshmiami.com/news/subquadratic-raised-29m-on-the-idea-that-it-has-cracked-ais-biggest-math-problem-now-comes-the-hard-part/
- eWeek, "Subquadratic Launches SubQ, a 12M-Token AI Model for Long-Context Tasks" — https://www.eweek.com/news/subquadratic-subq-12m-token-llm-neuron/
- Pulse2, "Subquadratic: $29 Million Seed Raised For Long-Context AI Architecture" — https://pulse2.com/subquadratic-29-million-seed-raised-for-long-context-ai-architecture/
- DeepSeek-AI, "Native Sparse Attention: Hardware-Aligned and Natively Trainable Sparse Attention," arXiv:2502.11089 — https://arxiv.org/pdf/2502.11089
- DeepSeek-AI, "DeepSeek-V3.2" (DeepSeek Sparse Attention / Lightning Indexer), arXiv:2512.02556 — https://arxiv.org/pdf/2512.02556
- vLLM Blog, "DeepSeek-V3.2-Exp in vLLM: Fine-Grained Sparse Attention in Action" (2025-09-29) — https://blog.vllm.ai/2025/09/29/deepseek-v3-2.html
- LMSYS Blog, "SGLang Day 0 Support for DeepSeek-V3.2 with Sparse Attention" (2025-09-29) — https://www.lmsys.org/blog/2025-09-29-deepseek-V32/
