# DeepSeek-V4: Hybrid Compressed Sparse Attention (CSA + HCA + DSA) for Million-Token Context

**Research window:** April 2026 – June 2026 (report date: 2026-06-03)
**Author:** Senior LLM Researcher, Foundation-Science / PayPal Fraud & Risk relevance review

## Executive Summary

On April 24, 2026, DeepSeek-AI released **DeepSeek-V4** under an MIT open-weights license: a two-member Mixture-of-Experts family — **V4-Pro (1.6T total / 49B active)** and **V4-Flash (284B total / 13B active)** — built specifically to make a **1M-token native context** economically serviceable rather than merely advertisable. The central contribution is a **layer-interleaved hybrid attention stack**: **Compressed Sparse Attention (CSA)** that pools roughly every 4 tokens into one data-dependent KV entry and then applies a **learned Lightning Indexer** to select top-k (≈1024) compressed blocks per query; **Heavily Compressed Attention (HCA)** that pools up to 128 tokens into a single global-summary entry and attends densely over the (now short) compressed sequence; and a **sliding-window branch** for local fidelity — all stored in **mixed FP4/FP8/BF16** precision. At 1M context, V4-Pro is reported at **~27% of V3.2's per-token inference FLOPs and ~10% of its KV cache** (V4-Flash: ~10% FLOPs / ~7% KV), with KV cache around **~2% of standard bf16 GQA**. The model posts strong agentic/coding numbers (SWE-Verified 80.6, Codeforces 3206) but its headline long-context retrieval (MRCR 8-needle ~0.59 at 1M; 83.5 on the 1M MRCR variant) **trails Claude Opus 4.6**, and independent testers report retrieval **degrading well inside the advertised window** (below ~520K on real codebases). The architecture is a genuine attention-system redesign and is open-weight, but ablations are thin, serving throughput is currently hardware-constrained (Ascend 950 dependency), and the efficiency-vs-fidelity trade-off is real and unresolved.

---

## What's New in the Window

| Item | Date | Lab | Notes |
|------|------|-----|-------|
| **DeepSeek-V4 Preview / open-weights release** | **2026-04-24** | DeepSeek-AI | V4-Pro and V4-Flash (instruct + base), MIT license, weights on Hugging Face. ([api-docs.deepseek.com](https://api-docs.deepseek.com/news/news260424)) |
| **DeepSeek-V4 Technical Report** — *"Towards Highly Efficient Million-Token Context Intelligence"* | 2026-04-24 | DeepSeek-AI | `DeepSeek_V4.pdf` shipped in the HF repo (no arXiv ID observed in-window). ([HF repo](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/blob/main/DeepSeek_V4.pdf)) |
| **DeepSeek-V4 model card (transparency)** | 2026-04-27 | DeepSeek-AI | Official model card PDF. ([fe-static.deepseek.com](https://fe-static.deepseek.com/chat/transparency/deepseek-V4-model-card-EN.pdf)) |
| **HF launch blog** — *"a million-token context that agents can actually use"* | 2026-04-24 | Hugging Face / DeepSeek | Most detailed public architecture walkthrough (layer interleaving, FP precision, agent tooling). ([huggingface.co/blog](https://huggingface.co/blog/deepseekv4)) |

**Released artifacts:** `deepseek-ai/DeepSeek-V4-Pro`, `DeepSeek-V4-Flash`, plus `-Base` variants. Checkpoints ship with **FP4 MoE experts + FP8 other weights**. Three inference modes: Non-Think, Think-High, and **Think-Max (requires ≥384K context window)** — implying a **384K max output/reasoning budget** within the 1M window.

**Naming note (disambiguation):** "DSA" here is **DeepSeek Sparse Attention** (the learned-indexer top-k mechanism inherited and extended from V3.2), *not* a generic acronym. The V4 novelty is wrapping DSA-style sparse selection around **compressed** KV blocks (CSA) and adding a parallel **heavy-compression dense** path (HCA).

---

## Technical Deep-Dive

### The problem being attacked
A standard transformer KV cache grows linearly with sequence length. Independent analysis pegs a large dense model (≈128 heads, ≈96 layers, FP16) at ~6.3 MB/token, making 1M-token contexts prohibitive ([runyard.dev](https://www.runyard.dev/blog/deepseek-v4-attention-architecture-explained)). V3.2 already used DeepSeek Sparse Attention (per-token learned top-k selection) to cut compute; V4 attacks the **cache size itself** by compressing *what gets stored* before selecting *what gets read*.

### 1. Compressed Sparse Attention (CSA) — the workhorse
- **Compressor:** a learned token-level compressor collapses every **m ≈ 4 tokens → 1 KV entry** using **softmax-gated pooling with a learned positional bias** (not naive mean-pooling), reportedly with **overlapping windows** to avoid sharp information loss at group boundaries ([runyard.dev](https://www.runyard.dev/blog/deepseek-v4-attention-architecture-explained), [HF blog](https://huggingface.co/blog/deepseekv4)).
- **Lightning Indexer:** a fast, low-precision multi-head dot-product scorer (described as **FP4 dot product with ReLU scoring**) that ranks the compressed blocks and selects the **top-k ≈ 1024** per query. Because it operates over 4×-compressed blocks, the effective search space (and thus indexer cost) is reduced ~4× relative to per-token DSA. One independent review reports the indexer path quantizes **FP32 → BF16 for ~2× speedup at 99.7% top-k recall** ([artgor/Medium](https://artgor.medium.com/deepseek-v4-review-why-million-token-context-needs-efficient-attention-not-just-larger-windows-6dc8e74a00b1)).
- **Sliding-window branch:** preserves the most recent `n_win` uncompressed tokens for local dependency fidelity.
- **Storage:** FP8 for most KV entries, **BF16 reserved for RoPE dimensions**.

CSA = (compress 4×) → (sparse top-k select compressed blocks) → (attend) + (local sliding window). It is DSA applied to a compressed substrate.

### 2. Heavily Compressed Attention (HCA) — global memory
- **Heavy compressor:** **m′ ≈ 128 tokens → 1 entry** (m′ ≫ m).
- **Dense attention, no selection:** because the compressed sequence is now ~128× shorter, queries attend **densely over all compressed blocks** — implemented as **MQA (multi-query attention)** over the compressed representations. No indexer needed.
- Same FP8/BF16(RoPE) storage and same sliding-window local branch.

HCA provides a cheap, always-on **global summary**; CSA provides **selective high-resolution recall**. The two are complementary tiers of an explicit **tiered memory system**.

### 3. Layer interleaving (V4-Pro, ~61 layers)
- Layers 0–1: **HCA only**
- Layers 2–60: **alternating CSA ↔ HCA**
- MTP (multi-token-prediction) block: **sliding-window only**

Rationale per the HF blog: different layers benefit from different attention regimes; forcing one mechanism stack-wide wastes capacity.

### 4. Supporting architecture
- **mHC (Manifold-Constrained Hyper-Connections):** replaces standard residual connections; constrains the residual-mixing matrices to the **Birkhoff polytope (doubly-stochastic matrices)** via the **Sinkhorn-Knopp algorithm**, improving signal-propagation stability while preserving expressivity — credited with enabling stable training at 1.6T params ([framia.pro](https://framia.pro/page/en-US/news/deepseek-v4-paper), [introl.com](https://introl.com/blog/deepseek-v4-mhc-efficiency-breakthrough-february-2026)).
- **Muon optimizer:** Newton-Schulz iterations approximately orthogonalize the gradient-update matrix before the weight step; reported faster convergence / better stability vs AdamW at scale ([framia.pro](https://framia.pro/page/en-US/news/deepseek-v4-paper)).
- **DeepSeekMoE FFN:** sparse expert activation (49B/1.6T Pro; 13B/284B Flash).
- **Agent tooling:** XML-based tool-call schema with a dedicated `|DSML|` token and `string="true|false"` parameter typing to reduce escaping/parse failures; interleaved `<think>` reasoning preserved across tool calls; **DSec** Rust RL-training sandbox (function calls / containers / Firecracker microVMs / QEMU VMs).

### What changed vs prior art (V3.2)
V3.2 = full-resolution KV + per-token DSA selection. V4 = **compress-then-select (CSA)** plus a **parallel heavy-compression dense path (HCA)**, interleaved per layer, with mixed FP4/FP8 storage. The conceptual leap is decoupling **KV-cache cost from raw sequence length** — the indexer becomes a *learned, query-conditioned retrieval over a compressed lifetime of tokens*.

---

## Evidence & Benchmarks

**Efficiency (vs V3.2, measured at 1M context, FP8-equivalent):**
- V4-Pro: **~27% of single-token inference FLOPs**, **~10% of KV cache** ([HF blog](https://huggingface.co/blog/deepseekv4), [MarkTechPost](https://www.marktechpost.com/2026/04/24/deepseek-ai-releases-deepseek-v4-compressed-sparse-attention-and-heavily-compressed-attention-enable-one-million-token-contexts/)).
- V4-Flash: **~10% FLOPs / ~7% KV cache**.
- KV cache ≈ **~2% of standard 8-head bf16 GQA**.
- Discovery-phase aggregate framing: "~73% FLOP / ~90% KV-cache reduction vs V3.2" is consistent with the above.

**Long-context retrieval:**
- **MRCR 8-needle:** stays **>0.82 through 256K**, holds at **0.59 at 1M** ([HF blog](https://huggingface.co/blog/deepseekv4)).
- **MRCR 1M variant:** **83.5** for V4-Pro vs **92.9** for Claude Opus 4.6 Max; **CorpusQA 62.0 vs 71.7** ([MarkTechPost](https://www.marktechpost.com/2026/04/24/deepseek-ai-releases-deepseek-v4-compressed-sparse-attention-and-heavily-compressed-attention-enable-one-million-token-contexts/)).

**Agentic / coding:**
- **SWE-Verified 80.6** (Opus-4.6-Max 80.8; Gemini-3.1-Pro 80.6).
- **Codeforces 3206** (> GPT-5.4-xHigh 3168).
- **Terminal Bench 2.0 67.9** (GPT-5.4-xHigh 75.1; Gemini-3.1-Pro 68.5).
- **MCPAtlas 73.6** (Opus-4.6-Max 73.8); **Toolathlon 51.8**.

**Training:** both models pre-trained on **>32T tokens** ([search synthesis / framia.pro](https://framia.pro/page/en-US/news/deepseek-v4-paper)). Training **compute/cost and dataset composition are not disclosed.**

**Ablations & limitations (honest read):**
- **No published per-mechanism ablations** isolating CSA vs HCA vs DSA contributions ([chinaresearchcollective](https://chinaresearchcollective.substack.com/p/deepseek-v4-preview-entering-the)).
- **Long-context degrades gradually, not flatly**, toward 1M — the 0.59 8-needle figure is a real cliff vs the 0.82 at 256K.
- **Independent production testing:** retrieval fidelity fell off **below ~520K tokens** on real codebases (tested at 45K/180K/520K), with the steepest drop on cross-file refactoring; testers attribute this to the aggressive 10%-KV trade-off ([aiweekly.co](https://aiweekly.co/alerts/deepseek-v4-context-window-cracks-at-production-scale)).
- **Vendor-controlled harnesses:** several evals use internal frameworks/tasks; some competitor runs failed (busy APIs; GPT-5.4 omitted from long-context) ([artgor/Medium](https://artgor.medium.com/deepseek-v4-review-why-million-token-context-needs-efficient-attention-not-just-larger-windows-6dc8e74a00b1)).
- **Stability tricks under-theorized:** "Anticipatory Routing," "SwiGLU Clamping" lack published grounding (same review).
- **Client/API mismatches:** community bug reports show the official API/clients capping at 128K–200K rather than 1M in practice ([cline #10551](https://github.com/cline/cline/issues/10551), [cherry-studio #14789](https://github.com/CherryHQ/cherry-studio/issues/14789)).

**Contested claims:** efficiency percentages are real *relative to V3.2 at 1M* but not independently reproduced on identical hardware; the "1M usable" claim is contradicted by sub-520K production degradation reports. Treat the headline efficiency as plausible and the "full 1M fidelity" framing as **partially hype**.

---

## Maturity Assessment

- **Open-weight, production-intended — not research-only.** MIT license, base + instruct checkpoints, runnable on Transformers/vLLM/SGLang. This is a deployable artifact, not a paper-only result.
- **Compute/serving:** DeepSeek itself notes Pro throughput is "**currently very limited**" pending batch availability of the **Ascend 950 supernode (H2 2026)**; meaningful price drops are gated on that hardware ([chinaresearchcollective](https://chinaresearchcollective.substack.com/p/deepseek-v4-preview-entering-the)). Self-hosting a 1.6T model (even at 49B active, FP4 experts) is a serious infrastructure commitment; **V4-Flash (284B/13B)** is the realistic on-prem target for latency-sensitive deployments.
- **Reproducibility:** weights + report are public, but **no training compute, no dataset disclosure, no per-mechanism ablations**, and several benchmarks run on internal harnesses. Architecture is reproducible from the report; *training* is not.
- **Stability at scale:** mHC (Birkhoff/Sinkhorn) + Muon are the credibility anchors for stable 1.6T training; they are described but not ablated.
- **Practical maturity verdict:** **early-production / preview.** The attention redesign is sound and the weights are usable today; the long-context guarantees and serving economics are not yet mature, and client-side 1M support is inconsistent.

---

## PayPal Fraud/Risk Implications

The load-bearing property for Fraud & Risk is that V4 **decouples KV-cache cost from sequence length**. That changes what is economically feasible in a sub-100ms scoring path.

1. **Long-horizon entity memory in one forward pass (dormant-then-reactivated ATO).** HCA's 128× global-summary tier plus CSA's selective high-resolution recall mean an entity's *months of raw event history* can be resident in context at ~2% of bf16-GQA cache. The **Lightning Indexer becomes a learned, query-conditioned retrieval over an account lifetime** — exactly the shape needed to surface a long-dormant baseline and contrast it with a sudden reactivation burst, the classic account-takeover signature. This is more expressive than a fixed feature-window because the *query* (current event + risk context) conditions which historical blocks are retrieved.

2. **Latency/cost at scale.** ~27% per-token FLOPs and ~10% KV vs V3.2 at 1M makes it conceivable to score against very long event streams within tight latency budgets — but **caveat:** independent reports of degradation below 520K mean PayPal cannot assume reliable recall across an entire ultra-long history. For sub-100ms real-time scoring, **V4-Flash (13B active)** is the candidate; V4-Pro is more suited to **asynchronous case review / investigative agents** than the synchronous decision path.

3. **Sequence + behavioral modeling.** Payment-event streams are exactly the regime CSA targets: bursty, locally-correlated (sliding window) with long-range dependencies (compressed blocks). The tiered memory maps cleanly onto "recent session behavior" (uncompressed window), "mid-horizon patterns" (CSA), and "lifetime baseline" (HCA).

4. **Graph-structured signals.** V4 is a sequence model, not a GNN. Account/device/IP/merchant graph relationships would have to be **serialized into the token stream** (e.g., linearized neighborhoods or textualized edge lists). The indexer could then retrieve relevant subgraph context per query — viable for *augmenting* graph signals, not replacing a dedicated graph model.

5. **Adversarial robustness — a genuine risk.** The compression-then-select pipeline is an attack surface: a fraudster who can pad an entity's history with benign-looking events may **dilute or evict** the few malicious tokens from the top-k compressed blocks, or exploit the 128× HCA summarization to hide a signal inside an averaged block. The reported fidelity degradation under "adversarial long-context" conditions is directly relevant. Any deployment must **red-team for compression-eviction and summary-poisoning attacks**, and likely retain non-compressed features for high-stakes signals.

6. **Explainability/auditability.** The **Lightning Indexer's top-k selection is an interpretable retrieval trace** — for a regulatory review you can surface *which historical event blocks drove a decision*. This is a meaningful auditability win over opaque dense attention, though block-level (not token-level) granularity and lossy compression complicate exact attribution.

7. **Agentic investigation.** Strong SWE-Verified/tool-use numbers, interleaved cross-tool reasoning, and the `|DSML|` XML tool schema make V4 a credible engine for **agentic case-review workflows** (pulling logs, querying ledgers, summarizing an investigation) over very long evidence contexts — the use case least sensitive to the sub-100ms latency constraint and best matched to V4-Pro.

**Net:** V4's hybrid attention is the most directly relevant frontier development for *long-horizon entity memory* and *agentic investigation* in fraud. The biggest cautions are (a) measured long-context degradation well inside 1M, (b) novel compression-specific adversarial surfaces, and (c) serving economics that currently favor V4-Flash + async use over synchronous V4-Pro scoring.

---

## Sources

- DeepSeek-V4 release announcement — https://api-docs.deepseek.com/news/news260424
- DeepSeek-V4-Pro model repo (incl. `DeepSeek_V4.pdf` technical report) — https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro
- Technical report PDF — https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/blob/main/DeepSeek_V4.pdf
- Official transparency model card PDF — https://fe-static.deepseek.com/chat/transparency/deepseek-V4-model-card-EN.pdf
- Hugging Face launch blog — https://huggingface.co/blog/deepseekv4
- MarkTechPost coverage — https://www.marktechpost.com/2026/04/24/deepseek-ai-releases-deepseek-v4-compressed-sparse-attention-and-heavily-compressed-attention-enable-one-million-token-contexts/
- Runyard architecture explainer (CSA/HCA/KV math) — https://www.runyard.dev/blog/deepseek-v4-attention-architecture-explained
- Andrew Lukyanenko (artgor) independent review — https://artgor.medium.com/deepseek-v4-review-why-million-token-context-needs-efficient-attention-not-just-larger-windows-6dc8e74a00b1
- China Research Collective preview analysis — https://chinaresearchcollective.substack.com/p/deepseek-v4-preview-entering-the
- AI Weekly — production-scale context degradation report — https://aiweekly.co/alerts/deepseek-v4-context-window-cracks-at-production-scale
- Framia technical findings (mHC/Muon/32T tokens) — https://framia.pro/page/en-US/news/deepseek-v4-paper
- Introl blog — mHC efficiency analysis — https://introl.com/blog/deepseek-v4-mhc-efficiency-breakthrough-february-2026
- cline issue #10551 (1M cap to 128K) — https://github.com/cline/cline/issues/10551
- cherry-studio issue #14789 (context length 200K) — https://github.com/CherryHQ/cherry-studio/issues/14789
