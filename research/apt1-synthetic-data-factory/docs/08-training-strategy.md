# Training Strategy — How the Trajectory Factory Feeds an APT-1-Style Fraud-CX Agent

**Date:** 2026-06-04
**Status:** Design + experiment plan (pre-implementation) — for review. *Updated 2026-06-04 across three research passes: objective question (§2A), RL recipe (§5), and consistency (§7, measure via Cover@τ) now evidenced; reward-hacking mitigations are the one remaining open gap.* **Updated 2026-06-06: token math re-baselined to MEASURED footprint and the binding constraint reframed as data-supply — see new §3A (adversarially-verified external scale review, 28/43 findings survived).**
**Grounding:** deep-research (2024-2026 agentic-training literature; 107-agent run, 23/25 claims verified, 2 refuted) + our factory artifacts ([README](../README.md), [contract.md](../spec/contract.md), packs [04](04-ato-domain-pack.md)/[06](06-app-scams-domain-pack.md)/[07](07-commerce-disputes-domain-pack.md)).
**Evidence tags:** `[EVIDENCED]` = multiply-corroborated in the literature · `[SINGLE]` = one primary paper, adjacent domain · `[SYNTHESIS]` = reasoned inference, not directly verified · `[OPEN]` = needs a dedicated follow-up research pass before we commit.

---

## 0. The one-paragraph answer
Start from a **strong open-weights base** (not from-scratch). Run **three stages**: **(1) Agentic mid-training (continual pre-training, CPT)** on a mixed corpus that injects agentic/tool/policy behavior; **(2) capability-decomposed SFT** on our *passing* graded trajectories with **action-token-only loss + masked incorrect steps**; **(3) RL / preference post-training** that turns our **executable grader into a verifiable reward** and exploits the *failing* trajectories as reflection-corrected negatives and preference pairs. The corpus must keep **~15-30% general/replay tokens** throughout to avoid catastrophic forgetting. This is the realistic, evidence-backed way to reproduce APT-1's "agentic pretrained + reliable" behavior at a <$11M-class budget.

**Binding constraint (re-baselined 2026-06-06, see §3A):** the bottleneck is **data supply, not model size or a CPT token target.** Certified gold is **structurally 0** until ATO-P13 is wired, and our **~0.1M unique domain tokens** are ~**1,000-3,000×** below the 100-300M unique pilot base. All trajectory token math is re-baselined to our **measured ~1,243 tokens/trajectory** (not 2,000). The first milestone is **"first 100 certified gold across ≥3 scenarios,"** not 50k.

---

## 1. Why a 3-stage pipeline (not base→SFT) `[EVIDENCED]`
A general base model has no "agentic inductive bias." If you jump straight to SFT, the model must learn the *capability* (multi-turn tool use, policy following) **and** the *alignment* (our specific SOPs) simultaneously — an optimization conflict that caps performance. Inserting an agentic CPT stage **decouples** these and **raises the post-training ceiling**.
- Alibaba **AgentFounder** (arXiv:2509.13310): agentic CPT alone = **+9.0%** on BrowseComp-zh under identical post-training.
- Amazon **Hephaestus** (arXiv:2502.06589, NAACL 2025): CPT adds fundamental agentic capability that "complex prompting or extensive fine-tuning often fails to introduce."
- *Caveat:* the "optimization-conflict" rationale is a motivating hypothesis (no isolating ablation); benchmarks are browsing/deep-research, not fraud-CX → transfer is plausible, not proven for us.

## 2. Base model: continue-train an open base, never from-scratch `[EVIDENCED]`
At the implied **<$11M / ~20-person** scale, every surveyed lab starts from a strong open base (Qwen3-30B-A3B-Base, Llama, etc.). NVIDIA "Reuse, Don't Retrain" (arXiv:2407.07263): a good two-phase CPT curriculum beats naive continued training by ~9% and the base by up to 16%. **From-scratch is not justified at this budget** — it buys nothing the literature can point to here.

| Path | Cost | When justified |
|---|---|---|
| **Continue-train open base** *(recommended)* | $ (the <$11M regime) | Default for us |
| From-scratch pretrain | $$$ (tens of $M) | Only if licensing forbids any base, or a radically non-transformer architecture — not our case |

**Base *size* is an open pilot variable, not a fixed choice (§3A).** An external advisor proposes **7B-8B**; our working assumption is **~30B-class** (Qwen3-30B-A3B-Base). Do **not** hard-commit: run both through identical CPT+SFT+RL on ATO and pick on **measured** `hard_policy_pass`/`pass^8`, not a priori cost. Note a low-latency production deployment is currently a **non-goal**, so the cost argument that would favor 8B is not operative.

## 2A. Can continued training use a NEW objective (or must we pretrain from scratch)? `[EVIDENCED — follow-up 2026-06-04]`
**Yes — you are not locked to next-token prediction by the base, and from-scratch is essentially never *forced* by the objective.** Objective changes from mild to radical are all achievable via *continued training*:
- **Auxiliary objectives graft cleanly, inference unchanged.** A **state/world-model prediction** head (arXiv:2512.03400) and a **next-latent prediction** head (NextLat, arXiv:2511.05963) train *alongside* NTP, leave architecture + inference untouched (aux head discarded at inference), and improve linearly-decodable / causally-steerable state representations **and downstream GRPO gains (most on harder instances)**. **Directly relevant: we have explicit `CaseState`, so a CaseState-prediction head is the natural auxiliary objective for us.**
- **Even radical objective swaps are CPT-not-scratch.** Decoder→bidirectional embedder via **LLM2Vec** (bidirectional attention + masked-NTP + contrastive; arXiv:2404.05961). Autoregressive→**diffusion** LM via continual pre-training at **<200B tokens** (<10% of base budget; arXiv:2410.17891, corroborated by RND1). These bound the *upper* cost of changing the objective family — still continued training.
- **Therefore from-scratch is only forced by an *architecture* change you can't graft** — and even diffusion turned out graftable. Nothing in our goal requires it.

**Caveat `[external validity]`:** the cleanest auxiliary-objective evidence is from **toy / from-scratch** settings (Rubik's-cube state prediction; small LMs), **not** CPT grafted onto a strong open base at agent scale, and none on fraud-CX. Feasibility is proven; the *benefit for our case* must be validated empirically (§9).

## 3. Stage 1 — Agentic mid-training (CPT)
**Objective:** standard next-token prediction (cross-entropy). `[EVIDENCED]` — CPT is NTP; the agentic-ness comes from the *data*, not a new loss.
**Corpus (what to feed):** `[SINGLE→tune]` tool/API documentation **+** function-calling trajectories **+** general/reasoning text. Hephaestus = 103B tokens over 76,537 APIs (docs + trajectories), reported ~**1:1:1 agent/code/text**. AgentFounder = two-stage 200B (agent+reasoning, 32K ctx) then 100B (curated agent, 128K ctx).
**For us:** feed (a) PayPal/tool API specs from our pack **Tool schemas**, (b) policy/SOP documents (the prose half of our **Policy packs**), (c) our generated fraud **trajectories**, (d) general + dialogue + reasoning replay.
**Curriculum:** `[EVIDENCED]` two-phase — *general blend first*, then *domain/agent blend*.
**Plan for the "stability gap":** `[EVIDENCED]` domain accuracy dips during the first few-B tokens before recovering. Mitigate with a **small high-quality fraud subset over ~4-5 epochs** and a mixture **close to base pretraining distribution** (stability-gap paper arXiv:2406.14833: OpenLlama-3B medical 36.2→40.7 with 40% of budget).
**Budget caveat:** `[OPEN]` surveyed runs used 100B-1T tokens — far above a <$11M build. The *ratios* likely transfer; the *absolute token/compute budget* must be rescaled to our model size (≈30B-class) — an open sizing question. **But the real planning quantity is *unique* tokens, not absolute trained tokens — see §3A.**

## 3A. Data-supply reality — measured footprint + the unique-token denominator `[MEASURED 2026-06-06]`
The binding constraint is **not model size or a CPT token target — it is data supply.** Re-baselined against an external scale review (adversarially verified, **28/43 findings survived**) and our **measured** factory output.

**Measured footprint (ATO sim-swapper, 5 candidates):**
- **~1,243 trainable tokens/trajectory** (`model_transcript`, range 1,182-1,421) — **not the 2,000 a planning rule-of-thumb assumes (~60% high).** The 4,792-token full record is dominated by `audit_trace` (~3,263 tok) = grading/provenance metadata, **NOT** training data. Under our action-token-only loss (§4) the gradient-bearing slice is only ~**400 tok/traj**. Budget SFT on ~1,243 (unmasked) / ~400 (masked), **never 2,000**. So 100k traj = **~124M trainable tokens** (not 200M); 1M RL rollouts = ~1.24B (not 2B).
- **0 certified gold — and the ceiling is *structurally* 0 today.** `certified_gold = PASS AND fully_evaluated`, but `ATO-P13` (llm_judge) is in the required manifest and is always skipped → `fully_evaluated` is unconditionally False. **No trajectory can be certified gold, regardless of agent quality, until P13 is wired.** (Behaviorally, gpt-5.4-nano also fails the sole scenario 5/5 on ATO-P03.)
- **~0.1M unique authored domain tokens** (~74k docs + ~22k code), ~entirely LLM-authored — **no real PayPal data**.

**The unique-token denominator (the real planning quantity).** Trained tokens are not free: `tokens_trained ≈ unique_tokens × epochs`, with an empirical **epoch cap ~4** before memorization dominates (Muennighoff arXiv:2305.16264). Consequences:
- A **3B CPT** run over today's ~0.1M corpus = **~31,000 epochs → catastrophic memorization** (impossible). At the 4-epoch cap, 3B *trained* tokens **requires ~750M unique** → we are ~**7,850× short** on unique tokens.
- The advisor's "**100-300M unique domain tokens**" pilot base is therefore THE dominant near-term data-engineering task: a **~1,000-3,000× synthetic re-representation** (EntiGraph-style, arXiv:2409.07431) of a **real seed layer**, enforced by a **dedup pass** (MinHash/SemDedup; report *effective-unique* post-dedup). 100-300M unique → a defensible **~0.4-1.2B *trained*-token pilot** — which is where the "1B CPT pilot" should actually come from.

**Trajectories CANNOT fill the CPT corpus.** They are SFT/RL fuel and only 5-10% of CPT. Even **1M RL rollouts (~1.24B trainable tokens) < a 3B corpus.** CPT needs a SEPARATE diversity-engineered non-trajectory corpus (tool schemas, policy prose, case narratives, general replay) on a real seed.

**Re-scoped targets (replace the advisor counts):**
| Quantity | Advisor (as written) | Re-baselined for us |
|---|---|---|
| tokens / trajectory | 2,000 | **measured ~1,243** (masked ~400) |
| initial SFT (single bucket) | 50k-100k certified | **~3k-10k certified** via blueprint/persona/seed diversity (APIGen-MT ~5k, ToolACE territory); 50k-100k is the **mature all-13-bucket** target |
| first milestone | "100k certified" | **"first 100 certified gold across ≥3 scenarios"** |
| CPT headline | "3B tokens" | **eval-gated ladder anchored on UNIQUE tokens** (100-300M unique → ~0.4-1.2B trained), not an absolute figure |
| base size | 7B-8B | **pilot variable: 8B vs ~30B** (§2; don't hard-commit) |

**Anti-circularity / provenance firewall (mandatory).** With no real data, the corpus is ~entirely model-generated; a nano-generated corpus would bake in nano's ATO-P03 blind spot. Enforce: (a) generate gold with a **stronger/different** model than the eval/distillation target; (b) keep a **held-out eval the generator never saw**; (c) a **tested invariant that training draws ONLY from `model_transcript`** (quarantine `audit_trace` / hidden ground truth); (d) ground the corpus on a **real seed layer** when available (SME-certified SOPs/tools/logs). This operationalizes the provenance/circularity concern ([02](02-ppa-and-taxonomy.md) §4A, [05](05-introspection-and-contract-revision.md)) at the *training-data* boundary.

## 4. Stage 2 — SFT (on PASSING trajectories)
**Decompose, don't dump raw.** `[EVIDENCED]` Agent-FLAN (arXiv:2403.12881): raw ReAct/JSON corpora entangle *format-following* with *reasoning* and shift off the pretraining distribution → OOD/overfitting + hallucination. Fix: split the corpus by capability (reasoning / retrieval / understanding / instruction-following) and **convert ReAct templates → natural multi-turn dialogue** (+3.1% T-Eval, +2.5% HotpotQA; hallucination H-Score 89.1 vs 83.9).
**Loss masking (core).** `[EVIDENCED]`
1. **Action/assistant-token-only loss** — compute loss only on the agent's messages + tool calls; **mask user turns, system, and tool outputs** (else the model learns to fabricate tool results and play the customer). Standard (Agent-FLAN; TRL `assistant_only_loss`; NVIDIA Nemotron).
2. **Mask incorrect steps** — STeP (arXiv:2505.20023): a per-step binary indicator excludes suboptimal thought-action pairs from the loss so the model never internalizes a bad decision. **Our grader's per-step pass/fail is exactly this indicator.**
**Data source:** our **PASSING** graded trajectories (outcome_pass AND hard_policy_pass), formatted per above.
**Initial target (re-baselined, §3A):** ~**3k-10k *certified*** trajectories for the single ATO bucket — **not** 50k-100k — reached through blueprint/persona/seed **diversity, not raw count** (APIGen-MT shipped ~5k and beat larger models on tau-bench). 50k-100k is the *mature, all-13-bucket* target. **Gated on first wiring ATO-P13** (certified-gold is structurally 0 until then, §3A). Track certified-gold **separately** from candidate volume; instrument pass-rate per pack.

## 5. Stage 3 — RL / preference post-training (grader = reward)
`[EVIDENCED — follow-up 2026-06-04]` Our executable checker is a **verifiable reward** (per-trajectory pass/fail + per-step `breaching_step`). Evidenced design, in order:

**(a) Start with a strong outcome-GRPO baseline — but know it's already an implicit PRM.** Outcome-only RLVR/GRPO/PPO is necessary but **too sparse alone** for multi-turn tool agents (poor credit assignment over many turns: SWEET-RL arXiv:2503.15478, turn-level arXiv:2505.11821, Agent-RLVR arXiv:2506.11425). *However*, **"GRPO is secretly a process reward model"** — GRPO with an outcome reward is provably equivalent to a non-trivial Monte-Carlo PRM (arXiv:2509.21154). → **Measure a well-tuned outcome-GRPO (reward = `task_success AND hard_policy_pass`, + `adherence_score` shaping) *before* building bespoke PRMs.**

**(b) Add dense step rewards from our `breaching_step` — two evidenced routes, both fed by the grader:**
- **Privileged-critic (SWEET-RL, arXiv:2503.15478):** an asymmetric critic that sees *training-time-only* info (the answer key / full CaseState) emits step rewards. **+6pp on ColBench** (Llama-3.1-8B matched GPT-4o). **Our grader + CaseState *are* that privileged info.**
- **Implicit PRM (iStar, arXiv:2509.19199):** trains a step-reward model jointly via a *trajectory-level DPO objective* — **no explicit step labels or extra rollouts** — and grafts onto GRPO/RLOO/DAPO. Turns our matched pass/fail pairs into DPO signal *and* free per-step rewards at once.

**(c) Exploit the FAILING half — guidance + re-attempt (Agent-RLVR, arXiv:2506.11425).** Don't merely imitate negatives: give the agent guidance (the `breaching_step` + a corrective hint), have it **re-attempt**, then RLVR-update on the recovered trajectory. **SWE-Bench Verified Pass@1 9.4%→22.4% (+138% rel).** RL-stage analog of SFT's reflection-corrected negatives (STeP, §4).

**(d) DPO from matched pass/fail.** Same-blueprint passing-vs-failing trajectories are ready-made preferred/rejected pairs (run before/alongside GRPO).

**Reward-hacking with executable checkers** `[PARTIAL — still thinly evidenced]` — agents can game the surface form a checker keys on, and *dense rewards can themselves induce hacking* (arXiv:2410.15115). Evidenced/standard mitigations: **pair the exact-match checker with an LLM-judge** (verifiable + judge turn-level rewards, arXiv:2505.11821 — our [judge-calibration.md](../spec/judge-calibration.md) already does this), **KL-penalty to the SFT model**, **checker diversity / held-out (secret) checkers**, RM ensembling. Direct primary evidence for the *executable-checker* case is still thin → keep as a monitored risk (§10) and validate via the §9 reward-hacking probe. *(A 3rd targeted pass (2026-06-04) fetched reward-hacking sources — incl. verifier-gaming/IPT arXiv:2604.15149 — but no GAP-2 claim survived top-25 adversarial verification, so this stays genuinely OPEN; the cross-cutting mitigations above plus our existing IPT-style audit (frontier slate H1 / [04](04-ato-domain-pack.md) policy checkers) are the working defense pending a dedicated GAP-2 pass.)*

## 6. Corpus mix — starting grid for ablation (NOT laws)
`[SINGLE→tune]` Treat these as the **center of an ablation sweep**, re-tuned for fraud-CX:

| Stage | General/replay | Domain (agent+fraud) | Source points |
|---|---|---|---|
| CPT | ~15-30% general (often ~**18%**) | ~70-85% | stability-gap 18/82; Hephaestus ~1:1:1 agent/code/text |
| SFT | ~**68%** general / instruction | ~**32%** domain (~2:1) | data-mixing optimizer (ICML 2025, medical 10M); anti-forgetting SFT fixes domain at 17% |
| Replay | **generic pretraining text** (not task data) | — | GeRe (arXiv:2508.04676): ~1k generic texts → MMLU 50.5 vs 38.3 |

**Two refuted claims (0-3) — act on them:** (a) a small fixed generic-replay set is **not** sufficient to protect *both* general ability *and* prior-task performance → combine replay **with** domain data; (b) knowledge-utilization does **not** transfer from general data alone → **keep synthesizing domain fraud trajectories**, don't assume general data covers it.

## 7. Consistency / "Pass100" `[EVIDENCED on single-turn reasoning; multi-turn transfer UNPROVEN — 3rd pass 2026-06-04]`

**Measure it right — do NOT optimize raw Pass@k.** Pass@k is mathematically degenerate at large k (→1 for any nonzero success probability), so it captures "chance of eventual lucky success," not reliability (arXiv:2510.08325, arXiv:2511.16231). **Define the Pass100 target as `Cover@τ`** = the fraction of cases solved on **at least a τ proportion** of identical runs; use high τ (≈0.8) to filter lucky hits. Keep `pass^k` ([contract.md](../spec/contract.md) §5) only as a diagnostic.

**Training levers that move consistency (single-turn-verified):**
- **Divergence choice — start here.** Mode-seeking **reverse-KL** collapses the policy to one mode (kills diversity); **mass-covering forward-KL / JS** preserves it. **DPH-RL** (arXiv:2509.07430) reports improving Pass@1 *and* Pass@k together (not a tradeoff).
- **Entropy-safe advantage — QAE** (arXiv:2509.22611): two-sided entropy safety; boosts Pass@1 while keeping Pass@k comparable.
- **Unlikeliness reward** (arXiv:2506.02355): counters GRPO's "rank-bias" distribution sharpening by up-weighting rare-but-correct solutions; improves pass@N across a wide N range.
- **Direct pass@k targeting (optional) — PKPO** (arXiv:2505.15201) / **advantage-shaping GRPO_K** (arXiv:2510.23049): a drop-in advantage reweighting on top of GRPO optimizing pass@k for arbitrary k≤n. Use cautiously — prefer optimizing toward **Cover@τ**.

**The sharpening-vs-diversity tradeoff is real but contested.** RLVR (GRPO/DAPO without KL) often raises Pass@1 but degrades Pass@k via entropy collapse — yet **ProRL** (arXiv:2505.24864: long RL + KL control + reference-policy resets) expands reasoning and improves Pass@k even where the base scores zero. Two simplistic framings ("RL only narrows the distribution"; "pass@k-training improves exploration") were **refuted** in verification — don't treat the tradeoff as settled.

**Load-bearing caveat:** *every* recipe here was validated on **single-turn** verifiable reasoning (math/code/Lean), **not** multi-turn tool agents. Open sub-question: how to define the per-trajectory success rate (ρ) these advantage transforms need in our multi-turn setting. Transfer is plausible (we also have a verifiable reward) but unproven → validate via §9 item 9.

## 8. How the factory wires into each stage (the tie-back)
| Factory output | Feeds | Stage |
|---|---|---|
| Tool schemas + Policy prose (packs) | API-doc / policy corpus | CPT |
| Generated trajectories (all) | agent corpus | CPT |
| **Passing** trajectories | gold imitation data (masked) | SFT |
| Per-step `breaching_step` | step-mask indicator + PRM labels | SFT + RL |
| **Failing** trajectories | reflection-corrected negatives | SFT (wrapped) + RL |
| Matched pass/fail per blueprint | DPO preferred/rejected pairs | RL |
| **Grader (checkers)** | verifiable reward function | RL |
| `pass^k` metric | reliability eval | all (eval-gate) |

## 9. Experiment plan (to validate mix + objective before scaling)
0. **Stage 0 — unblock data supply (PREREQUISITE for everything below).** `[NEW 2026-06-06]` (a) wire the **ATO-P13** calibrated llm_judge so `certified_gold` can ever be True; (b) swap gpt-5.4-nano for a **frontier gold-producer** (keep nano as a distillation *target* only); (c) make `Pack.scenario` a **sampler** + add ≥2 more buckets; (d) prove the gate emits **≥1 certified gold**. **Milestone: first 100 certified gold across ≥3 scenarios.** Then run the cheap **base→SFT-only baseline** (item 5) *before* funding any 1B+ CPT pilot.
1. **Mix ablation (CPT):** sweep general:domain ∈ {10:90, 18:82, 30:70}; measure (a) fraud-task accuracy, (b) general-capability retention (MMLU/held-out), (c) the stability-gap depth/recovery. Pick the knee. **Enforce a dedup pass (MinHash/SemDedup) and report `tokens_trained = effective-unique × epochs` (epoch cap ~4); the planning quantity is *unique* tokens, not absolute (§3A).**
2. **Curriculum ablation:** one-phase vs two-phase (general→domain); confirm two-phase wins as reported.
3. **Masking ablation:** full-sequence loss vs action-only vs action-only+incorrect-step-masking; expect (3) best, lowest hallucination (use an Agent-FLAN-style hallucination check on our packs).
4. **Negative-use ablation:** SFT-on-passing-only vs +reflection-corrected-negatives vs +DPO pairs; measure policy-adherence rate and `pass^8`.
5. **CPT-or-not ablation:** base→SFT vs base→CPT→SFT, identical post-training; confirm the ceiling lift transfers to fraud-CX.
6. **Reward-hacking probe:** train RL against the grader, then evaluate on **held-out/secret checkers** + human audit to detect surface-form gaming; test KL-to-SFT magnitudes and exact-match+judge pairing.
7. **RL ablation ladder (Stage 3):** outcome-only GRPO (baseline — already an implicit PRM, so this is the bar) → +DPO from matched pass/fail → +step-level rewards (compare **privileged-critic SWEET-RL** vs **implicit-PRM iStar**, both fed by `breaching_step`) → +**Agent-RLVR guidance-and-re-attempt** on failing trajectories. Measure the *marginal* gain of each over the GRPO baseline (don't assume PRMs help until shown).
8. **Auxiliary-objective ablation (CPT/SFT):** add a **CaseState-prediction head** (and optionally a next-latent head) on/off; confirm inference stays unchanged and measure state-tracking + downstream RL lift (the §2A external-validity check).
9. **Consistency experiment (Pass100):** adopt **Cover@τ** (τ≈0.8) as the reliability target; ablate divergence (reverse-KL vs forward-KL/JS via DPH-RL), entropy-safe advantage (QAE), and unlikeliness reward; track **Cover@τ AND pass@1 AND a diversity proxy** to watch the sharpening-vs-diversity tradeoff. Since all source recipes are single-turn, this doubles as the **multi-turn transfer test** (§10 item 8).
**Primary metrics throughout:** `task_success`, `hard_policy_pass` (policy-adherence rate), `adherence_score`, **`pass^8` (the reliability headline)**, general-capability retention, hallucination rate.

## 10. Open items
0. `[OPEN — now the binding constraint, 2026-06-06]` **Data supply is the unsolved problem.** Certified-gold is structurally **0** (ATO-P13 unwired) and we have ~**0.1M** unique domain tokens vs a 100-300M unique pilot base (~**1,000-3,000×**). This gates every downstream stage; plan is §3A Stage 0 (§9 item 0). Sub-tasks: real seed layer (SME-certified), EntiGraph-style re-representation, dedup enforcement, anti-circularity firewall.
1. ✅ **CLOSED** (follow-up 2026-06-04) — SFT→RL recipe with a verifiable grader: §5 (outcome-GRPO baseline → step-level via SWEET-RL/iStar → Agent-RLVR guidance → DPO).
2. ✅ **CLOSED** (follow-up 2026-06-04) — the objective question: §2A (new/auxiliary objectives are CPT-graftable; from-scratch not forced).
3. ✅ **CLOSED** (3rd pass 2026-06-04) — Consistency / Pass100: measure with `Cover@τ` (not raw Pass@k); train via divergence choice (DPH-RL) / entropy-safe advantage (QAE) / unlikeliness reward / optional PKPO. See §7. *Single-turn-validated; multi-turn transfer is item 8.*
4. `[OPEN — still the one unclosed gap]` **Reward-hacking** mitigations specific to *executable policy checkers* — the 3rd pass fetched sources (incl. verifier-gaming arXiv:2604.15149) but no GAP-2 claim survived verification; needs a dedicated GAP-2-only research pass.
8. `[VALIDATE EMPIRICALLY]` Do the consistency recipes (DPH-RL / QAE / unlikeliness / PKPO) transfer to **multi-turn tool agents**, and how is per-trajectory success-rate (ρ) defined for the advantage transforms in a multi-turn setting?
5. `[VALIDATE EMPIRICALLY]` Does an auxiliary **CaseState-prediction head** help when grafted via CPT onto a *strong* base at scale (proven only in toy/from-scratch settings)?
6. `[VALIDATE EMPIRICALLY]` Marginal benefit of explicit privileged-critic (SWEET-RL) / implicit-PRM (iStar) over a *well-tuned outcome-GRPO* baseline (already an implicit PRM, arXiv:2509.21154).
7. `[REFRAMED 2026-06-06]` Planning quantity is **unique** tokens, not absolute trained tokens: target **100-300M unique** (post-dedup) → ~0.4-1.2B trained at a 4-epoch cap (§3A). The "3B CPT" headline is dropped as **unanchored** (it is also ~10-100× smaller than the agentic-CPT runs §3/§5 survey, e.g. Hephaestus 103B / AgentFounder 300B — further evidence the absolute figure is arbitrary). Commit only to the eval-gated ladder.

## 11. Sources (verified)
**Pass 1 (stages + mix + masking):** AgentFounder arXiv:2509.13310 · Hephaestus arXiv:2502.06589 · Agent-FLAN arXiv:2403.12881 · STeP arXiv:2505.20023 · NVIDIA Reuse-Don't-Retrain arXiv:2407.07263 · Stability-gap arXiv:2406.14833 · GeRe arXiv:2508.04676 · data-mixing optimizer arXiv:2508.11953 · anti-forgetting SFT arXiv:2506.09428 · Mix-CPT arXiv:2407.10804.
**Pass 2 (objectives + RL, 2026-06-04):** state-prediction arXiv:2512.03400 · NextLat arXiv:2511.05963 · FSP arXiv:2510.14751 · LLM2Vec arXiv:2404.05961 · AR→diffusion CPT arXiv:2410.17891 · SWEET-RL arXiv:2503.15478 · turn-level rewards arXiv:2505.11821 · Agent-RLVR arXiv:2506.11425 · iStar arXiv:2509.19199 · GRPO-is-a-PRM arXiv:2509.21154.
**Pass 3 (consistency + reward-hacking, 2026-06-04):** Pass@k-degeneracy / Cover@τ arXiv:2510.08325 · arXiv:2511.16231 · PKPO arXiv:2505.15201 · advantage-shaping GRPO_K arXiv:2510.23049 · unlikeliness reward arXiv:2506.02355 · DPH-RL arXiv:2509.07430 · QAE arXiv:2509.22611 · ProRL arXiv:2505.24864.
**Footprint re-baseline (2026-06-06):** data-constrained scaling / epoch-cap arXiv:2305.16264 · synthetic CPT / EntiGraph arXiv:2409.07431 · DAPT arXiv:2004.10964 · Chinchilla arXiv:2203.15556 · Llama-3 (Meta) · APIGen-MT (agentic SFT scale) · Agent-RLVR arXiv:2506.11425 · *(internal) adversarially-verified external scale review — 28/43 findings survived; measured footprint 5 candidates @ ~1,243 tok/traj, ~0.1M unique authored tokens, 0 certified gold.*
*Refuted across passes:* FSP > NTP+MTP; "first systematic turn-level reward study"; "RLVR only narrows the distribution"; "pass@k-training improves exploration." *Reward-hacking (GAP 2) sources fetched in pass 3 but no claim survived verification → still `[OPEN]`.*
