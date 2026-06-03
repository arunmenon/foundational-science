# Saguaro: Parallelizing Speculation and Verification (Speculative Speculative Decoding)

**Research window:** April 2026 – June 2026 (report compiled 2026-06-03)

## Executive Summary

Speculative decoding (SD) accelerates LLM inference by letting a small draft model propose tokens that a large target model verifies in a single parallel forward pass. But SD still contains a hidden sequential dependency: each round, the draft model sits idle while verification runs, and verification cannot start until drafting finishes. **Speculative Speculative Decoding (SSD)**, introduced by Tanishq Kumar, Tri Dao, and Avner May (arXiv:2603.03251, submitted 3 March 2026; v3 revised 4 May 2026; accepted as an ICLR 2026 poster), removes this dependency. While verification of the current round runs, the draft model *predicts the likely verification outcomes* and pre-computes speculations for each, caching them. If the actual outcome lands in the predicted set, the next round's speculation is returned immediately, hiding drafting latency entirely behind verification compute. The optimized implementation, **Saguaro**, uses a "geometric fan-out" allocation and a modified draft sampling scheme to maximize cache hits. Reported gains: ~30% average (up to 2x) over optimized SD baselines and up to ~5x over autoregressive decoding, reaching 255.8 tok/s on Llama-3.1-70B at batch size 1. The losslessness guarantee is preserved (output distribution is unchanged; on a cache miss it degrades gracefully to ordinary SD). The principal cost is architectural: Saguaro assumes a *dedicated GPU for the draft model*, and the technique is latency-oriented, with diminishing returns at high batch sizes and throughput-bound serving.

## What's New in the Window

The relevant artifacts that were live or updated during April–June 2026:

- **Speculative Speculative Decoding (SSD) / Saguaro** — arXiv:2603.03251. Authors: Tanishq Kumar, Tri Dao (Princeton / Together AI), Avner May (Together AI). Version history: v1 (3 Mar 2026), v2 (22 Mar 2026), **v3 (4 May 2026)** — the v3 revision falls inside the research window. Accepted as an **ICLR 2026 poster** (OpenReview submission #9487, `aL1Wnml9Ef`). Standalone code at `github.com/tanishqkumar/ssd`.
  - arXiv: https://arxiv.org/abs/2603.03251 ; HTML: https://arxiv.org/html/2603.03251 ; OpenReview: https://openreview.net/forum?id=aL1Wnml9Ef
- **P-EAGLE: Parallel-Drafting EAGLE with Scalable Training** — arXiv:2602.01469 (submitted 1 Feb 2026), the cited companion line of work. P-EAGLE parallelizes *draft-token generation* (turning EAGLE's autoregressive drafter into a parallel multi-token predictor via a learnable shared hidden state), reporting 1.10x–1.36x over autoregressive EAGLE-3 on GPT-OSS 120B/20B and Qwen3-Coder 30B, with a vLLM implementation. This is a *different axis* of parallelism from Saguaro: P-EAGLE makes the drafter itself faster; Saguaro overlaps the entire draft phase with verification. AWS published an applied write-up of P-EAGLE in vLLM. (https://arxiv.org/abs/2602.01469 ; https://aws.amazon.com/blogs/machine-learning/p-eagle-faster-llm-inference-with-parallel-speculative-decoding-in-vllm/)
- **Independent commentary in-window:** an ArXivIQ deep review (https://arxiviq.substack.com/p/speculative-speculative-decoding) and a comparative ML-systems analysis placing Saguaro against **Nightjar** (adaptive-depth SD under variable load, +27% throughput) and **SLEM / universal draft model** (2.8x, any-pair vocabulary, merged into HF Transformers) — https://www.arunbaby.com/ml-system-design/0067-speculative-decoding-saguaro-nightjar-universal-draft/

Treat the secondary-source throughput figure of "255.8 tok/s, 4.7x" as reported by the comparative blog citing the paper; the paper's headline framing is "~30% over SD, up to 5x over AR."

## Technical Deep-Dive

### The dependency SSD attacks

Standard SD per round: (1) draft model autoregressively generates K candidate tokens; (2) target model verifies all K in one forward pass, accepting a prefix of length `k` and sampling one bonus token `t*`. Steps (1) and (2) are strictly serial. The draft model's compute is wasted during verification, and total latency is `T_draft + T_verify` per round even though verification dominates cost.

### Core idea: predict the verification outcome, pre-draft for it

A verification outcome is the pair `v = (k, t*)`: how many speculated tokens were accepted and which bonus token was sampled. SSD's insight is that this outcome space is small and skewed — and largely predictable from the draft distribution. So while verification of round *n* runs, the draft model enumerates the *likely* outcomes `v` and pre-computes the next speculation `S(v)` for each, storing them in a **speculation cache** (a dictionary from outcome → ready-to-use token sequence). When round *n* verification returns its true outcome `v*`:

- **Cache hit** (`v*` was anticipated): the prepared speculation is returned with effectively zero added latency — drafting overhead is fully hidden behind verification.
- **Cache miss**: fall back to synchronous drafting with a backup speculator, i.e. ordinary SD. This is what preserves **losslessness** — the output distribution always matches the target model, and worst-case behavior reduces to standard SD.

### Speedup model (Theorem 7)

The paper formalizes the expected speedup as:

```
speedup = [ p_hit · E_hit + (1 - p_hit) · E_miss ]
          ----------------------------------------------------
          [ p_hit · max(1, T_p) + (1 - p_hit) · (1 + T_b) ]
```

where `p_hit` is cache-hit probability, `E_hit`/`E_miss` are expected accepted tokens per round under hit/miss, and `T_p`/`T_b` are primary/backup speculator latencies relative to the verifier pass. **Corollary 8** states that with identical primary/backup speculators, SSD strictly beats standard SD whenever `p_hit > 0` and verification cost is positive — the overlap is "free" upside, not a gamble against a baseline.

### Geometric fan-out (Theorem 12)

The budget question is: given a fixed compute budget `B = Σ F_k` (number of pre-drafted hypotheses), how many guesses `F_k` should be allocated to each possible accept-length `k`? Empirically, cache-hit rates follow a **power law** over outcomes. Under that assumption the optimal allocation decays geometrically:

```
F_k = F_0 · a_p^( k / (1+r) )      for k < K
F_K = F_0 · a_p^( K / (1+r) ) · (1 - a_p)^( -1/(1+r) )
```

with `a_p` the primary speculator's per-token acceptance rate, `r` the power-law exponent, and `K` the lookahead length. Intuition: short accept-lengths are far more probable, so weight hypotheses toward them rather than spreading uniformly. The paper reports geometric fan-out hits up to ~90% accuracy at predicting the bonus token, and that the advantage of geometric over uniform allocation grows at higher sampling temperatures (where the outcome distribution spreads out).

### Saguaro sampling (Definition 14, Theorem 15)

To make outcomes *more predictable*, Saguaro reshapes the draft distribution by down-weighting the top-`F` draft tokens by a factor `C ∈ [0,1]`:

```
σ_{F,C}(z) ∝  C·exp(z_t)   if t ∈ top_F(z)
             exp(z_t)      otherwise
```

Lowering `C` pushes residual probability mass onto the top tokens, raising cache-hit rate **monotonically as C → 0** — but it also lowers the acceptance rate (the draft is now deliberately "miscalibrated"). The hit-rate vs. acceptance-rate tradeoff is navigated empirically per workload (Figure 5).

### Batch-aware fallback (Theorem 17)

At larger batch sizes, cache misses become more frequent (the joint outcome across a batch is harder to anticipate), and a slow neural backup speculator can stall an entire batch. The optimal policy switches backups by batch size `b`: a slow-but-accurate neural backup for small batches `b < b*`, and a fast cheap backup (n-gram / random tokens) for `b ≥ b*`. The empirical switch point matches the theoretical `b*`.

### What changed vs. prior art

- **vs. standard SD (Leviathan/Chen):** SSD removes the serial `T_draft` term by overlapping it with verification; SD never overlaps the two phases.
- **vs. EAGLE / EAGLE-3:** EAGLE improves the *quality and speed of drafting* (feature-level autoregression, tree drafts) but keeps drafting and verification serial. SSD is orthogonal and the authors explicitly note it "composes naturally with EAGLE and token-tree speculation."
- **vs. P-EAGLE (arXiv:2602.01469):** P-EAGLE parallelizes *within* the draft step (multi-token-per-pass drafting). SSD parallelizes *across* the draft/verify boundary. They are complementary, not competing.
- **vs. Nightjar / SLEM:** Nightjar adapts speculation depth to load via a multi-armed-bandit policy (throughput under variable traffic); SLEM is a universal cross-vocabulary draft model (compatibility). Saguaro is the single-user latency champion of this cohort.

## Evidence & Benchmarks

**Setup (from the paper):** Target Llama-3.1-70B on 4×H100 80GB with tensor parallelism; draft Llama-3.2-1B on a *separate* H100; datasets Alpaca, GSM8k, UltraFeedback, HumanEval; engines SGLang (v0.5.9) and vLLM (v0.16.0); greedy plus temperature variants; lookahead K=10; primary analysis at batch size 1 with batch sweeps for the fallback study.

**Headline results:**
- ~30% average and up to 2x faster than optimized SD baselines; up to ~5x over autoregressive decoding.
- 255.8 tok/s on Llama-3.1-70B (single concurrent request), reported as ~4.7x over AR by the comparative ML-systems analysis citing the paper.
- Pushes the throughput–latency Pareto frontier outward across batch sizes.

**Ablations:**
1. Geometric vs. uniform fan-out (Fig. 4) — geometric wins, especially at high temperature.
2. Saguaro sampling `C` sweep (Fig. 5) — confirms the hit-rate vs. acceptance-rate tradeoff.
3. Backup-speculator choice by batch size (Fig. 6) — neural vs. fast backup crossover matches theory.
4. Draft-compute scaling (Fig. 6 right) — adding draft GPUs projects gains at larger batches, with diminishing returns.
5. Power-law cache-hit scaling confirmed empirically (Fig. 3).

**Limitations and open questions (author-stated and independently noted):**
- **Dedicated draft GPU required.** Saguaro asynchronously drafts during verification, so the draft model lives on separate hardware — additional infrastructure cost vs. collocated SD. This is the single biggest deployment friction.
- **Latency-bound, not throughput-bound.** The authors note SD-family methods are "generally ineffective for throughput-bound workloads"; gains concentrate at low batch / single-user.
- **Diminishing returns** as draft device count grows.
- **Sensitivity to power-law parameter `r`.** Fan-out optimality depends on accurately estimating the per-workload exponent; mis-estimation erodes hit rate.
- **Joint design space with EAGLE/token-trees is unexplored** — composition is asserted, not yet measured.
- **Reproducibility caveat:** the OpenReview page surfaced metadata and the abstract but not the full review threads in our retrieval, so I cannot independently confirm reviewer scores or the specific rebuttal content beyond the "ICLR 2026 poster" acceptance.

**Contested / soft claims:** The "5x over AR" and "255.8 tok/s / 4.7x" figures are best-case, single-request, on a specific 70B/1B pairing and engine versions; they should not be read as portable to arbitrary models or to served multi-tenant traffic. The "~30% over SD" average is the more defensible operating-point number.

## Maturity Assessment

- **Status: research-grade, not production-integrated.** Code exists (`github.com/tanishqkumar/ssd`) as a standalone implementation, but Saguaro has **no first-class integration** in vLLM, SGLang, or TensorRT-LLM as of this window. By contrast, **EAGLE-3 is the production default** across all three engines, and **P-EAGLE already runs in vLLM**. The pragmatic production choice today remains EAGLE-3 / P-EAGLE via vLLM; Saguaro is an "evaluate as needs diverge" option.
- **Compute/data requirements:** No new training data for the core method (it reuses an existing draft/target pair). The real cost is the **extra GPU** for the asynchronous drafter — material in a fleet at scale. Benchmarks assume 4×H100 (target) + 1×H100 (draft).
- **Reproducibility:** Theory is explicit (theorems with stated assumptions), engine and model versions are pinned, code is public. The main reproducibility risk is the power-law `r` estimation and the empirically tuned `C`, both workload-specific.
- **Trajectory:** Strong pedigree (Tri Dao), ICLR acceptance, an active SD-acceleration ecosystem (P-EAGLE, Nightjar, SLEM, EAGLE-3) all updated in early-to-mid 2026. If the EAGLE/token-tree composition pans out and someone lands it in vLLM/SGLang, it could move toward production within a few release cycles — but that has not happened yet.

## PayPal Fraud/Risk Implications

The core property that matters for Fraud & Risk: **Saguaro reduces decode latency without changing model outputs (losslessness).** Any place where an LLM is in a latency budget, this shrinks the wall-clock cost with zero accuracy or auditability change.

- **Tail-latency control during fraud surges (most concrete fit).** Real-time risk scoring runs under sub-100ms SLAs. If any part of adjudication uses an LLM — agentic case triage, narrative generation for ambiguous/high-value transactions, reason-code synthesis — Saguaro's ~30% decode reduction (and best-case overlap of the entire draft phase) directly compresses p99 latency. The operational win: fewer instances where the system breaches its budget and **falls back to weaker rule-based scorers under load**. Because gains are largest at batch size 1 / single-request, the fit is *interactive/per-case adjudication*, not bulk batch scoring of the full transaction firehose.
- **Agentic investigation workflows.** Case-review copilots that read entity history, query graphs, and write findings are decode-heavy and latency-sensitive for analyst experience. Lossless ~1.3x–2x decode speedups make multi-step agent loops materially snappier without retraining or changing investigative conclusions.
- **Explainability/auditability preserved by construction.** Regulatory review requires that the model's output distribution be unchanged. Saguaro is provably lossless — on a cache miss it degrades to ordinary SD — so it is an *infrastructure* optimization that does not enter the model-governance surface. This is a meaningful advantage over accuracy-altering speedups (quantization, distillation) that require re-validation.
- **What it does NOT do.** Saguaro does not improve fraud-detection *accuracy*, does not extend *entity memory*, does not harden *graph/sequence* models, and does not address *adversarial drift*. It is a pure decode-latency play for LLM components. The bulk of PayPal's sub-100ms tabular/graph risk scoring is not LLM autoregressive decode at all, so Saguaro is irrelevant to those hot paths.
- **Cost caveat for a fraud fleet.** The dedicated-draft-GPU requirement is non-trivial at PayPal scale. The economics only work where per-request latency is the binding constraint (interactive adjudication, agent loops), not for throughput-bound batch risk scoring where collocated EAGLE-3 is cheaper.
- **Security flag worth raising (adversarial angle).** Speculative decoding introduces a **timing side channel**: accepted vs. rejected speculations produce measurable latency differences, and prior work (arXiv:2411.01076, "When Speculation Spills Secrets") shows an attacker measuring response latency can infer generated tokens and partially reconstruct prompt/context. In an adversarial fraud setting — where attackers actively probe scoring systems — any SD/SSD-accelerated LLM endpoint that is externally timeable could leak signal about its reasoning or inputs. If Saguaro (or any SD variant) is deployed in a fraud-facing path, the timing-side-channel surface should be part of the threat model, not an afterthought.

**Bottom line for PayPal:** A credible, lossless decode-latency optimization for *LLM-in-the-loop* fraud workflows (agentic case review, narrative/reason-code generation, ambiguous high-value adjudication), most valuable for tail-latency containment during surges. It is not a fix for the core real-time risk-scoring stack, it carries an extra-GPU cost, it is not yet production-integrated (prefer EAGLE-3/P-EAGLE in vLLM today), and it inherits the SD timing-side-channel risk that warrants security review in adversarial deployments.

## Sources

- Speculative Speculative Decoding (Saguaro), arXiv:2603.03251 — https://arxiv.org/abs/2603.03251
- HTML full text — https://arxiv.org/html/2603.03251 (and https://arxiv.org/html/2603.03251v1)
- PDF — https://arxiv.org/pdf/2603.03251
- OpenReview (ICLR 2026 poster, #9487) — https://openreview.net/forum?id=aL1Wnml9Ef ; https://openreview.net/pdf?id=aL1Wnml9Ef
- HuggingFace paper page — https://huggingface.co/papers/2603.03251
- alphaXiv — https://www.alphaxiv.org/abs/2603.03251
- ArXivIQ independent review — https://arxiviq.substack.com/p/speculative-speculative-decoding
- Arun Baby, "Speculative decoding in 2026: Saguaro, Nightjar, and the universal draft model" — https://www.arunbaby.com/ml-system-design/0067-speculative-decoding-saguaro-nightjar-universal-draft/
- P-EAGLE, arXiv:2602.01469 — https://arxiv.org/abs/2602.01469 ; https://arxiv.org/html/2602.01469v1
- AWS ML Blog, P-EAGLE in vLLM — https://aws.amazon.com/blogs/machine-learning/p-eagle-faster-llm-inference-with-parallel-speculative-decoding-in-vllm/
- SGLang speculative decoding docs — https://sgl-project.github.io/advanced_features/speculative_decoding.html
- "When Speculation Spills Secrets: Side Channels via Speculative Decoding in LLMs," arXiv:2411.01076 — https://arxiv.org/pdf/2411.01076
- Red Hat, economics of LLM inference with speculative decoding — https://www.redhat.com/en/blog/solving-economics-llm-inference-speculative-decoding
