# Hybrid Verified Decoding: Payoff-Predicted Allocation of Verification

**Research window:** April 2026 – June 2026 · **Report date:** 2026-06-03

## Executive Summary

Hybrid Verified Decoding (HVD), introduced in arXiv:2606.01019 ("Hybrid Verified Decoding: Learning to Allocate Verification in Speculative Decoding," May 31, 2026, by authors from Thoughtworks and NVIDIA), reframes speculative decoding as a *control problem*: at each decode step, decide whether to spend verification compute on a cheap cache-derived draft or on a learned model-based drafter. The core innovation is a lightweight MLP "payoff predictor" that, using only signals available **before** verification, forecasts how many tokens of a candidate cache draft the target model will accept; if the predicted accepted length exceeds a threshold (τ = 6), the system verifies the long cache draft, otherwise it falls back to an EAGLE-3-style model drafter. The payoff is concentrated: the paper reports that only ~4.8–8.9% of cache drafts are genuinely high-payoff, yet the predictor recovers most of them (61–80% recall, 78–88% precision), yielding a **2.73× average speedup over EAGLE-3 on agentic workflows** and 2.97× over greedy decoding across 3 LLMs (Qwen3-8B, Qwen3-4B, Llama-3.1-8B) and 16 datasets, while remaining lossless (token verification preserves the target distribution). The contribution is a control-layer advance rather than a new drafting primitive, and the evaluation is honest about its scope: deterministic (temperature 0) decoding, batch size 1, two model families. For PayPal's agentic fraud case-review traffic — which is highly repetitive in scaffolds, tool outputs, and policy boilerplate — HVD is directly relevant: it can cut per-case latency and GPU cost roughly 2-3× while preserving exact, auditable outputs.

## What's New in the Window

**Primary release.**
- **Hybrid Verified Decoding: Learning to Allocate Verification in Speculative Decoding** — arXiv:2606.01019, submitted **May 31, 2026**. Authors: Xin Su, Dawid Majchrowski, Fangyuan Yu, Vanshil Atul Shah, Sebastian Rogawski, Pawel Morkisz, Anahita Bhiwandiwalla, Phillip Howard. Affiliations: **Thoughtworks** (Xin Su, Fangyuan Yu, Phillip Howard) and **NVIDIA** (Majchrowski, Shah, Rogawski, Morkisz, Bhiwandiwalla). HTML: https://arxiv.org/html/2606.01019, abstract: https://arxiv.org/abs/2606.01019.

This paper is the headline development in the window. It sits at the intersection of two now-converging lines of speculative decoding research:

1. **Model-free / retrieval drafting for repetitive workloads** — exemplified by **SuffixDecoding** (arXiv:2411.04975, NeurIPS 2025 Spotlight; CMU/Snowflake), which caches token sequences in suffix trees and speculates at ~20 µs/token on CPU, reporting up to 5.3× on agentic benchmarks (SWE-Bench, AgenticSQL) and ~2.8× over EAGLE-2/3. HVD adopts SuffixDecoding's suffix-cache as its cache-draft source. Productionized in Snowflake's **ArcticInference** (up to 4.5× end-to-end on agent tasks).
2. **Model-based drafting that scales with training** — exemplified by **EAGLE-3** (arXiv:2503.01840, March 2025), which replaces feature prediction with direct token prediction plus multi-layer feature fusion ("training-time test"), discovers a data-scaling law for draft acceptance, and reports 3–6.5× speedups. HVD uses EAGLE-3 as its model-based fallback drafter and primary baseline.

HVD's "new" contribution is neither of these primitives but the **learned runtime arbitration between them**, conditioned on a per-step payoff prediction. A loosely related contemporaneous thread is **"Speculative Speculative Decoding"** (arXiv:2603.03251, ICLR 2026; Kumar, Dao, May), which recursively applies speculation to the drafter itself — a different axis (cheaper drafting) than HVD's (smarter draft *selection*).

## Technical Deep-Dive

### The problem HVD targets

In speculative decoding, the target model verifies several drafted tokens in one forward pass; the realized speedup is governed by how many drafted tokens are *accepted*. Cache/retrieval drafts (e.g., SuffixDecoding) are nearly free to produce but have *bimodal* payoff: when the current context matches a long cached suffix (common in repetitive agentic traffic) acceptance is long and the speedup is large; when it does not, verifying a long, wrong cache draft wastes a target forward pass. Model-based drafters (EAGLE-3) give steadier but shorter acceptance (EAGLE-3 averages ~2.4 accepted tokens/step at ~40% acceptance) at the cost of a draft-model forward pass. The decision of *which drafter to verify at each step* is normally made by hand-tuned heuristics (e.g., cache suffix-match score thresholds). HVD learns this decision.

### Payoff predictor

- **Architecture:** a lightweight MLP — 2 hidden layers × 256 units, ReLU — trained by squared-error regression `min_θ Σ_t (g_θ(φ_t) − y_t)²` to predict accepted length `y_t` from pre-verification features `φ_t`. Training: batch 65,536, 20 epochs, lr 1e-3, seed 42.
- **Features (all available before any target verification):**
  - *Cache match*: suffix score, matched length, candidate draft length.
  - *Decode state*: prompt length, generated length, relative position.
  - *Recent history*: rolling cache-selection rate and recent accepted lengths.
  - *Draft structure*: presence of whitespace, punctuation, brackets, delimiters (cheap lexical signals of structured/boilerplate continuations).
- **Labels via trace replay (no extra inference):** for each token position `t` in a *previously recorded* target-model generation, treat it as a decode state and set the label to the longest prefix of the cache draft that matches the actual subsequent tokens: `y_t = max{ℓ : d^c_{t,1:ℓ} = x_{t+1:t+ℓ}}`. Because labels come from replaying existing traces, training the predictor requires no additional model forward passes — important for cheap re-tuning on a new traffic distribution.

### Decision rule and the "concentration" finding

At each step the suffix cache proposes a candidate continuation; the predictor scores it; if predicted accepted length **> τ = 6**, HVD verifies the (long) cache draft, otherwise it invokes the EAGLE-3 model drafter (draft tree depth 8, ~32 tokens, top-k 4) and verifies that. The threshold is chosen so that selected cache drafts amortize the cost of a target forward pass over many committed tokens.

The empirical motivation is a **sparsity/concentration result**: only **4.8–8.9%** of proposed cache drafts are oracle-high-payoff (≥6 tokens accepted), but those few account for most of the achievable speedup. The MLP recovers them at **61–80% recall and 78–88% precision** — enough to capture most of the upside while rarely paying for a long, doomed cache verification. This is the crux of why a *learned* selector beats a *rule-based* one (suffix-score thresholds), which the paper includes as a hybrid baseline.

### Cache structure

The cache-draft source is a **suffix cache following SuffixDecoding** (arXiv:2411.04975): it indexes suffix matches over the prompt plus tokens committed so far and returns candidate continuations from matched spans with no model forward pass. Config: max tree depth 64, max draft tokens 64, min token probability 0.1.

### Losslessness

HVD uses standard speculative-decoding verification: the target model independently checks the proposed tokens, returning the accepted-prefix length and the committed token block. This preserves the target model's output distribution exactly (lossless up to hardware numerics, the same guarantee that underpins all rejection-sampling-based speculative decoding). Note the experiments use **deterministic decoding (temperature 0)**, so the lossless property is exercised in its greedy form; sampling-temperature behavior is not separately studied.

### What changed vs prior art

- **vs SuffixDecoding/SAM-Decoding (cache-only):** adds a learned escape hatch — when the cache draft is predicted low-payoff, HVD does not waste a verification pass on it but switches to a model drafter. Execution analysis: HVD runs at **39.6 ms/cycle** vs **48.4 ms** for cache-only and **43.3 ms** for a rule-based hybrid.
- **vs EAGLE-3 (model-only):** on repetitive/agentic traffic, HVD opportunistically grabs the long, cheap cache drafts EAGLE-3 cannot match, hence 2.73× over EAGLE-3.
- **vs rule-based hybrids:** the learned predictor's better precision/recall on the rare high-payoff drafts is the measured source of gain.

## Evidence & Benchmarks

**Setup:** 3 instruction-tuned LLMs (Qwen3-8B, Qwen3-4B, Llama-3.1-8B) × 16 datasets across six families — agentic/workflow (Delegate-52, InstructEdit/FineEdit), code/repo (RepoBench, SWE-bench OpenHands, Magicoder, MBPP), structured (BFCL, Spider), multi-hop QA (HotpotQA, MuSiQue, 2WikiMultiHopQA), long-context (InfiniteBench, CNN/DailyMail, GovReport), open-ended (Alpaca, MT-Bench). 48 model-dataset pairs. vLLM prototype, **batch size 1**.

**Headline results:**
- **2.73× average speedup over EAGLE-3 on agentic workflows**, "outperforms EAGLE-3 in every setting" among the agentic configs.
- **2.97× average over greedy decoding** across all 48 pairs.
- **2.64× average over SuffixDecoding**.
- Highest gains on the most repetitive workload (Delegate-52, up to **3.40×**); smaller gains on the smaller model (Qwen3-4B averages ~2.53×) and on less-repetitive open-ended/long-context sets.

**Predictor quality (ablation core):** high-payoff drafts are 4.8–8.9% of all cache drafts; predictor achieves 61–80% recall / 78–88% precision; per-cycle latency drops from 48.4 ms (cache-only) and 43.3 ms (rule-based hybrid) to 39.6 ms (learned HVD), evidencing the selector's value.

**Limitations and open questions (per paper and analysis):**
- **Two model families only** (Qwen, Llama); cache×EAGLE-3 is the only drafter pairing evaluated — "broader draft-source combinations, such as multi-head drafters" untested.
- **Deterministic decoding (T=0) only**; no temperature/sampling sweep, so acceptance behavior and lossless guarantee under stochastic sampling are not separately validated.
- **Batch size 1.** No throughput-vs-latency or batched-serving analysis. This is the most consequential gap for production: at high batch sizes the target forward pass is GPU-bound and the arithmetic of "wasted verification" changes; cache drafts also interact with shared KV-cache/continuous batching in ways the paper does not study.
- **Fixed threshold τ = 6.** Not adaptive to model size or workload; the smaller-model regression suggests τ may need per-deployment tuning.
- **Contested/uncertain framing:** the 2.73× headline is against EAGLE-3 *on agentic subsets*; the all-dataset numbers are vs greedy/SuffixDecoding. Speedups are workload-conditioned and will shrink on non-repetitive traffic — consistent with, not contradicting, the SuffixDecoding literature, but worth not over-generalizing.

## Maturity Assessment

**Stage:** Research prototype with a credible engineering path to production. The method is built on two already-productionized primitives — SuffixDecoding (shipping in Snowflake ArcticInference) and EAGLE-3 (integrated in vLLM/SGLang ecosystems) — and HVD itself is prototyped in vLLM. The only net-new component is a tiny MLP (2×256), which is trivially cheap to train and serve.

**Compute/data requirements:**
- *Predictor training:* negligible. Labels come from **trace replay** of existing generation logs (no extra model inference), so the predictor can be retrained on a deployment's own traffic in minutes on a CPU/single GPU. This is a notable operational advantage — the selector adapts to a new distribution without re-running the LLM.
- *Drafters:* requires a trained EAGLE-3 head for the target model (the expensive part, but standard and reusable) plus a suffix cache (cheap, CPU, ~20 µs/token as in SuffixDecoding).
- *Runtime overhead:* the MLP overhead is not isolated but is clearly amortized — total cycle time *drops* vs cache-only and rule-based hybrids.

**Reproducibility:** Hyperparameters are fully specified (MLP shape, batch, epochs, lr, seed, τ, cache limits, EAGLE-3 tree config); models and datasets are public; baselines (greedy, SuffixDecoding, EAGLE-3, rule-based hybrid) are standard. Main reproduction risks are the agentic datasets (Delegate-52, InstructEdit/FineEdit availability) and the vLLM-prototype integration details. No public code link confirmed as of this writing.

**Net:** production-*adaptable* for batch-1 / latency-sensitive single-stream serving; **not yet validated** for high-throughput batched serving, which is the regime most fraud-scoring fleets actually run.

## PayPal Fraud/Risk Implications

The relevance is highest for **agentic / investigative case-review workflows**, and more nuanced for real-time transaction scoring.

**1. Agentic fraud case review (strong fit).** Investigative agents (alert triage, evidence gathering, narrative generation, SAR/regulatory drafting, tool-calling over internal risk APIs) produce highly repetitive token streams: fixed reasoning scaffolds, recurring tool-output formats, policy boilerplate, and templated rationales. This is exactly the "high-payoff cache draft concentrates in a small part of the draft space" regime HVD exploits. Expected impact:
   - **Latency:** ~2.7–3× lower per-case decode latency vs an EAGLE-3-only deployment, shortening analyst-in-the-loop cycles and enabling more cases reviewed per shift.
   - **GPU cost:** roughly proportional reduction in decode FLOPs per case at batch-1/low-batch, materially lowering the cost of running large investigative agents at scale.
   - **Auditability preserved:** verification is lossless — the committed tokens are exactly the target model's outputs — so accelerated case narratives and decisions remain bit-for-bit equivalent to the un-accelerated model, which matters for regulatory review and reproducible decision records.
   - **Cheap self-tuning:** because the payoff predictor trains from trace replay of logged generations, it can be re-fit on PayPal's own case-review traffic without re-running the LLM, adapting τ and feature weights to PayPal-specific scaffolds and as fraud playbooks evolve.

**2. Real-time transaction risk scoring (weak/indirect fit).** Sub-100ms scoring is typically tabular/sequence/graph model territory (GBDTs, sequence encoders, GNNs), not autoregressive LLM decoding, so HVD does not directly accelerate the hot path. Where an LLM *is* in the loop (e.g., generating textual reason codes, summarizing entity histories, or producing explanations for flagged transactions), HVD could cut that generation latency — but the paper's batch-1 evidence is a real caveat: production scoring fleets run at high batch/throughput, a regime HVD has not validated. Treat batched-serving gains as unproven until tested.

**3. Long-horizon entity memory / sequence & graph signals.** HVD does not improve memory, sequence modeling, or graph reasoning per se. Indirectly, the suffix-cache draft source rewards *repetition across a session* — if investigative agents replay entity histories, device/IP/merchant relationship summaries, or prior-case templates, those repeated spans become high-payoff cache drafts, so longer, more memory-heavy prompts can actually *increase* cache acceptance rather than slow things down.

**4. Adversarial robustness.** Neutral-to-mildly-positive. Because verification is lossless, an adversary cannot change *outputs* by manipulating the drafter — at worst they degrade *speed*. A conceivable nuisance vector: crafting inputs that defeat the cache (no repetitive structure) to force the slower model-drafter path; impact is bounded (latency, not correctness) and the learned predictor will simply route to the model drafter. Worth noting but low severity.

**5. Explainability.** Positive by construction: lossless decoding means accelerated explanations/reason codes are identical to what the un-accelerated target model would emit, so speedups do not compromise the explanation artifacts used in regulatory/audit review.

**Recommended next step for PayPal:** prototype HVD on an internal agentic case-review pipeline at the batch sizes it actually serves, training the payoff predictor on logged case-review traces, and measure (a) speedup vs EAGLE-3-only at production batch, (b) cache-acceptance distribution on real scaffolds, and (c) sensitivity of τ. The high-leverage open question is whether the batch-1 gains survive continuous batching.

## Sources

- Hybrid Verified Decoding (primary) — https://arxiv.org/abs/2606.01019 and https://arxiv.org/html/2606.01019
- SuffixDecoding — https://arxiv.org/abs/2411.04975 ; CMU blog https://www.cs.cmu.edu/~csd-phd-blog/2025/suffix-decoding/ ; project page https://suffix-decoding.github.io/ ; OpenReview https://openreview.net/forum?id=uwL0vbeEVn
- SAM Decoding (suffix automaton speculative decoding) — https://arxiv.org/pdf/2411.10666
- Snowflake ArcticInference / fast speculative decoding in vLLM — https://www.snowflake.com/en/engineering-blog/fast-speculative-decoding-vllm-arctic/
- EAGLE-3 — https://arxiv.org/abs/2503.01840 ; HTML https://arxiv.org/html/2503.01840v1 ; OpenReview https://openreview.net/forum?id=4exx1hUffq ; summary https://wentao.site/eagle_v3_summary/ ; HF practical write-up https://huggingface.co/blog/lujangusface/tw-eagle3-gpu
- Speculative Speculative Decoding (related, ICLR 2026) — https://arxiv.org/pdf/2603.03251 ; OpenReview https://openreview.net/forum?id=aL1Wnml9Ef
- Lossless / exact-distribution verification background — vLLM docs https://docs.vllm.ai/en/latest/features/speculative_decoding/ ; Traversal Verification https://arxiv.org/pdf/2505.12398 ; heterogeneous-vocabulary lossless SD https://arxiv.org/html/2502.05202v3
- Author affiliation corroboration — Anahita Bhiwandiwalla (Intel Labs background) https://www.intel.com/content/www/us/en/research/featured-researchers/anahita-bhiwandiwalla.html ; Phillip Howard (Google Scholar) https://scholar.google.com/citations?user=EKh822gAAAAJ
