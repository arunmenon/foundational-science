# Collapse-Free Multi-Reward RL from Internal Feedback (Label-Free Self-Improvement)

**Research window:** April 2026 – June 2026 (compiled 2026-06-03)

## Executive Summary

Reinforcement Learning from Internal Feedback (RLIF) trains reasoning LLMs with *no* external rewards, gold labels, or verifiers, optimizing intrinsic signals the model produces about its own generations. The seminal method, **Intuitor** (Zhao et al., UC Berkeley, ICLR 2026; arXiv:2505.19590), replaced the verifiable reward in GRPO with **self-certainty** — the average KL divergence between the model's per-token output distribution and a uniform distribution — and matched GRPO on in-domain math while generalizing better out-of-domain. The central problem, sharpened by the **No Free Lunch** analysis (arXiv:2506.17219), is that single-signal intrinsic RL **collapses**: entropy/self-certainty objectives share overlapping gradients that reward *confidence regardless of correctness*, so prolonged training degenerates into confidently-wrong, low-entropy outputs that fall below the base model. The newest entry in the window — **"Two is better than one: A Collapse-free Multi-Reward RLIF Training Framework"** (Joarder et al., arXiv:2605.22620, May 2026) — attacks this by **decomposing** the internal signal into a coarse *answer-level* reward (cluster/majority voting) plus a fine *completion-level* reward (token-wise self-certainty), normalizing them with GDPO, and adding **KL-Cov regularization** to suppress the low-entropy tokens that drive collapse. It reports MATH-500 of 67.6% on Qwen2.5-Math-7B vs 60.0% for Intuitor and 64.4% for GRPO, with sustained rather than degenerating improvement. The result is meaningful but research-stage: evaluation is math/code only, single base-model family, code "to be released," and a competing camp (JURY-RL, CoVerRL) argues that pure internal signals still need a verification gate to avoid the consensus trap.

---

## What's New in the Window

The April–June 2026 window contains a cluster of label-free / internal-feedback RL papers, with one new primary entry and several closely related companions:

| Paper | arXiv | Date | Lab/Authors | One-line contribution |
|---|---|---|---|---|
| **Two is better than one: A Collapse-free Multi-Reward RLIF Training Framework** | [2605.22620](https://arxiv.org/abs/2605.22620) | 21 May 2026 | Joarder, Sikdar, Akash, Bhattarai, Gyawali | Dual internal reward (cluster-vote + self-certainty) + GDPO norm + KL-Cov to prevent RLIF collapse |
| **JURY-RL: Votes Propose, Proofs Dispose for Label-Free RLVR** | [2604.25419](https://arxiv.org/abs/2604.25419) | 28 Apr 2026 | Chen, Fu, Wu, G. Chen, Liu, D. Liu, Liao | Majority vote *proposes* answer; a Lean formal verifier *disposes* reward; ResZero fallback when verification is inconclusive |
| **CoVerRL: Breaking the Consensus Trap in Label-Free Reasoning via Generator-Verifier Co-Evolution** | [2603.17775](https://arxiv.org/abs/2603.17775) | Mar/early-Apr 2026 | (authors not surfaced) | Single model alternates generator/verifier roles; verifier scrutinizes reasoning to break majority-vote diversity collapse; +4.7–5.9% over label-free baselines |

**Antecedents that this window builds on (outside but foundational):**
- **Intuitor / "Learning to Reason without External Rewards"** — [2505.19590](https://arxiv.org/abs/2505.19590), Xuandong Zhao, Zhewei Kang, Aosong Feng, Sergey Levine, Dawn Song (UC Berkeley / sunblaze-ucb), **accepted ICLR 2026**. Code: [github.com/sunblaze-ucb/Intuitor](https://github.com/sunblaze-ucb/Intuitor). Defines RLIF and self-certainty.
- **No Free Lunch: Rethinking Internal Feedback for LLM Reasoning** — [2506.17219](https://arxiv.org/abs/2506.17219) (Jun 2025), Zhang et al. The cautionary analysis showing intrinsic-only RLIF degrades over training and on instruction-tuned models.
- **EVOL-RL / "Evolving Language Models without Labels: Majority Drives Selection, Novelty Promotes Variation"** — [2509.15194](https://arxiv.org/abs/2509.15194). Majority-vote anchor + novelty reward; reports Qwen3-4B-Base AIME25 pass@1 4.6%→16.4%, pass@16 18.5%→37.9% on label-free AIME24.
- **SRT / "Can Large Reasoning Models Self-Train?"** — [2505.21444](https://arxiv.org/abs/2505.21444). Documents the self-reward-hacking → sudden collapse failure mode.

The defining novelty of 2605.22620 within the window is the **explicit, multi-granularity reward decomposition specifically engineered to be collapse-free using purely internal signals** (no external/formal verifier), distinguishing it from the verifier-gated JURY-RL/CoVerRL camp.

---

## Technical Deep-Dive

### Background: self-certainty and why single-signal RLIF collapses

Intuitor's reward is **self-certainty**, the average KL divergence from a uniform distribution to the model's next-token distribution:

```
Self-certainty(o|q) = (1/|o|) Σ_{i=1}^{|o|} KL( U || p_πθ(· | q, o_<i) )
                    = -(1/(|o|·|V|)) Σ_{i=1}^{|o|} Σ_{j=1}^{|V|} log( |V| · p_πθ(j | q, o_<i) )
```

where `U` is uniform over vocabulary `V`. High self-certainty = sharply peaked (confident) token distributions. Intuitor drops this into GRPO in place of the verifiable reward, giving fully unsupervised training (Zhao et al., [2505.19590](https://arxiv.org/abs/2505.19590)).

**The collapse mechanism.** The No Free Lunch paper ([2506.17219](https://arxiv.org/abs/2506.17219)) proves that entropy-minimization and self-certainty objectives share **overlapping gradient directions** — they are partially equivalent because both fundamentally *reward confidence regardless of correctness*. With a *static* (offline) self-certainty annotator, Intuitor itself observed the policy learning to inflate confidence by ~step 100 (appending already-solved sub-problems, inflating length while accuracy drops). The takeaway: a single confidence-style intrinsic reward has a trivial degenerate optimum — be maximally confident on everything — that decouples from task correctness. No Free Lunch's own prescription was to **pair internal with external feedback**; 2605.22620's contribution is to instead get a *second, complementary internal* signal plus regularization.

### The collapse-free multi-reward framework (2605.22620)

Three ingredients:

1. **Answer-level reward — cluster voting.** Sample a group of completions per prompt, cluster by final answer, and reward each completion by the consensus/plurality strength of its cluster (a majority-vote signal). This is a *coarse, correctness-correlated* proxy: it rewards agreement across independent rollouts rather than per-token confidence, so it is harder to game by simply sharpening token distributions. (This is the same family of signal as TTRL / EVOL-RL's majority anchor, but used here as one of two heads.)

2. **Completion-level reward — token-wise self-certainty.** The Intuitor signal above, providing a dense, fine-grained, per-token shaping reward that the coarse cluster vote lacks.

3. **Combination + anti-collapse regularization.**
   - **GDPO-based normalization**: group-wise standardization across trajectories to reduce reward-scale imbalance between the two heads (so the dense self-certainty term does not dominate the sparse vote term).
   - **KL-Cov regularization**: a coverage-targeted KL term that specifically penalizes the *low-entropy token distributions* responsible for disproportionate entropy reduction. Rather than uniformly regularizing entropy (which would blunt learning), it surgically protects exploration on the tokens most prone to collapse, preventing the late-stage entropy crash.

**What changed vs prior art.** Intuitor = single internal reward (self-certainty), prone to collapse. No Free Lunch = single intrinsic objectives are theoretically near-equivalent and degrade. The new framework's thesis ("two is better than one") is that **two internal rewards at *different granularities* are not redundant** — the coarse cluster vote keeps the objective tied to cross-sample consensus (a correctness proxy) while the dense self-certainty provides gradient on every token, and KL-Cov stops the shared confidence-collapse attractor. Unlike JURY-RL/CoVerRL, it uses **no external/formal verifier**, keeping the method fully label-free.

---

## Evidence & Benchmarks

**Setup (2605.22620):** base model **Qwen2.5-Math-7B**; benchmarks MATH-500, GSM8K, AMC, AIME, LiveCodeBench v6, CRUXEval.

**Headline results (reported, ~step 240k):**

| Benchmark | Proposed (dual) | Intuitor | GRPO (supervised RLVR) |
|---|---|---|---|
| MATH-500 | **67.6%** | 60.0% | 64.4% |
| GSM8K | **94.6%** | 92.2% | 93.8% |
| AMC+AIME (combined) | **45.0%** | 35.0% | — |

Notably, the label-free method reportedly *exceeds* supervised GRPO on MATH-500 and GSM8K in these numbers — a claim to treat with caution given it inverts the usual label-free-vs-supervised gap and depends heavily on the Qwen2.5-Math base, the family most sensitive to spurious/internal rewards (see below).

**Ablations (MATH):**
- Single reward 63.8% → dual reward **67.6%** (the core "two is better than one" claim).
- Without KL-Cov 64.2% → with KL-Cov **67.6%** (regularization contributes ~3.4 pts and, per the paper, is what prevents reward collapse and sustains improvement over long training).

**Limitations the authors acknowledge:** training compute cost; evaluation concentrated on mathematics; sensitivity to reward-function design across diverse problem types. Code is "to be released."

**Open questions / contested claims (cross-source):**
- **Base-model confound.** The *Spurious Rewards Paradox* ([2601.11061](https://arxiv.org/abs/2601.11061)) shows Qwen2.5 models gain even from *random/incorrect* rewards via a memorization "Anchor-Adapter" circuit. Since 2605.22620 uses Qwen2.5-Math-7B, some of the gains may reflect Qwen-specific priors rather than a generalizable RLIF mechanism. No cross-family (Llama, OLMo) results were surfaced.
- **No Free Lunch caution.** [2506.17219](https://arxiv.org/abs/2506.17219) found intrinsic-only RLIF gives "little improvement for instruction-tuned models" and degrades over training; the new paper claims to sustain improvement, but the evidence is on a *base* math model, not instruction-tuned, so it does not directly refute the harder No Free Lunch case.
- **Consensus trap.** CoVerRL ([2603.17775](https://arxiv.org/abs/2603.17775)) argues majority-vote signals suffer "diversity collapse" — models become overconfident in *systematic* errors that voting cannot detect. Cluster voting as one of the two heads here may inherit this blind spot; KL-Cov preserves token entropy but does not verify answer correctness.
- **Verifier-gated alternative outperforms?** JURY-RL ([2604.25419](https://arxiv.org/abs/2604.25419)) reports pass@1 "comparable to supervised ground-truth training" with *monotonic* (non-collapsing) curves by gating votes through a Lean proof. Whether a purely-internal dual reward truly matches a verifier-gated method on robustness is unresolved.

---

## Maturity Assessment

**Stage:** Research-only. arXiv preprint (21 May 2026), code not yet released, single base-model family, math/code benchmarks only. No production deployments, no third-party reproductions surfaced in the window.

**Compute/data:** Built on GRPO-style group-relative RL, so it requires the usual on-policy rollout sampling (a *group* of completions per prompt for both cluster voting and GRPO advantage estimation) — multiple-rollout sampling is the dominant cost. No labels, gold solutions, or verifiers needed, which is the headline practicality win: it can run on an unlabeled prompt stream. The Intuitor lineage is implemented on both Open-R1 and VERL ([github.com/sunblaze-ucb/Intuitor](https://github.com/sunblaze-ucb/Intuitor)), so the infra path to reproduce the multi-reward variant exists once code lands.

**Reproducibility risk:** Moderate-to-high until code release. KL-Cov and GDPO normalization details, cluster-voting thresholds, and the 240k-step schedule matter for the collapse-free claim; small reward-scaling choices are exactly what determines whether collapse occurs. The Qwen2.5-Math confound (Spurious Rewards Paradox) means independent validation on Llama/OLMo is needed before trusting the mechanism as general.

**Trajectory:** The window shows a fast-moving, crowded subfield (at least 4 label-free RL papers Apr–May 2026) converging on the same diagnosis — single-signal intrinsic RL collapses — with two competing remedies: **(a) multi-signal internal decomposition + regularization** (2605.22620), and **(b) verification-gated voting** (JURY-RL, CoVerRL). Both are credible; the field has not yet settled which is more robust.

---

## PayPal Fraud/Risk Implications

Fraud ground truth is **delayed, sparse, noisy, and adversarially shifting** — chargebacks resolve weeks later, confirmed-fraud labels are a tiny imbalanced minority, and patterns drift. A collapse-free label-free RL objective is attractive precisely because it could let a risk-*reasoning* model self-improve on the **unlabeled recent-transaction stream between label refreshes**. Concrete, specific mappings:

- **Self-improvement between label refreshes (core use case).** Run the multi-reward objective on recent unlabeled transactions/cases to keep a reasoning model adapting to drift in the weeks before confirmed labels arrive, then periodically re-anchor with the (delayed) verified labels — a natural hybrid that matches No Free Lunch's "pair internal with external" prescription, with the internal signal doing the between-refresh work.

- **Why collapse-freeness is load-bearing under class imbalance.** With ~99%+ legitimate traffic, a naive confidence/self-certainty reward has a trivial degenerate optimum: become maximally confident and **always predict "legit."** That is exactly the entropy/self-certainty collapse 2605.22620 targets. The **cluster-voting head** (consensus across rollouts on a case) plus **KL-Cov** (protecting exploration so the model keeps modeling rare-fraud tokens/decisions) are the specific mechanisms that would resist the always-legit attractor. This is the single most relevant property for fraud.

- **Adversarial drift hardening.** KL-Cov's preservation of token-level entropy keeps the policy from prematurely committing, which is desirable when adversaries continuously probe and shift tactics; an over-confident collapsed model is brittle to novel fraud, whereas a model retaining exploratory capacity can keep flagging anomalous reasoning paths.

- **Sequence/graph signals.** The method is signal-agnostic at the reward level — it rewards consensus and confidence over *completions*. For an agentic risk-reasoning model that ingests transaction sequences, device/IP/merchant graph context, and entity memory, cluster voting over multiple reasoning rollouts on the same case is a plausible label-free reward that rewards stable, reproducible risk verdicts across sampled reasoning chains.

- **Latency caveat (important).** This is a **training-time** technique, not an inference-time one. The multi-rollout sampling required for cluster voting and GRPO advantages is expensive and offline; it does **not** help the sub-100ms real-time scoring path directly. Payoff is a better/continually-adapted reasoning model that is later distilled or serves the async case-review/investigation tier, not the synchronous authorization decision.

- **Explainability/auditability fit.** Because the object being trained is a *reasoning* model producing chains-of-thought, and because the cluster-voting reward favors verdicts reproducible across independent reasoning samples, the resulting model is more amenable to the investigative/agentic case-review workflow (where an analyst needs a defensible rationale) than to opaque real-time scorers. Regulatory review benefits from reasoning traces, though label-free self-training raises its own governance question: a model improving on unlabeled data without ground truth must be monitored for silent drift toward systematic errors (the CoVerRL "consensus trap" risk) — independent verification gates (à la JURY-RL) or periodic labeled re-anchoring would be prudent controls.

**Net assessment for PayPal:** Promising as a *between-label-refresh self-adaptation* layer for an offline/async risk-reasoning or case-investigation model, specifically because its design directly counters the always-predict-majority collapse that imbalanced fraud data induces in naive intrinsic rewards. Not applicable to the real-time sub-100ms path, and should be deployed with a verification/label re-anchoring gate to avoid confidently-wrong consensus on systematic fraud patterns. Maturity (preprint, no code, Qwen-only) means treat as a research bet, not a near-term production component.

---

## Sources

- Two is better than one: A Collapse-free Multi-Reward RLIF Training Framework — https://arxiv.org/abs/2605.22620 ; PDF https://arxiv.org/pdf/2605.22620
- Learning to Reason without External Rewards (Intuitor, ICLR 2026) — https://arxiv.org/abs/2505.19590 ; HTML https://arxiv.org/html/2505.19590v4 ; code https://github.com/sunblaze-ucb/Intuitor ; HF https://huggingface.co/papers/2505.19590
- No Free Lunch: Rethinking Internal Feedback for LLM Reasoning — https://arxiv.org/abs/2506.17219 ; PDF https://arxiv.org/pdf/2506.17219
- JURY-RL: Votes Propose, Proofs Dispose for Label-Free RLVR — https://arxiv.org/abs/2604.25419 ; HTML https://arxiv.org/html/2604.25419 ; OpenReview https://openreview.net/forum?id=tnfvv9Wsw9
- CoVerRL: Breaking the Consensus Trap in Label-Free Reasoning via Generator-Verifier Co-Evolution — https://arxiv.org/abs/2603.17775 ; HTML https://arxiv.org/html/2603.17775
- EVOL-RL: Evolving Language Models without Labels — https://arxiv.org/abs/2509.15194 ; HTML https://arxiv.org/html/2509.15194v1
- SRT: Can Large Reasoning Models Self-Train? — https://arxiv.org/abs/2505.21444 ; site https://self-rewarding-llm-training.github.io/
- Spurious Rewards Paradox: Mechanistically Understanding How RLVR Activates Memorization Shortcuts in LLMs — https://arxiv.org/abs/2601.11061 ; HF https://huggingface.co/papers/2601.11061
- RLIF topic overview — https://www.emergentmind.com/topics/reinforcement-learning-from-internal-feedback-rlif
