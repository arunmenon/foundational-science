# ZAYA1-8B MoE++: Compressed Convolutional Attention + PID-Controlled Router

**Research window:** April 2026 – June 2026 (compiled 2026-06-03)
**Primary artifact:** Zyphra ZAYA1-8B, released May 6, 2026 (ZAYA1-8B Technical Report, arXiv:2605.05365v1)

## Executive Summary

On May 6, 2026, Zyphra released **ZAYA1-8B**, an Apache-2.0 Mixture-of-Experts (MoE) reasoning model with **8.4B total / ~760M active parameters** that matches or exceeds substantially larger open-weight and proprietary models on math, code, and reasoning benchmarks. Its headline is a triad of architecture changes Zyphra brands "MoE++": (1) **Compressed Convolutional Attention (CCA)**, a latent-space attention variant achieving **8× KV-cache compression** and **2× query compression** relative to full multi-head attention; (2) an **MLP-based router with PID-controller bias balancing**, which replaces auxiliary-loss / bias-nudge load balancing with a control-theoretic feedback loop driven through AdamW; and (3) **learned residual scaling** to control residual-norm growth through depth at negligible cost. Equally notable is the systems claim: ZAYA1 is, per Zyphra and AMD, the first frontier-class MoE pretrained, midtrained, and SFT'd **end-to-end on AMD Instinct MI300X** (1,024 GPUs across 128 nodes, AMD Pensando Pollara 400 networking, co-built with IBM). The thesis is "intelligence density per active parameter" — sub-billion active compute delivering reasoning competitive with 30B–106B-active-class models. The work is genuinely interesting for cost/latency-bound inference and for auditable routing, but several claims (FLOP utilization parity with NVIDIA, "punches above weight" framing) rest on the company's own technical report rather than independent reproduction, and key data sources and per-stage ablations are withheld.

## What's New in the Window

- **ZAYA1-8B Technical Report** — Zyphra, May 6, 2026. arXiv:2605.05365 (HTML: https://arxiv.org/html/2605.05365v1). Introduces the MoE++ architecture (CCA + ZAYA1 router + learned residual scaling), the full pretraining→SFT→RL pipeline on AMD MI300X, and **Markovian RSA** test-time compute.
- **Model + weights** — released Apache-2.0 on Hugging Face; serverless endpoint on Zyphra Cloud. Two checkpoints referenced: **ZAYA1-Base** (8.3B total / 760M active) and the post-trained **ZAYA1-8B** reasoning model.
- **Zyphra launch post** — "ZAYA1-8B: Frontier intelligence density, trained on AMD" (https://www.zyphra.com/post/zaya1-8b).
- **AMD/IBM systems announcement** — AMD press materials (via StockTitan) describing the 128-node × 8-GPU MI300X cluster, Pensando Pollara 400 interconnect, IBM Cloud collaboration, and a ">10× faster model save times" distributed-I/O claim (https://www.stocktitan.net/news/AMD/...).
- **Press / analysis coverage (all early-to-mid May 2026):** VentureBeat, MarkTechPost, HPCwire/AIwire, Morningstar/PR Newswire, plus secondary explainers (Let's Data Science, BuildFastWithAI, DataNorth).

This is a single-release event with surrounding coverage; no independent third-party reproduction or competing follow-up paper appeared within the window.

## Technical Deep-Dive

### Architecture overview

| Property | Value |
|---|---|
| Total params | 8.4B (Base reported as 8.3B) |
| Active params | ~0.76B (top-1 routing) |
| Transformer layers | 40 |
| Hidden dimension | 2048 |
| Experts per MoE layer | 16 |
| Top-k | **1**, no residual/shared experts |
| Expert FFN width | 4096 pre-act / 2048 post-act |
| Attention | CCA: 8 query heads, 2 KV heads, head dim 128 |
| License | Apache-2.0 |

The top-1, no-shared-expert choice is unusual versus contemporary MoEs (which often use top-2/top-8 plus shared experts). Zyphra's hypothesis: the stronger MLP router "assigns more certain expert choices, with better expert specialization, so additional experts in parallel via top-k are less useful." The report shows ZAYA1 produces **lower-entropy (more confident) per-token routing** than linear routers, consistent with that argument.

### 1. Compressed Convolutional Attention (CCA)

CCA performs sequence mixing **in a compressed latent space** using a lightweight **convolutional down-projector**, then attends. Reported compression: **query 2×, KV-cache 8×** relative to full multi-head attention. With 8 query heads and 2 KV heads at head dim 128, this combines GQA-style head sharing with an additional learned convolutional compression of the K/V representation.

- **vs prior art:** Positioned as "competitive with MLA and GQA" while reducing **prefill FLOPs** and improving **training speed relative to GQA and MLA**. Where MLA (DeepSeek) compresses KV via a low-rank latent projection, CCA uses a *convolutional* down-projector — i.e., local sequence-mixing is folded into the compression, not just a per-token linear bottleneck.
- **Long-context enabler:** CCA's small KV footprint is what makes 32K midtraining (1.2T tokens) and 131K SFT (660B tokens) tractable on MI300X. Under context parallelism, "short asynchronous point-to-point exchanges handle the convolution and value-shift boundary conditions" across CP ranks — i.e., the convolution introduces cross-rank halo dependencies that are handled with localized comms.
- **Caveat:** the exact kernel size and decompression math are deferred to Appendix C; the public HTML does not fully specify them, so the precise convolution geometry is not independently verifiable from the body text.

### 2. ZAYA1 router with PID-controller bias balancing

The router is an **MLP**, not a linear projection. Pipeline:

```
r_l = W_down · x_l                 # residual stream D -> router latent R = 256
r_l = r_l + γ · r_{l-1}            # Exponential Depth Averaging (EDA), learned γ
s_l = softmax( MLP( RMSNorm(r_l) ) )   # 3-layer GeLU MLP -> per-expert scores
e_idx = topk( s_l + b_l )          # selection uses score PLUS learned balancing bias
```

**Exponential Depth Averaging (EDA)** mixes the current layer's router latent with the previous layer's (`γ` learned), smoothing routing decisions across depth.

**PID bias balancing.** The balancing bias `b_{l,e}` is updated by a control loop whose error/gradient signal is the deviation of empirical load from uniform:

```
∇b_{l,e} = p_{l,e} − 1/E
```

where `p_{l,e}` is the empirical fraction of tokens routed to expert `e` and `E = 16`. Crucially, this error is **fed into AdamW** rather than applied as a fixed-step sign nudge. That is the conceptual leap: DeepSeek's loss-free balancing uses a simple bias increment in the direction of the load error (effectively pure proportional control with a hand-set step). Routing the error through AdamW supplies **momentum (an integral-like accumulation) and adaptive per-parameter scaling (a derivative-/curvature-aware term)** — i.e., the bias controller behaves like a PID loop rather than a P-only controller. Zyphra reports this "improved the convergence speed and stability of the PID loop relative to the classical DeepSeek implementation." Figure 4 shows normalized router-load entropy `H(p)/ln(E)` reaching near-maximum within ~100 steps, faster than the linear-router baseline.

**Why this matters beyond tidiness:** auxiliary-loss balancing perturbs the language-modeling gradient (a known accuracy tax), and fixed-step bias nudges can oscillate or under-react under distribution shift. A momentum-smoothed feedback controller is, by construction, more robust to transient load spikes and quicker to recover from perturbations — a property the report demonstrates via entropy-recovery curves. Note: the body text describes the *proportional* error term explicitly and attributes integral/derivative behavior to the optimizer rather than spelling out separate I and D coefficients, so "PID" here is partly a framing of AdamW dynamics rather than three hand-tuned gains.

### 3. Learned residual scaling

Per layer, two learned vectors `α, β ∈ ℝ^D` rescale the residual stream / layer output: `Res-scale(x) = αx + β`. Overhead is ~`4·L·D` parameters (negligible). Purpose: control residual-norm growth through 40 layers without gradient pathologies — described as delivering benefits similar to Qwen's attention-gating without the gating-matrix cost.

### 4. Training pipeline and AMD systems

| Phase | Context | Tokens | Notes |
|---|---|---|---|
| Pretrain 1 | 4K | 8T | broad web |
| Pretrain 2 | 4K | 4T | upweighted code/math/reasoning |
| Midtrain | 32K | 1.2T | RoPE base 1M, long-CoT |
| SFT | 131K | 660B | RoPE base 5M |

Optimizer: **Muon** with AdamW-RMS matching during pretraining/midtraining. Hardware: **1,024 MI300X (128 nodes × 8 GPUs)**, Pensando Pollara 400 interconnect, IBM Cloud. MI300X's **192 GB HBM** is credited with "avoiding costly expert or tensor sharding," and AMD-optimized distributed I/O is claimed to give **>10× faster model save times**. Post-training is a **4-stage RL cascade**: reasoning warmup → adaptive RLVE-Gym difficulty curriculum → large-scale math/code RL with test-time-compute traces → behavioral RL for chat/instruction following.

### 5. Markovian RSA (test-time compute)

A bounded-memory aggregation scheme: run `N=16` parallel rollouts (budget `β=40K` tokens each), keep only the last `τ=4K` tokens ("tails"); over `T=2` aggregation rounds, sample `C=4` tails, concatenate, and regenerate. Because "aggregation prefill depends only on `C` carried-forward tails of length `τ`, not the full reasoning history," reasoning length is effectively unbounded at **constant memory**. The report cautions this is **co-designed with post-training** — applying Markovian RSA to models not trained for it yields "substantially smaller" uplift.

## Evidence & Benchmarks

**Single-rollout, in-class (Table VII):**

| Benchmark | ZAYA1-8B (0.7B act) | Qwen3-4B-Thinking | Qwen3.5-4B | Gemma-4-E4B |
|---|---|---|---|---|
| AIME'26 | **89.1** | 79.0 | 84.5 | 50.3 |
| HMMT'26 | **71.6** | 53.6 | 63.6 | 32.1 |
| IMO-AnswerBench | **59.3** | 51.6 | 48.7 | 27.3 |
| LiveCodeBench-v6 | **64.8** | 54.9 | 55.8 | 54.2 |
| GPQA-Diamond | 71.0 | 66.1 | **76.2** | 57.4 |
| MMLU-Pro | 74.2 | 74.3 | **79.7** | 70.2 |

**Scaling comparison (Table VIII):**

| Model | Active | Total | AIME'26 | HMMT'26 | LCB-v6 |
|---|---|---|---|---|---|
| **ZAYA1-8B** | 0.7B | 8B | 89.1 | 71.6 | 64.8 |
| Nemotron-3-Nano-30B-A3B | 3B | 30B | 90.1 | 75.5 | 64.6 |
| Qwen3-Next-80B-A3B-Think | 3B | 80B | 90.2 | 79.3 | 67.8 |
| Intellect-3 | 12B | 106B | 86.3 | 72.3 | 66.8 |

With **Markovian RSA**: AIME'25 91.9, HMMT'25 89.6 (reported to exceed Claude 4.5 Sonnet 88.3 and GPT-5-High on HMMT'25); an "extra-high compute" config (~5.5M tokens/problem) reportedly surpasses DeepSeek-V3.2 on an APEX math shortlist.

**Post-training delta (Table IX):** AIME'26 +20.8 (68.3→89.1), HMMT'26 +32.4 (39.2→71.6), LCB-v6 +10.0 — i.e., much of the headline capability comes from the RL cascade, not the base model.

**Ablations actually run:** parameter-matched study showing the router is a higher-marginal-value place to spend parameters than experts/attention; expert-redundancy check (first-projection input overlap 1.45× random baseline vs Qwen3-30B's 1.48×) arguing no pathological collapse.

**What is contested / weak:**
- **No isolated component ablation** of CCA vs MLA/GQA, or of the PID router vs DeepSeek loss-free balancing, on the *final* model — efficiency/quality claims for each are largely asserted, not separately measured here.
- **No per-stage RL attribution** (only aggregate cascade gain), so the contribution of each RL stage is opaque.
- **No controlled optimizer ablation** (Muon vs momentum variants explicitly not run).
- **FLOP-utilization parity with NVIDIA** is reported qualitatively; AMD's own note says findings derive from "a Zyphra technical report" rather than independent verification. No public MFU number appears in the report body.
- **Trade-offs:** ZAYA1 trails on GPQA-Diamond and MMLU-Pro vs Qwen3.5-4B, and the report concedes **agentic/tool-use benchmarks (BFCL-v4, τ²) lag** models with tool-focused post-training.
- **Data opacity:** individual source datasets are withheld, limiting reproducibility and contamination assessment (relevant given AIME/HMMT'25/'26 timing).

## Maturity Assessment

- **Weights & license:** production-friendly — Apache-2.0, on Hugging Face, with a hosted endpoint. The base and reasoning checkpoints are both available.
- **Reproducibility:** **partial.** Architecture is described in enough detail to re-implement CCA, the router, and residual scaling in principle, but exact CCA convolution geometry is in an appendix, training data is undisclosed, and the AMD-specific kernels/I-O stack are proprietary. Re-pretraining requires ~13T+ tokens and a 1,024-GPU class cluster — out of reach for most.
- **Hardware dependency:** the systems story is AMD/ROCm-specific; the *model* itself is portable (standard transformer + MoE), so inference does not require AMD.
- **Inference cost:** ~760M active params + 8× KV compression make it cheap and memory-light to serve, especially at long context — its strongest practical selling point.
- **Verdict:** the **model and weights are production-usable today**; the **research claims (control-theoretic routing superiority, CCA vs MLA efficiency, NVIDIA-parity utilization) are promising but single-source and under-ablated.** Treat benchmark "beats Claude/GPT-5" lines as best-config, co-designed-TTC results, not steady-state single-shot capability.

## PayPal Fraud/Risk Implications

These are hypotheses for evaluation, not validated deployments.

- **Latency/cost wall for real-time scoring.** Sub-100ms transaction scoring at PayPal volume is dominated by compute and KV-memory cost. A **~760M-active** MoE with **8× KV compression** is directly aimed at this wall: you get many-expert capacity at small-model inference cost, and the compressed KV cache materially lowers memory/bandwidth per request — relevant if entity context (recent events, session history) is fed as long context.
- **Expert specialization as a fraud-typology fabric.** Top-1 routing over specialized experts is a natural fit for hosting distinct fraud archetypes — card-testing, ATO/bot, collusion/merchant-collusion, refund/return abuse, friendly fraud — each as specialized experts, with per-transaction cost staying sub-billion-active. Confident (low-entropy) routing means a transaction is mostly scored by the most relevant expert(s).
- **PID-controlled routing = auditable, drift-resistant utilization.** This is the most fraud-specific draw. Auxiliary-loss/bias-nudge balancing can let an expert silently collapse or saturate under adversarial drift (attackers shifting attack mix). A **momentum-smoothed feedback controller that targets uniform load** gives (a) **stable, monitorable expert utilization** — load entropy becomes a live health metric for model-risk governance — and (b) **faster recovery from utilization perturbations**, which adversarial fraud waves resemble. The controlled variable (per-expert load) is exactly the kind of measurable, governable signal regulators and model-risk teams want for **explainability/auditability**.
- **Long-horizon entity memory.** 131K-context training + CCA's cheap KV make it feasible to condition on **long behavioral/event sequences** (account history, device/IP trails) without exploding memory — useful for sequence modeling of payment-event streams and session-level ATO detection.
- **Markovian RSA for agentic case review.** Constant-memory, unbounded "thinking" with carried-forward tails maps onto **investigative/agentic workflows**: a case-review agent can reason over a long evidence trail while keeping context bounded — though the report's caveat (uplift requires co-designed post-training) means PayPal would need its own RL/SFT on fraud traces to realize the benefit.
- **Caveats for this domain.** (1) Benchmarks are math/code/reasoning, not tabular/graph fraud signals — transfer is unproven; PayPal's signals are tabular + graph + sequence, not natural-language reasoning. (2) The model **lags on agentic/tool-use benchmarks**, the very capability investigative workflows need. (3) Routing *stability* is shown in training, not under deliberate adversarial routing attacks — an open question worth red-teaming (can an attacker craft inputs that force a specific expert or unbalance load?). (4) Class imbalance and calibration for sub-basis-point fraud rates are unaddressed by any cited result.

## Sources

- ZAYA1-8B Technical Report (arXiv:2605.05365v1): https://arxiv.org/html/2605.05365v1
- Zyphra launch post — "ZAYA1-8B: Frontier intelligence density, trained on AMD": https://www.zyphra.com/post/zaya1-8b
- AMD/IBM systems claims (StockTitan): https://www.stocktitan.net/news/AMD/amd-powers-frontier-ai-training-for-hgwyvtxsids6.html
- MarkTechPost coverage (2026-05-06): https://www.marktechpost.com/2026/05/06/zyphra-releases-zaya1-8b-a-reasoning-moe-trained-on-amd-hardware-that-punches-far-above-its-weight-class/
- VentureBeat coverage: https://venturebeat.com/technology/meet-zaya1-8b-a-super-efficient-open-reasoning-model-trained-on-amd-instinct-mi300-gpus
- HPCwire/AIwire coverage: https://www.hpcwire.com/aiwire/2026/05/07/zyphra-releases-zaya1-8b-reasoning-model/
- PR Newswire / Morningstar press release: https://www.morningstar.com/news/pr-newswire/20260506la53238/zyphra-releases-zaya1-8b-a-reasoning-model-trained-on-amd-and-optimized-for-maximum-intelligence-density-per-parameter
- Let's Data Science explainer: https://letsdatascience.com/blog/zaya1-8b-amd-mi300x-claude-sonnet-math
- BuildFastWithAI explainer: https://www.buildfastwithai.com/blogs/zaya1-8b-reasoning-model-2026
- DataNorth coverage: https://datanorth.ai/news/zyphra-releases-zaya1-8b
