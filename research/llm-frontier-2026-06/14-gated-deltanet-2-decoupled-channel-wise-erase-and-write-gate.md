# Gated DeltaNet-2: Decoupled Channel-Wise Erase and Write Gates for Delta-Rule Linear Attention

## Executive Summary

Gated DeltaNet-2 (arXiv:2605.22791, submitted May 21, 2026, NVIDIA — Ali Hatamizadeh, Yejin Choi, Jan Kautz) is a concrete architectural refinement of the delta-rule linear-attention line. Its central insight is that prior gated delta-rule models (Gated DeltaNet, ICLR 2025; Kimi Delta Attention / KDA, from Kimi Linear, arXiv:2510.26692) use a *single* scalar gate to control two physically distinct operations: how much old content to **erase** on the key side and how much new content to **write** on the value side. Gated DeltaNet-2 decouples these into an independent channel-wise erase gate `b_t` (key axis) and channel-wise write gate `w_t` (value axis), layered on top of KDA's per-channel decay. The authors derive a chunkwise WY-style parallel training algorithm with the decay absorbed into asymmetric rank-one erase factors plus a gate-aware backward pass, fused in Triton, so training stays hardware-efficient. At 1.3B parameters / 100B FineWeb-Edu tokens, it is reported as the strongest overall recurrent architecture versus Mamba-2, Gated DeltaNet, KDA, and Mamba-3 across language modeling, commonsense reasoning, and retrieval, with the clearest gains on RULER multi-key needle-in-a-haystack retrieval. The work is research-grade, code-released under a non-commercial NVIDIA license, with no public checkpoints and (as of this writing) no independent replication — the latter is the key open risk.

---

## What's New in the Window (April–June 2026)

Gated DeltaNet-2 lands inside a dense April–May 2026 cluster of delta-rule / linear-attention refinements. The relevant in-window and immediately-adjacent releases:

- **Gated DeltaNet-2: Decoupling Erase and Write in Linear Attention** — arXiv:2605.22791, submitted **2026-05-21**, NVIDIA (A. Hatamizadeh, Y. Choi, J. Kautz). Code: `github.com/NVlabs/GatedDeltaNet-2` (released 2026-05-21, NVIDIA Source Code License-NC). The primary subject of this report.
  - Abstract / paper: https://arxiv.org/abs/2605.22791 ; HTML: https://arxiv.org/html/2605.22791v1
- **OSDN: Improving Delta Rule with Provable Online Preconditioning in Linear Attention** — arXiv:2605.13473, **2026-05-13**. A sibling approach that augments the *scalar* delta gate with a diagonal preconditioner updated online via hypergradient feedback (algebraically a per-feature scaling of the write-side key). Reports +32% JRT-style in-context recall over DeltaNet at 340M and a 39% reduction in recall-residual ratio at 1.3B. OSDN and Gated DeltaNet-2 attack the same defect — the scalar step size ignores feature-wise curvature — from different angles (online preconditioner vs. explicit decoupled gates). https://arxiv.org/abs/2605.13473
- **Kaczmarz Linear Attention** — arXiv:2605.08587, May 2026. Another in-window delta-rule-adjacent update rule (Kaczmarz iterative projection view of memory writes).
- **FG²-GDN: Enhancing Long-Context Gated Delta Networks with Doubly Fine-Grained Control** — arXiv:2604.19021, April 2026. Adds doubly fine-grained control to gated delta networks; a near-neighbor in motivation (finer-grained gating for long context).

Adjacent prior art that frames the contribution (just outside the 2-month window but load-bearing):

- **Mamba-3: Improved Sequence Modeling using State Space Principles** — arXiv:2603.15569, ICLR 2026. Trapezoidal discretization, complex-valued state, MIMO formulation. It is the strongest non-delta-rule baseline Gated DeltaNet-2 claims to beat. https://arxiv.org/abs/2603.15569
- **Kimi Linear / KDA** — arXiv:2510.26692, Oct 2025. Introduced channel-wise (diagonal) decay over the gated delta rule; 3:1 KDA-to-global-attention hybrid, up to 75% KV-memory reduction and ~6.3x decoding throughput. The direct parent Gated DeltaNet-2 generalizes. https://arxiv.org/abs/2510.26692
- **Gated Delta Networks: Improving Mamba2 with Delta Rule** — arXiv:2412.06464, ICLR 2025 (S. Yang, J. Kautz, A. Hatamizadeh). Introduced scalar gating + delta rule. The grandparent.

Independent coverage so far is thin and explicitly flags the absence of external replication (e.g., WinBuzzer, 2026-05-25: "Current evidence still comes from NVIDIA's own materials, because no independent benchmark replication is available yet").

---

## Technical Deep-Dive

### The problem: one scalar gate, two jobs

Linear attention replaces softmax attention's unbounded KV cache with a fixed-size recurrent state matrix `S_t` (constant decode memory, linear-time mixing). The delta rule treats each write as one step of online gradient descent on a key→value associative objective: before writing the new value, it *subtracts the current read* of the old state at the incoming key, so it edits rather than blindly accumulates. Gated DeltaNet added an adaptive (scalar) forget gate; KDA refined the forgetting to a per-channel diagonal decay.

The shared limitation Gated DeltaNet-2 targets: in all of these, the active edit's step size is a **single scalar** that simultaneously controls (a) how much of the old associated content to remove (an operation naturally living on the **key** axis — which stored coordinates to clear) and (b) how much of the incoming value to commit (an operation on the **value** axis). Tying these forces a compromise: aggressive overwriting to insert new content also scrambles unrelated associations sharing the state.

### The mechanism: decoupled channel-wise erase and write gates

Gated DeltaNet-2 keeps KDA's channel-wise decay `D_t` (diagonal, per-key-dimension forgetting) but replaces the tied scalar delta gate with two channel-wise vectors:

- **Erase gate `b_t`** (key side): which coordinates of the decayed old read to remove.
- **Write gate `w_t`** (value side): which coordinates of the incoming value to commit.

The reported state recurrence is:

```
S_t = ( I − k_t (b_t ⊙ k_t)^T ) D_t S_{t-1} + k_t (w_t ⊙ v_t)^T
```

where `⊙` is elementwise (channel-wise) product. The erase term `k_t (b_t ⊙ k_t)^T` is an **asymmetric rank-one** projector (the two `k_t` factors are gated differently), which is what lets erase and write strengths differ per channel.

The construction is a strict generalization of its predecessors:
- When `b_t` and `w_t` collapse to the **same scalar**, it recovers **KDA** exactly.
- When the channel-wise decay *also* collapses to a scalar, it recovers **Gated DeltaNet**.
- Removing decay entirely recovers plain **DeltaNet**.

This nesting is a genuine strength: it means the new gates can only add capacity, and the ablations (below) can isolate exactly what each gate buys.

### Making it trainable in parallel: chunkwise WY with absorbed decay

Naive token-by-token recurrence is not GPU-friendly. The authors derive a chunkwise parallel ("WY representation") formulation. The cumulative channel-wise decay is **absorbed into asymmetric erase factors** so the chunk math stays clean:

```
K̄_r = γ_r^{-1} ⊙ k_r          (decay-normalized key)
Ē_r = γ_r ⊙ (b_r ⊙ k_r)        (gated erase factor)
```

A triangular solve `A = (I + T)^{-1}` produces two auxiliaries via a **shared inverse**: `Y` (erase path) and `U` (write path). Four fused Triton kernels handle (1) intra-chunk products, (2) the WY solve, (3) auxiliary construction, and (4) state/output computation.

### What is genuinely harder than scalar-gated variants

The backward pass is the subtle part and is highlighted as a limitation. With scalar gates, the gate can be factored *outside* the dot products in the WY inverse path; with channel-wise erase/write gates it **cannot**. The gradients must accumulate with the gates embedded inside the inverse path (`dA += dU Z^T` and `dA += dY Ē^T`), which is why the implementation needs a bespoke "gate-aware backward" and incurs extra kernel complexity and a small constant throughput gap versus KDA (attributed to the added gate projections).

### Position vs. prior art

| Method | Decay | Active-edit gate | Erase/write coupling |
|---|---|---|---|
| DeltaNet | none | — | n/a |
| Gated DeltaNet (ICLR'25) | scalar | scalar | tied |
| KDA / Kimi Linear (2510.26692) | channel-wise | scalar | tied |
| Mamba-2/3 | selective SSM | additive write | **no explicit erase** |
| OSDN (2605.13473) | scalar | scalar + online diagonal preconditioner | implicit, write-side only |
| **Gated DeltaNet-2 (2605.22791)** | channel-wise | **channel-wise erase `b_t` + write `w_t`** | **decoupled** |

The cleanest conceptual contrast is with Mamba-2/3, which use *additive* writes with no explicit erase operator at all; Gated DeltaNet-2 is on the opposite end — an explicit, fine-grained, decoupled erase/write editor.

---

## Evidence & Benchmarks

All numbers below are NVIDIA-reported, at **1.3B params / 100B FineWeb-Edu tokens**, 16 heads, `d_k = d_v = 128`, peak LR 4e-4, 0.5M-token global batch, 4K seq length (2K for hybrid). Two settings are reported: pure **recurrent** and **hybrid** (recurrent + sliding-window attention).

**Language modeling & commonsense reasoning (Table 2):**
- WikiText ppl: 15.90 (recurrent) / 15.62 (hybrid)
- LAMBADA ppl: 11.41 (recurrent) / 10.43 (hybrid)
- Commonsense average accuracy: 53.11% (recurrent) / 53.97% (hybrid)
- Reported to outperform Mamba-2, Gated DeltaNet, KDA, and Mamba-3 in both settings.

**RULER synthetic retrieval (Table 3):**
- Multi-key MK-NIAH-1 at 4K (recurrent): **37.8%** vs Gated DeltaNet 28.0% and Mamba-3 MIMO 35.6%.
- Single-key S-NIAH at 4K–8K: "strongest where memory editing matters most." Gains hold as context grows. This multi-key advantage is the headline result and the most architecturally meaningful one — it is exactly what decoupled erase/write is theorized to help (preserving multiple concurrent associations while overwriting others).

**Real-world retrieval (Table 4):**
- Average accuracy: 29.88% (recurrent) / **42.28%** (hybrid). Best-in-class on SWDE (23.65%), SQuAD/SQD (36.75%), FDA (19.98%), TriviaQA/TQA (61.37%).
- Note the large recurrent→hybrid jump (29.88 → 42.28): much of the strong real-world retrieval depends on adding sliding-window attention, not the pure recurrent core.

**Ablations (Table 5) — the most informative part:**
- **Channel-wise erase gate alone recovers 90%+ of the gains.**
- **Channel-wise write gate alone recovers ~60%.**
- Expanding the erase range from [0,1] to [0,2] gives **no consistent benefit**.

Interpretation and caveats:
- The ablation reveals the contribution is **asymmetric**: most of the benefit comes from the *erase* (key-side) gate. The "decoupling" framing is real, but the write-side gate is the junior partner. This is honest of the authors but tempers the "two equal gates" narrative.
- Pure-recurrent real-world retrieval (NQ, DROP) gains are explicitly noted as **modest without sliding-window attention**.

**Training efficiency:**
- H100 throughput: 38.0 Kt/s @ 2K, 36.1 Kt/s @ 16K — near-flat scaling vs. Transformer quadratic degradation; "small constant gap" vs. KDA from the added gate projections.

**Limitations stated by the authors:**
- Erase gate dominates; write gate is secondary.
- Gains on some real-world recall tasks are modest without sliding-window attention.
- The gate-aware backward pass adds nontrivial kernel-implementation overhead.

**Open / contested:**
- **No independent replication** as of early June 2026; all evidence is NVIDIA's own (confirmed by independent press, which flags this explicitly).
- Single scale (1.3B) and a single pretraining corpus (FineWeb-Edu). No multi-scale scaling curves, no >1.3B results, no instruction-tuned/downstream-fine-tuned evaluation.
- Overlap with OSDN's target problem means it is unclear, absent head-to-head comparison, whether explicit decoupled gates beat OSDN's online preconditioner; the paper does not benchmark against OSDN (near-simultaneous release).

---

## Maturity Assessment

**Stage: research-grade, not production-ready.**

- **Code:** Released (`NVlabs/GatedDeltaNet-2`) — PyTorch + fused Triton kernels (fast-weight WY chunkwise with gate-aware backward), built on the Flash Linear Attention framework. Includes `pretrain.py`, `cache.py`, `data.py` and a documented FineWeb-Edu training recipe.
- **License:** **NVIDIA Source Code License-NC (non-commercial)** — a hard blocker for direct production use at a commercial entity like PayPal without a separate license. Any internal use would require a clean-room reimplementation of the (published) algorithm or a commercial license negotiation.
- **Checkpoints:** **None released.** Reproduction requires training from scratch (1.3B / 100B tokens — a meaningful but not extreme compute spend, roughly a few thousand H100-hours).
- **Reproducibility:** Recipe and kernels are public, dependencies are mainstream (PyTorch, Triton, flash-linear-attention), config is documented — so reproduction is plausible, but it has not yet been demonstrated by third parties. The bespoke gate-aware backward kernel is the main reproduction-fragility point.
- **Compute/data needs:** Comparable to KDA/Gated DeltaNet at the same scale; small constant throughput overhead. Constant-memory decode is the production-relevant property.

Net: a well-motivated, cleanly-generalizing architecture with released code but unproven outside its lab, no weights, and a non-commercial license. Treat reported numbers as promising-but-unverified.

---

## PayPal Fraud/Risk Implications

The fit is strong conceptually; map each property to a concrete fraud/risk use case, with honest qualifiers.

**1. Bounded per-entity streaming state (latency & cost).**
The core selling point — a *fixed-size recurrent state* with constant-memory, linear-time updates — maps cleanly onto **one bounded state vector per account / device / card**, updated incrementally as each transaction or event streams in. Unlike a softmax/KV-cache transformer whose memory grows with history length, the per-entity state is O(1) regardless of how long an account has existed. For sub-100ms real-time scoring this is the right computational shape: a constant-size state read + rank-one update per event, no replay of the full history. This is the most defensible application property and is independent of the (unverified) accuracy claims.

**2. Decoupled erase/write = overwrite stale benign behavior without scrambling fraud signatures.**
The central mechanism aligns unusually well with fraud entity-memory dynamics. A legitimate user's behavior drifts continuously (new merchants, new devices, changing spend), and that benign context should be *overwritten* (erase, key-side) as it goes stale. But durable fraud-relevant associations (a device fingerprint once linked to a chargeback ring; a counterparty linked to a mule network) should be *preserved* even as surface behavior changes. A single scalar gate forces a tradeoff between adapting to drift and retaining signatures; decoupled channel-wise gates are exactly the tool to "edit benign drift, keep risk associations." **Caveat:** the ablation shows the *erase* gate carries ~90% of the benefit — which, fortunately, is the erase-stale-benign direction that matters most here.

**3. Multi-key retrieval = holding concurrent risk signals simultaneously.**
The headline RULER **multi-key** gains (37.8% vs 28.0% for Gated DeltaNet at 4K) matter because a single entity state must concurrently encode multiple distinct risk dimensions — geo/velocity, counterparty graph context, device reputation, recent dispute history — without one overwriting another. Better multi-key recall in a fixed state is precisely the property needed to keep several risk "needles" addressable at once. This is the most fraud-relevant benchmark result.

**4. Long-horizon entity memory & adversarial drift.**
Adaptive channel-wise forgetting + selective preservation is a plausible hedge against **adversarial concept drift**: fraudsters deliberately mimic benign patterns to age-out of detection windows. A model that can preserve a learned fraud signature per channel while letting benign channels decay resists "behavioral laundering" better than uniform-decay recurrent state. This is speculative — no fraud-domain evaluation exists — but the inductive bias is in the right direction.

**5. Sequence + graph signals.**
PayPal's signals are sequence (event streams) + graph (account/device/IP/merchant edges) + tabular/text. Gated DeltaNet-2 is a sequence backbone; it would slot in as the **per-entity sequence encoder** feeding a graph/GNN layer, not as a graph model itself. Its constant-state decode is attractive for streaming the sequence side cheaply, then materializing embeddings into graph propagation.

**6. Explainability/auditability — a genuine weakness.**
For regulatory review, the channel-wise gates are *more* inspectable than a black-box attention map in principle (per-channel erase/write magnitudes are interpretable as "what was forgotten vs. retained"), but in practice a 128-dim gated recurrent state is not self-explaining and there is no published interpretability tooling. Do not over-claim auditability gains; this would need dedicated explainability work and likely surrogate/attribution models on top.

**Practical adoption posture for PayPal:**
- **License blocks direct use** (NC). Internal use = clean-room reimplementation of the published algorithm (feasible — math and kernels are public) or a commercial license.
- **Validate before betting on it:** no independent replication, single scale, no fraud-domain results. Recommended path is an internal reproduction on a fraud sequence benchmark (per-entity event streams, extreme class imbalance) comparing Gated DeltaNet-2 vs. KDA vs. Gated DeltaNet vs. a transformer baseline on (a) detection AUC/recall at fixed FPR, (b) p99 scoring latency, (c) memory per entity, (d) robustness to injected behavioral drift.
- **Highest-confidence wins** are the *systems* properties (constant-size streaming state, linear decode), which hold regardless of the contested accuracy claims. The *accuracy/robustness* wins are promising but unproven in-domain.

---

## Sources

- Gated DeltaNet-2 (abstract): https://arxiv.org/abs/2605.22791
- Gated DeltaNet-2 (v1): https://arxiv.org/abs/2605.22791v1
- Gated DeltaNet-2 (HTML full text): https://arxiv.org/html/2605.22791v1
- Gated DeltaNet-2 (PDF): https://arxiv.org/pdf/2605.22791
- Official code (NVIDIA): https://github.com/NVlabs/GatedDeltaNet-2
- Independent commentary (ArxivIQ): https://arxiviq.substack.com/p/gated-deltanet-2-decoupling-erase
- Independent press (WinBuzzer, 2026-05-25, flags lack of replication): https://winbuzzer.com/2026/05/25/nvidias-gated-deltanet-2-splits-linear-memory-gates-xcxwbn/
- OSDN (online preconditioning, sibling work): https://arxiv.org/abs/2605.13473
- Kaczmarz Linear Attention: https://arxiv.org/abs/2605.08587
- FG²-GDN (doubly fine-grained gated delta networks): https://arxiv.org/abs/2604.19021
- Kimi Linear / KDA (channel-wise decay parent): https://arxiv.org/abs/2510.26692
- Gated Delta Networks (ICLR 2025 grandparent): https://arxiv.org/abs/2412.06464 ; PDF: https://jankautz.com/publications/GatedDeltaNet_ICLR25.pdf ; code: https://github.com/NVlabs/GatedDeltaNet
- Mamba-3 (ICLR 2026 baseline): https://arxiv.org/abs/2603.15569
- DeltaNet background (Songlin Yang blog): https://sustcsonglin.github.io/blog/2024/deltanet-1/
