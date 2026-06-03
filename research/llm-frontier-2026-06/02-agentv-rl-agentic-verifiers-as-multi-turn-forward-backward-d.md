# AgentV-RL: Agentic Verifiers as Multi-Turn Forward/Backward Deliberation

## Executive Summary

AgentV-RL (arXiv:2604.16004, "AgentV-RL: Scaling Reward Modeling with Agentic Verifier," Apr 17 2026, Fudan / HUST / HKU / ByteDance Seed) reframes reward modeling from a single-pass scalar scorer into an *agentic, multi-turn, tool-augmented verification process*. Two complementary agents deliberate over a candidate solution: a **forward agent** traces premises → conclusion (sufficiency: "does the reasoning actually produce the claimed answer?") and a **backward agent** re-derives conclusion → premises (necessity: "are all problem constraints actually satisfied?"). Both interleave internal reasoning with tool calls (a Python interpreter) under a Plan → Validate → Verdict loop, and their verdicts are aggregated. Critically for deployment, the authors distill this multi-agent process into a *single* small verifier via a synthetic-trajectory data engine plus a two-stage recipe (rejection-sampling SFT then GRPO reinforcement learning). The headline claim: a 4B verifier (built on Qwen3-4B) reaches 79.0% Best-of-128 on MATH500, beating outcome reward model (ORM) baselines — including a 70B ORM — by 25.2 absolute points, with consistent gains under both parallel (Best-of-N) and sequential (iterative-refinement) test-time scaling. The work is open-source (Apache-2.0, built on `verl`), though only code and recipes are released — no pretrained checkpoints — and the verification process is expensive (≈8.3K tokens, 11.3 rounds, ~323s/sample on A100), making it a research-grade reranker rather than a low-latency online scorer today.

---

## What's New in the Window

The research window is April–June 2026. The central artifact and most directly adjacent work:

- **AgentV-RL: Scaling Reward Modeling with Agentic Verifier** — arXiv:[2604.16004](https://arxiv.org/abs/2604.16004), submitted **Apr 17, 2026**, accepted to **ACL 2026**.
  - Authors: Jiazheng Zhang, Ziche Fu, Zhiheng Xi, Wenqing Jing, Mingxu Chai, Wei He, Guoqiang Zhang, Chenghao Fan, Chenxin An, Wenxiang Chen, Zhicheng Liu, Haojie Pan, Dingwei Zhu, Tao Gui, Qi Zhang, Xuanjing Huang.
  - Affiliations (per author overlap with prior Fudan NLP / ByteDance Seed work): Fudan University, Huazhong University of Science and Technology, The University of Hong Kong, and ByteDance Seed.
  - Code: [github.com/JiazhengZhang/AgentV-RL](https://github.com/JiazhengZhang/AgentV-RL) (Apache-2.0, built on `verl`).

What is genuinely new *in this window* versus the late-2025/early-2026 generative-verifier trend:

1. **Bidirectional (forward + backward) agentic verification.** Prior generative/process verifiers (e.g., ThinkPRM, GenPRM — both 2025) verify in one direction by generating a verification chain-of-thought. AgentV-RL adds an explicit *backward necessity* agent that reasons from the answer back to the constraints, then aggregates both verdicts. This is the differentiating mechanism.
2. **Verification cast as a full agentic loop with tools.** Rather than emitting a single long CoT, each agent runs a Thought–Action–Observation loop (Plan → Validate → Verdict) with a code interpreter, averaging ~1.6 tool calls per trajectory. This is closer to "ReAct-style verification" than to GenRM-style next-token scoring.
3. **Distillation of a multi-agent process into one RL-trained small model.** The synthetic data engine + two-stage (SFT → GRPO) recipe collapses the two-agent deliberation into a single 0.6B/1.7B/4B verifier, so deployment does not require running two separate agents.

Concurrent / closely related work appearing in the same window (useful as context, not the subject):

- **Scaling Agentic Verifier for Competitive Coding** — arXiv:[2602.04254](https://arxiv.org/abs/2602.04254) (Feb 2026), an agentic-verifier line specialized to code.
- **Agentic Reward Modeling: Verifying GUI Agent via Online Proactive Interaction** — arXiv:[2602.00575](https://arxiv.org/abs/2602.00575) (Feb 2026), agentic verification in the GUI-agent setting.
- **Verify Before You Commit: Faithful Reasoning in LLM Agents via Self-Auditing (SAVER)** — arXiv:[2604.08401](https://arxiv.org/abs/2604.08401) (Apr 2026), backward/self-audit reasoning for agent faithfulness — directly relevant to the auditability angle.

Direct prior art it builds on (pre-window, for grounding the "what changed" comparison):

- **Process Reward Models That Think (ThinkPRM)** — arXiv:[2504.16828](https://arxiv.org/abs/2504.16828) (Apr 2025).
- **GenPRM: Scaling Test-Time Compute of PRMs via Generative Reasoning** — arXiv:[2504.00891](https://arxiv.org/abs/2504.00891) (2025).
- **Generative Verifiers: Reward Modeling as Next-Token Prediction (GenRM)** — arXiv:[2408.15240](https://arxiv.org/abs/2408.15240) (2024).

---

## Technical Deep-Dive

### Problem framing

The paper's motivating failure modes for existing verifiers: (a) **error propagation / false positives** — a verifier that follows the solution's own (plausible but wrong) chain can be fooled by a seemingly correct trajectory; and (b) **lack of external grounding** — purely parametric verifiers are unreliable on computation- or knowledge-intensive steps. AgentV-RL's two design responses are *bidirectionality* (to break self-confirmation) and *tool use* (to ground numerical/factual checks).

### The two agents

- **Forward agent (sufficiency check).** Runs a **Plan → Validate → Verdict** pipeline. *Plan* decomposes the candidate solution into atomic verifiable sub-steps; *Validate* checks each sub-step over multiple turns, calling a Python interpreter for arithmetic/symbolic checks; *Verdict* emits a binary judgment. It asks: do the premises, executed forward, actually entail the stated conclusion?
- **Backward agent (necessity check).** Reasons from the conclusion back toward the premises, checking that every problem constraint is satisfied by the proposed answer (i.e., the answer is *necessary/consistent* with the problem statement, not merely an internally consistent derivation). This catches solutions that "derive something" cleanly but violate a problem constraint.
- **Aggregation.** Forward and backward verdicts are combined via ensemble logic (paper Appendix C.3) into a final accept/reject + score usable for ranking. The ablation shows forward-only and backward-only are each individually competitive, but the bidirectional combination is strictly best — i.e., the two error modes are partially independent and the agents are *synergistic*, not redundant.

Both agents emit **Thought–Action–Observation** sequences, making tool integration native and the trajectory itself an explicit, inspectable audit trail.

### Synthetic data engine

To create training signal without human step labels, the engine: (1) draws problems from public math RL datasets (**Polaris**, **DeepScaleR-40K**, **AReaL-boba-106k**); (2) samples **k=8** candidate solutions per problem; (3) runs the agentic verifier and **keeps only trajectories whose verdict matches ground-truth correctness** (rejection sampling on verdict correctness); yielding ≈**15K SFT trajectories**. This is the same "filter on verdict correctness" philosophy as ThinkPRM's synthetic-CoT filtering, but applied to multi-turn tool-using trajectories rather than single CoTs.

### Two-stage training

1. **Rejection-sampling SFT.** Next-token-prediction fine-tuning on the ~15K filtered multi-turn verification trajectories — teaches the model the Plan/Validate/Verdict format, tool-call syntax, and bidirectional structure.
2. **Reinforcement learning (GRPO).** Group Relative Policy Optimization on ~**50K** samples. Reward is outcome-level and binary: **r(ℋ) = +1 if the final verdict matches ground-truth correctness, −1 otherwise**, with the standard GRPO importance-sampling ratio and a KL penalty to the SFT reference. So the RL signal optimizes *verdict correctness*, while the SFT stage instills the agentic *process*. The verifier is trained to be a discriminator-by-deliberation: the reward never directly supervises individual steps, only the final accept/reject decision.

### How verdicts are used at inference

- **Parallel TTS (Best-of-N reranking):** generate N candidate solutions from a base solver, run the verifier on each, pick the top-scored. Reported up to N=128.
- **Sequential TTS (iterative refinement):** the verifier's localized critique feeds back to revise the solution over turns; the paper tracks correction rate (fixing wrong→right) and degradation rate (right→wrong).

### What changed vs prior art

| Dimension | GenRM (2024) | ThinkPRM / GenPRM (2025) | **AgentV-RL (2026)** |
|---|---|---|---|
| Output | next-token verify/score | step-wise verification CoT | multi-turn agentic trajectory + verdict |
| Direction | forward (judge the solution) | forward, step-wise | **forward + backward (sufficiency + necessity)** |
| External grounding | none | GenPRM adds code; ThinkPRM none | **native tool/code interpreter in loop** |
| Training signal | NTP on verify+gen | filter ~1% PRM800K labels | **synthetic trajectory filter → SFT → GRPO (verdict reward)** |
| Deployment unit | single model | single model | **multi-agent process distilled into single small model** |

The novel contributions are (1) backward necessity-checking as a first-class verification agent, and (2) the RL stage that optimizes the *aggregated verdict* of a tool-using agentic process inside one small model.

---

## Evidence & Benchmarks

All numbers below are as reported by the authors (arXiv:2604.16004); they have not been independently reproduced as of this writing.

**Parallel scaling (Best-of-N), verifier = Agentic-Verifier-Qwen3-4B:**
- **MATH500: 79.0% at N=128**, reported as **+25.2 absolute points** over ORM baselines (the headline number; comparison includes a 70B ORM).
- GSM8K: 93.3% (N=128).
- Gaokao2023: 57.4%.
- AIME24: 53.3%.

**ORM baselines compared against** (per the paper): GRM-Gemma-2B, Skywork-V2-Llama-8B, InternLM2-20B-RM, INF-ORM-Llama3.1-70B, Starling-RM-34B. The "beats a 70B ORM with a 4B verifier" claim refers to INF-ORM-Llama3.1-70B; the 4B agentic verifier wins despite ~17x fewer parameters because it spends *test-time* compute on deliberation rather than parameters on a single scalar head.

**Sequential scaling (iterative refinement):**
- MATH500 Turn-1: 84.2% accuracy, with a **41.6% correction rate** (wrong→right) and only **0.6% degradation** (right→wrong) — i.e., the verifier-guided refinement rarely breaks already-correct solutions.

**Generalization / OOD (Qwen3-4B verifier vs base Qwen3-4B):**
- LiveCodeBench: 70.86% (vs 57.14% base).
- HotpotQA: 66.00% (vs 40.00% base).
These suggest the agentic verification skill transfers beyond math to code and multi-hop QA.

**Ablations:**
- Bidirectional > forward-only and > backward-only (the two agents are synergistic).
- Tool use adds incremental gains *on top of* agentic reasoning.
- SFT+RL > SFT-only > train-free prompting — both stages contribute.
- Model-size scaling 0.6B → 1.7B → 4B is monotonic (e.g., +5.2 points on Gaokao2023 across the range).
- Inference-time scaling: sampling multiple verification trajectories per candidate further improves accuracy.

**Reported compute cost (A100, batch 128):**
- Forward-only variant: ~4,114 tokens, 5.7 rounds, **159.1s** latency/sample.
- Full bidirectional verifier: ~8,349 tokens, 11.3 rounds, **323.4s** latency/sample.

**Limitations the authors acknowledge:**
- Synthetic verification data may not capture real-world distribution diversity.
- The multi-turn agentic process substantially increases deployment cost (tokens, rounds, latency).
- Performance depends on the **reliability and coverage of external tools** (here, mainly a Python interpreter) — a brittle or absent tool degrades grounding.

**Open / contested questions (my assessment):**
- The 25.2-point headline mixes verifier paradigms (agentic Best-of-N reranker vs single-pass ORM scalar). It is a fair *end-task* comparison but not a controlled "same compute budget" comparison; ThinkPRM-style generative verifiers (also test-time-scaled) are the more apples-to-apples baseline and are not the headline comparison.
- Benchmarks are math-heavy (MATH500, GSM8K, AIME24, Gaokao). LiveCodeBench/HotpotQA generalization is promising but limited; no results on noisy, adversarial, or low-signal domains.
- GRPO with a binary verdict reward optimizes *final-verdict* correctness, not faithfulness of the intermediate trace — the audit trail is more inspectable than a scalar but is not guaranteed to be the *causal* reason for the verdict.

---

## Maturity Assessment

**Research-only, with a usable open recipe.** The repo (Apache-2.0, ~145 commits, built on `verl` + vLLM-style serving) provides Best-of-N (`run_verify_multihead.py`), iterative refinement (`main_refine.py`), and SFT/GRPO training scripts (`train_sft_multiturn.sh`, `train_grpo.sh`), plus the JSONL data format (problem–solution pairs + boolean labels). However, **no pretrained checkpoints are released** — model paths are inputs, so reproducing the headline 4B verifier requires re-running the synthetic-data engine and the two-stage training yourself.

**Compute / data requirements:** modest by frontier standards — base models are Qwen3 0.6B/1.7B/4B; training data is ~15K SFT + ~50K RL samples derived from public math datasets via rejection sampling. This is *trainable on a single multi-GPU node*, which is a genuine advantage for adoption. The expensive part is **inference**: full bidirectional verification is ~8K tokens and ~5 minutes per candidate on an A100, and Best-of-128 multiplies that by candidate count.

**Reproducibility:** medium. The pipeline, datasets, and training scripts are public and the framework (`verl`) is mainstream, so the recipe is reproducible in principle; but absent released weights and absent independent third-party reproductions in the April–June 2026 window, the headline numbers should be treated as author-reported. The dependence on a code-interpreter tool also makes results sensitive to the execution environment.

**Bottom line:** a credible, well-engineered research contribution with a clean open recipe; not production-ready as a low-latency scorer. Its realistic near-term use is offline/asynchronous reranking and high-stakes review, not inline scoring.

---

## PayPal Fraud/Risk Implications

The match is strong on **explainability/auditability and agentic case review**, weaker on **inline latency**. Concrete mappings:

1. **Fraud case-review copilot as a backward agent (highest fit).** Given an existing verdict (decline, hold, SAR filed, account suspension), the backward agent re-derives *whether the evidence necessitates that verdict*: does the device-graph linkage, velocity pattern, KYC/identity signal, and merchant history actually entail "fraud" rather than "legit"? The Plan→Validate→Verdict trace becomes an **auditable premise-to-conclusion record** for regulators reviewing declines/SARs — directly answering the banking-AI requirement that "every AI-assisted decision in fraud has a verifiable chain of authority / decision token recording policy, inputs, and rationale." The 0.6% right→wrong degradation rate is exactly the property a review layer wants: it rarely overturns correct decisions while catching errors.

2. **Bidirectional cross-check to suppress false positives/negatives.** Forward (sufficiency: "do the flagged signals add up to fraud?") + backward (necessity: "is every fraud criterion actually met, or did the model latch onto a spurious correlate?") is a natural defense against the *self-confirmation* failure mode that plagues single-pass risk explanations. Given PayPal's extreme class imbalance and the cost asymmetry of false declines, an independent backward necessity-check on borderline cases could reduce good-customer friction.

3. **Tool calls = real-time evidence lookups.** Where the paper calls a Python interpreter, a fraud verifier would call **deterministic risk tools**: graph queries (account/device/IP/merchant neighborhood), velocity aggregations, KYC/document checks, sanctions/list lookups, and rule-engine evaluations. This grounds the verdict in *current* ledger/graph state rather than parametric memory — important against adversarial drift, since the tools reflect live data.

4. **Graph + sequence signals.** The forward agent's atomic-step decomposition maps onto checking each evidentiary link in a fraud ring (device → account → IP → funding instrument), and the multi-turn loop fits sequence/behavioral evidence (session event streams). Entity memory across sessions can be surfaced as tool observations rather than baked into weights.

5. **Adversarial robustness.** Bidirectional verification raises the bar for an attacker: a fraudulent pattern crafted to look legit to a forward scorer must *also* survive backward necessity-checking against constraints — two partially independent failure surfaces. The RL verdict-reward also makes the verifier a discriminator hardened on hard negatives (the k=8 rejection-sampling style mirrors mining hard fraud/legit pairs).

**Hard constraints / honest caveats for PayPal:**
- **Latency is disqualifying for the sub-100ms inline scoring path.** At ~8K tokens / ~5 min per candidate, AgentV-RL cannot sit in the real-time authorization decision. Its place is the **asynchronous tier**: case review, post-decision audit, SAR justification, batch reranking of borderline alerts, and analyst copilot — not the inline risk model.
- **Distill, then deploy selectively.** The paper's own thesis (collapse the multi-agent process into one small model) suggests the realistic PayPal pattern: distill a small verifier for cheap forward sufficiency checks online, and reserve the full bidirectional + tool-using agent for the offline high-stakes review queue.
- **Math benchmarks ≠ fraud distributions.** Reported gains are on math/code/QA; fraud is noisier, adversarial, and label-delayed. The synthetic-data engine would need re-grounding on real fraud outcomes (chargebacks, confirmed fraud labels), and the binary verdict reward would need calibration to PayPal's cost-asymmetric objective.
- **Faithfulness vs inspectability.** The trace is far more auditable than an ORM scalar, but GRPO optimizes verdict correctness, not trace faithfulness — for regulatory defensibility, pair it with a faithfulness/self-audit layer (cf. SAVER, arXiv:2604.08401, same window).

**Net:** AgentV-RL is most valuable to PayPal as an **auditable, tool-grounded, bidirectional case-review and post-decision verification layer** that produces regulator-ready premise→conclusion traces and reduces false positives on borderline cases — explicitly *not* as an inline sub-100ms scorer.

---

## Sources

- AgentV-RL: Scaling Reward Modeling with Agentic Verifier — abstract: https://arxiv.org/abs/2604.16004
- AgentV-RL — full HTML (v1): https://arxiv.org/html/2604.16004v1
- AgentV-RL — code repository (Apache-2.0, built on verl): https://github.com/JiazhengZhang/AgentV-RL
- `verl` distributed RL framework (dependency): https://github.com/volcengine/verl
- Process Reward Models That Think (ThinkPRM), arXiv:2504.16828: https://arxiv.org/abs/2504.16828
- GenPRM: Scaling Test-Time Compute of PRMs via Generative Reasoning, arXiv:2504.00891: https://arxiv.org/pdf/2504.00891
- Generative Verifiers: Reward Modeling as Next-Token Prediction (GenRM), arXiv:2408.15240: https://arxiv.org/html/2408.15240
- Scaling Agentic Verifier for Competitive Coding, arXiv:2602.04254: https://arxiv.org/abs/2602.04254
- Agentic Reward Modeling: Verifying GUI Agent via Online Proactive Interaction, arXiv:2602.00575: https://arxiv.org/pdf/2602.00575
- Verify Before You Commit: Faithful Reasoning in LLM Agents via Self-Auditing (SAVER), arXiv:2604.08401: https://arxiv.org/pdf/2604.08401
- Qwen2.5-Math-RM-72B (reward-model baseline context): https://huggingface.co/Qwen/Qwen2.5-Math-RM-72B
- Skywork-Reward-V2-Qwen3-4B (ORM baseline context): https://huggingface.co/Skywork/Skywork-Reward-V2-Qwen3-4B
- Generative AI use cases in banking (auditability / decision-token context): https://www.backbase.com/blog/generative-ai-banking-use-cases
