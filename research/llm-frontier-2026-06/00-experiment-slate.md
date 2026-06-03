# PayPal Fraud & Risk — Frontier-LLM Experiment Slate (June 2026)

**Author:** Principal Applied Scientist, Fraud & Risk
**Source corpus:** 18 frontier-LLM deep-dive reports (DeepSeek-V4, SubQ/SSA, Parallax, GAAMA, Saguaro, HVD, SAECache, GRIFT/IPT, AgeMem, Dynamic Workflows, ZAYA1, Gated DeltaNet-2, Meta-Soft, Multi-Layer Memory, RLIF, Overthinking/Adaptive-TTC, Sleeper Memory Poisoning, AgentV-RL)
**Date:** 2026-06-03

---

## Executive Summary

The frontier in this window splits cleanly into four buckets relevant to Fraud & Risk: (1) **attention/memory architectures** that decouple cost from sequence length, enabling long-horizon entity memory; (2) **inference-efficiency** techniques (speculative decoding, KV-cache eviction, MoE) that lower latency/cost on the LLM-in-the-loop tiers; (3) **agentic memory + investigation** systems that strengthen cross-session entity memory and case review, with a sharp new **adversarial attack surface** (sleeper memory poisoning); and (4) **verification/robustness** methods (isomorphic perturbation testing, gradient fingerprints, bidirectional verifiers, adaptive test-time compute) that map directly onto auditability and adversarial-drift defense.

A consistent honest constraint runs through every report: **none of these belong on the synchronous sub-100ms scoring hot path as-is.** The hot path stays tabular/GNN/sequence-model territory. The frontier wins concentrate in (a) the **asynchronous/investigative tier**, (b) **offline training and audit pipelines**, and (c) **architectural ideas portable into our own owned models** (constant-state streaming encoders, sparse-indexer entity memory).

### Top 3 recommended bets

1. **H1 — Isomorphic Perturbation Testing (IPT) as an adversarial-drift early-warning audit (low effort, high impact).** From report 10. Fraud's graph/sequence signals admit well-defined structure-preserving transforms (permute device/IP/merchant IDs while preserving graph relations). A model that memorized instance-level shortcuts (specific BINs, IPs, device IDs) flips under permutation; a model that learned transferable fraud structure does not. This is a black-box, offline audit that runs on already-scored traffic, needs no model internals, and gives a *causal* early-warning metric for the exact failure mode (device-farming, IP-churn, BIN-rotation) that craters production accuracy when rings rotate. Highest ratio of impact to effort in the entire slate.

2. **H2 — Write-time provenance gating + activation-probe detection on agent-written entity memory (medium effort, high impact).** From reports 03, 16, 11. Sleeper memory poisoning is an imminent, design-level threat to any cross-session entity memory written from untrusted text (dispute narratives, KYC docs, merchant blurbs, support chat). The goal-adjacency effect makes fraud *worse* than the generic case because investigation queries are highly predictable. We must gate memory writes with provenance metadata + per-model activation/document scanners *before* we build entity-memory products that fraudsters can groom. This is a prerequisite control, not a nice-to-have.

3. **H3 — Constant-state recurrent per-entity sequence encoder (Gated DeltaNet-2 / KDA-style) for long-horizon behavioral memory (medium effort, high impact).** From reports 14, 05. A fixed-size recurrent state per account/device/card, updated by a rank-one op per event, is the right computational shape for streaming behavioral memory under tight latency — O(1) memory regardless of account age, with decoupled erase/write gates that overwrite benign drift while preserving durable fraud signatures. The systems properties (constant-memory decode) hold independent of the contested accuracy claims, making this a lower-risk architectural bet than the long-context transformers.

---

## Prioritization Matrix

| ID | Title | Effort | Impact | Tier | Quadrant |
|----|-------|--------|--------|------|----------|
| **H1** | Isomorphic perturbation audit for shortcut/drift | Low | High | Offline audit | **Quick win — do first** |
| **H4** | Adaptive test-time compute cutoff for LLM triage | Low | Medium | Async/triage | Quick win |
| **H8** | Lossless speculative decoding for case-review LLMs | Low | Medium | Async/agentic | Quick win |
| **H9** | Semantic-aware prefix-cache eviction for investigation prompts | Low | Low–Med | Serving infra | Quick win |
| **H2** | Provenance gating + poison detection on entity memory | Medium | High | Async write-path | **Big bet — prioritize** |
| **H3** | Constant-state recurrent per-entity sequence encoder | Medium | High | Near-real-time | **Big bet** |
| **H6** | Concept-mediated graph memory for ring/multi-hop investigation | Medium | High | Async/investigative | Big bet |
| **H7** | Bidirectional verifier for false-positive reduction & SAR audit | Medium | Med–High | Async/audit | Strategic |
| **H10** | Adaptive-budget LLM allocator gated on graph/sequence anomaly | Medium | Medium | Async/triage | Strategic |
| **H12** | Parallel self-verifying subagent swarm for case investigation | Medium–High | Medium | Async/investigative | Strategic |
| **H5** | Sparse-indexer long-context entity memory (DeepSeek-V4-Flash style) | High | High | Async/investigative | **Ambitious bet** |
| **H11** | Collapse-free label-free RL for between-refresh adaptation | High | Medium | Offline training | Ambitious / research |
| **H13** | Learned memory-curation policy credited by sparse fraud outcomes | High | Medium | Offline | Ambitious / research |

---

## Hypotheses

### H1 — Isomorphic Perturbation Testing as an adversarial-drift / shortcut-learning audit

- **Source topics/reports:** 10 (IPT & GRIFT, verifier gaming in RLVR).
- **Hypothesis (falsifiable):** *If* we subject deployed fraud scorers to structure-preserving identity permutations (swap device fingerprints among equivalent devices, remap IP/merchant/account IDs while preserving graph relations and behavioral structure, permute amounts within an equivalence band) and require score invariance, *then* the score-instability rate under perturbation will rise measurably **before** production AUC-PR degrades when a fraud ring rotates devices/IPs/BINs, *because* shortcut-memorized models reference instances (which break under permutation) while structure-learning models reference transferable patterns (which are invariant).
- **Experiment design:** Baseline = current drift monitoring (feature/prediction-distribution + FPR tracking). Treatment = add an offline IPT harness that re-scores historical scored transactions under N structure-preserving perturbations and computes a per-model score-instability rate. Offline first, on replayed historical traffic spanning at least one known ring-rotation event; validate that instability spiked *ahead of* the accuracy drop. Then run as a continuous CI/audit gate.
- **Datasets/signals:** Historical scored transaction event streams, device/IP/merchant graph (for relation-preserving relabeling), confirmed-fraud + chargeback labels (for the lagging accuracy comparison), known ring-rotation incident timestamps.
- **Success metrics:** Lead time (days) between instability-spike alert and AUC-PR drop; correlation of instability rate with subsequent recall@fixed-FPR loss; false-alarm rate of the audit; ability to localize which feature families are shortcut-driven.
- **Effort:** Low. **Expected impact:** High.
- **Risks:** A sloppy "isomorphism" that actually changes true risk produces false alarms; if instability is later used as a *training reward* under heavy optimization, the model may learn to satisfy the audit while still shortcutting (the OpenAI obfuscation warning) — keep it an audit, not a reward.

### H2 — Provenance gating + activation/document-scan detection on agent-written entity memory

- **Source topics/reports:** 03 (Sleeper Memory Poisoning), 16 (memory governance / mnemonic sovereignty), 11 (AgeMem security), 06 (propagation along graph edges).
- **Hypothesis (falsifiable):** *If* every agent-derived entity-memory write carries source provenance (channel, timestamp, source trust tier) and passes a per-model activation-probe / document-scan gate before persistence, *then* the end-to-end sleeper-poisoning success rate (a planted "this merchant is low-risk" memory later steering an auto-approve) drops by a large margin versus an ungated write path, *because* externally-sourced claims are blocked from promotion to "verified fact" and injected payloads produce separable activation signatures (>0.95 AUROC reported) at write time.
- **Experiment design:** Build a red-team corpus of poisoned dispute narratives, merchant blurbs, KYC PDFs, and support-chat lines using an Actor–Critic universal-payload generator (per report 03). Baseline = naive memory-write path (and a prompt-hardening-only variant). Treatment = provenance tagging + write-time probe/scanner + provenance-weighted, temporally-decayed retrieval with per-entity isolation. Offline/shadow on a sandboxed investigation-agent stack. Measure injection rate, retrieval rate on goal-adjacent queries, and coupled end-to-end adversarial-usage rate.
- **Datasets/signals:** Synthetic poisoned-content corpus; investigation-agent memory store; the in-house version-pinned LLM backing the agent (for per-model probe training); benign labeled activations.
- **Success metrics:** End-to-end attack success rate (goal-adjacent), injection rate at write gate, probe AUROC on held-out payloads, write-path added latency (target: few-hundred-ms budget on the async path), memory-vs-graph contradiction detection rate.
- **Effort:** Medium. **Expected impact:** High.
- **Risks:** Probes transfer poorly across models (must retrain per model version); adaptive attacks defeated GEPA hardening on some models; vendors may already have partially hardened, shifting baselines; this is a *prerequisite* before any entity-memory product ships, so sequencing matters.

### H3 — Constant-state recurrent per-entity sequence encoder (decoupled erase/write gating)

- **Source topics/reports:** 14 (Gated DeltaNet-2 / KDA), 05 (Parallax local-linear recall), 04/01 (long-horizon entity memory motivation).
- **Hypothesis (falsifiable):** *If* we encode each entity's payment-event stream with a fixed-size recurrent state using decoupled channel-wise erase/write gates, *then* we match or beat a fixed-window sequence-transformer baseline on ATO/bot detection recall@fixed-FPR while holding p99 per-event scoring latency and per-entity memory constant as history grows, *because* the erase gate overwrites stale benign behavioral drift while the write/decay gates preserve durable fraud-relevant associations (device-to-chargeback-ring links) in a bounded state, and multi-key retention keeps several risk dimensions addressable at once.
- **Experiment design:** Baseline = current sequence encoder (fixed-window transformer / GBDT-on-aggregates). Treatment = clean-room reimplementation of the published Gated DeltaNet-2 recurrence (NC license blocks direct use) and a KDA/Gated-DeltaNet ablation ladder, as the per-entity sequence leg feeding the existing graph/tabular stack. Offline on historical event streams with strict out-of-time splits. Include an injected-drift stress test (synthetic "behavioral laundering": fraudster mimics benign patterns to age out).
- **Datasets/signals:** Per-entity (account/device/card) payment + login + session event streams; ATO labels; chargeback/confirmed-fraud labels; synthetic behavioral-drift attacks.
- **Success metrics:** AUC-PR and recall@fixed-low-FPR vs baseline; p99 scoring latency per event; bytes of state per entity (constant vs growing); robustness delta under injected drift; ATO detection lead time.
- **Effort:** Medium. **Expected impact:** High.
- **Risks:** No fraud-domain validation exists in the literature; single-scale (1.3B) NVIDIA-only results, no independent replication; NC license requires clean-room build; gains may not transfer from language modeling to tabular/sequence fraud. The systems property (constant state) is the safe anchor even if accuracy gains disappoint.

### H4 — Adaptive test-time compute cutoff for LLM triage / step-up reasoning

- **Source topics/reports:** 18 (Overthinking & adaptive TTC), with the inverse-scaling robustness angle.
- **Hypothesis (falsifiable):** *If* we add cheap online overthinking indicators (answer oscillation, hesitation markers, confidence trajectory) plus a decoding-margin early-stop to an LLM-based triage/step-up reasoning model, *then* we cut p50/p99 reasoning latency and token cost substantially while *reducing* reasoning-induced false declines on easy legitimate cases, *because* negative answer flips (correct→incorrect) accumulate past a per-difficulty token threshold and easy-confident legitimate traffic overthinks itself into wrong "decline" calls.
- **Experiment design:** Baseline = fixed-budget reasoning. Treatment = answer-oscillation + decoding-margin monitor with a tunable cost-of-compute λ. Offline on a replayed stream of historical case-review/step-up decisions; measure flip rate, false-decline impact, latency. Re-measure all thresholds on PayPal data (do not transfer the 7K/12K-token math numbers).
- **Datasets/signals:** Logged reasoning traces from any LLM-in-the-loop triage; ground-truth dispositions; per-case difficulty proxies (graph anomaly, entity-memory conflict).
- **Success metrics:** Token/compute reduction at fixed accuracy; false-decline rate delta on benign traffic; p99 latency; fraction of decisions terminated early with retained-accuracy.
- **Effort:** Low. **Expected impact:** Medium.
- **Risks:** ~1-in-4 early-stop triggers can be false alarms at the reported precision ceiling; thresholds are model/domain-specific; conformal-guarantee variants rest on exchangeability that adversarial drift violates.

### H5 — Sparse-indexer long-context entity memory for investigative scoring (DeepSeek-V4-Flash style)

- **Source topics/reports:** 01 (DeepSeek-V4 CSA/HCA + Lightning Indexer), 04 (SubQ/SSA subquadratic indexer — treat as research signal only).
- **Hypothesis (falsifiable):** *If* we score against an entity's months-to-years of raw event history held in a long-context model with a learned, query-conditioned sparse indexer (tiered compressed + selective recall), *then* we improve detection of slow-burn fraud (synthetic-identity aging, dormant-then-activated mules, merchant bust-out) versus a fixed feature-window/aggregate pipeline, *because* the indexer performs query-conditioned retrieval over the entity lifetime and can surface the one anomalous event amid millions that aggregates smooth away.
- **Experiment design:** Baseline = current aggregate/feature-window scorer + RAG. Treatment = V4-Flash (13B active) or an owned clean-room sparse-indexer model, used on the **async investigative tier** (not inline). Offline first; red-team specifically for compression-eviction / summary-poisoning (a fraudster padding history to dilute malicious tokens out of top-k). Gate any rollout on internal reproduction, not vendor claims.
- **Datasets/signals:** Long entity event histories; serialized graph neighborhoods (linearized edge lists); slow-burn fraud labels (synthetic-ID, mule, bust-out); adversarial padding test sets.
- **Success metrics:** Slow-burn fraud recall@k and AUC-PR; needle-in-history retrieval accuracy at long context; degradation curve vs context length; robustness to compression-eviction attacks; cost per investigative scoring call.
- **Effort:** High. **Expected impact:** High.
- **Risks:** Measured long-context degradation well inside the advertised window (sub-520K on real data); novel compression-specific adversarial surfaces; serving economics favor async use; SubQ-class vendor claims are unreproduced ("AI Theranos" risk) — do not adopt hosted SubQ for regulated decisions.

### H6 — Concept-mediated sparse graph memory for ring detection & multi-hop investigation

- **Source topics/reports:** 06 (GAAMA: concept-mediated PPR, hub dampening, provenance edges), 16 (entity-event graph layer).
- **Hypothesis (falsifiable):** *If* we build investigative entity memory as a concept-mediated sparse graph (episodes→transaction logs, facts→atomic risk assertions, reflections→analyst generalizations, concepts→fraud typologies/rings) with edge-type-aware Personalized PageRank and hub dampening, *then* multi-hop ring-detection recall improves over flat-RAG / entity-centric-KG investigation retrieval, *because* concept nodes give cross-cutting traversal that surfaces rings while hub dampening (`min(1, θ/deg)`) down-weights non-discriminative shared hubs (data-center IPs, popular device models) that dominate naive PPR.
- **Experiment design:** Baseline = flat-RAG over case notes + entity-centric KG (HippoRAG-style). Treatment = concept-mediated graph with edge-typed PPR + hub dampening + provenance edges; require concept canonicalization (the literature's top error source) before adversarial use. Offline on historical investigation cases with known fraud rings.
- **Datasets/signals:** Case-review logs, transaction logs, device/IP/merchant/account graph, confirmed ring memberships, analyst notes.
- **Success metrics:** Multi-hop ring recall/precision; temporal-question accuracy; provenance-trace completeness for SAR narratives; latency of depth-2 PPR at graph-DB scale; false-link rate from hubs.
- **Effort:** Medium. **Expected impact:** High.
- **Risks:** Graph contribution in the source was small (~+1.2pp; hierarchy carried most of the lift); no latency/scale numbers published; concept fragmentation is itself an attack surface (canonicalization is a prerequisite for adversarial robustness).

### H7 — Bidirectional (forward/backward) verifier for false-positive reduction and SAR/decline audit

- **Source topics/reports:** 02 (AgentV-RL forward sufficiency + backward necessity verifier), with SAVER self-audit; 12 (propose→refute→converge).
- **Hypothesis (falsifiable):** *If* we add a bidirectional verifier on borderline/high-value decisions — forward agent ("do the flagged signals add up to fraud?") + backward agent ("is every fraud criterion necessitated by the evidence, or did the model latch onto a spurious correlate?") with tool-grounded checks (graph queries, velocity aggregations, sanctions lookups) — *then* false declines on borderline good-customer cases drop without materially raising missed fraud, *because* an independent necessity check catches self-confirming forward errors, and the reported low right→wrong degradation rate means it rarely overturns correct decisions.
- **Experiment design:** Baseline = single-pass risk explanation/disposition. Treatment = distilled small forward verifier online for cheap sufficiency checks + full bidirectional tool-using agent on the offline high-stakes review queue. Offline/async only (latency disqualifies inline). Calibrate the binary verdict reward to PayPal's cost-asymmetric objective; re-ground the synthetic-data engine on real chargeback/confirmed-fraud outcomes.
- **Datasets/signals:** Borderline alert queue, decline/SAR decisions, device-graph + velocity + KYC + sanctions tools, chargeback labels.
- **Success metrics:** Alert precision lift; false-decline reduction at fixed missed-fraud; right→wrong overturn rate; regulator-readiness of premise→conclusion traces; $ good-customer-LTV preserved.
- **Effort:** Medium. **Expected impact:** Medium–High.
- **Risks:** ~8K tokens / minutes per case — disqualifying inline; GRPO optimizes verdict correctness, not trace faithfulness (pair with a self-audit layer for regulatory defensibility); math-benchmark gains may not transfer to noisy adversarial fraud.

### H8 — Lossless speculative decoding for LLM-in-the-loop case review

- **Source topics/reports:** 07 (Saguaro/SSD), 08 (Hybrid Verified Decoding), with EAGLE-3/P-EAGLE production context.
- **Hypothesis (falsifiable):** *If* we apply HVD (suffix-cache + EAGLE-3 with a learned payoff predictor) or speculative-speculative decoding to investigative/case-review LLM generation, *then* per-case decode latency and GPU cost drop ~2–3× *with bit-for-bit identical outputs*, *because* agentic case-review token streams are highly repetitive (fixed reasoning scaffolds, recurring tool-output formats, policy boilerplate) and lossless verification preserves the exact target distribution — so accelerated narratives remain audit-equivalent.
- **Experiment design:** Baseline = EAGLE-3-only (or greedy) on the existing case-review pipeline. Treatment = HVD with the payoff predictor trained from trace replay of logged case-review generations; test at the *production batch size actually served* (the key open gap — batch-1 gains may not survive continuous batching). Measure speedup, cache-acceptance distribution on real scaffolds, τ sensitivity.
- **Datasets/signals:** Logged case-review/SAR-drafting generation traces (for trace-replay predictor training); no labels or model retraining needed.
- **Success metrics:** Speedup vs EAGLE-3 at production batch; p99 latency; GPU cost/case; output-equivalence verification; cache-acceptance rate on PayPal scaffolds.
- **Effort:** Low. **Expected impact:** Medium.
- **Risks:** Batch-1-only evidence in the literature; Saguaro needs a dedicated draft GPU and isn't production-integrated (prefer EAGLE-3/P-EAGLE in vLLM); SD/SSD introduce a timing side-channel (accepted-vs-rejected latency leaks) that must be in the threat model for any externally-timeable fraud-facing endpoint.

### H9 — Semantic-aware prefix-cache eviction for investigation/assistant prompts

- **Source topics/reports:** 09 (SAECache token-type-weighted eviction), 13 (ZAYA1 KV compression context).
- **Hypothesis (falsifiable):** *If* we replace LRU prefix-cache eviction with token-type/queue-aware eviction (keep high-reuse risk-policy + entity-context blocks, aggressively evict single-use CoT) in the vLLM stack serving investigation/assistant prompts, *then* TTFT improves 1.4–2.7× and prefill recompute cost drops, *because* investigation prompts have ~42× reuse-rate spread between high-reuse structured prefixes (SOP/policy/entity-history) and throwaway reasoning tokens.
- **Experiment design:** Baseline = vLLM LRU. Treatment = SAECache drop-in Cache Evictor. Shadow/canary on real investigation-agent traffic that genuinely exhibits structured prefix reuse; verify no regression on low-reuse workloads (the source reports 12–34% TTFT degradation on low-multi-turn traffic).
- **Datasets/signals:** Live investigation/assistant serving traces; prompt-template structure.
- **Success metrics:** TTFT improvement; prefix-cache hit ratio; prefill FLOPs saved; regression check on low-reuse traffic.
- **Effort:** Low. **Expected impact:** Low–Medium.
- **Risks:** Single small-scale preprint (1.5B / single A40); the online miss-after-eviction learner is manipulable (cache-thrashing / timing side-channel) — bound weight excursions and monitor eviction churn; does not improve detection accuracy.

### H10 — Adaptive-budget LLM allocator gated on graph/sequence anomaly

- **Source topics/reports:** 18 (Lagrangian shadow-price allocator, Solve-then-Learn classifier), combined with PayPal's existing graph/sequence anomaly features.
- **Hypothesis (falsifiable):** *If* a lightweight gradient-boosted classifier predicts per-case reasoning budget from cheap pre-reasoning features (graph centrality / novel-edge formation, behavioral-sequence anomaly, entity-memory conflict) and allocates LLM compute via a Lagrangian shadow-price (`Acc − λ·Cost`), *then* we achieve higher accuracy-per-compute than uniform budgeting on the case-review tier, *because* spending long deliberation only on genuinely ambiguous high-anomaly cases and fast-cutting clean repeat-customer patterns matches fraud's heavily-skewed difficulty distribution.
- **Experiment design:** Baseline = uniform reasoning budget. Treatment = GBT allocator imitating an offline oracle, λ tuned to PayPal's true cost-of-latency. Offline on replayed case stream; conformal-control variant for an SLA guarantee on budget-overrun fraction (with continuous recalibration given drift).
- **Datasets/signals:** Pre-reasoning graph/sequence/entity-memory features; case dispositions; cost-of-latency model.
- **Success metrics:** Accuracy-per-compute vs uniform; fraction exceeding latency budget; relative accuracy gain at fixed average budget.
- **Effort:** Medium. **Expected impact:** Medium.
- **Risks:** Calibration/oracle table must be refit on distribution shift; conformal exchangeability breaks under adversarial drift; allocation classifier itself becomes a target.

### H11 — Collapse-free label-free RL for between-label-refresh self-adaptation

- **Source topics/reports:** 17 (Collapse-free Multi-Reward RLIF; Intuitor; No Free Lunch; JURY-RL verification gate).
- **Hypothesis (falsifiable):** *If* we self-train an offline risk-*reasoning* model on the unlabeled recent-transaction stream using a dual internal reward (cluster-vote consensus across rollouts + token self-certainty) with KL-Cov regularization, then periodically re-anchor on delayed confirmed labels, *then* the model adapts to fraud drift in the weeks before labels arrive without collapsing to the trivial "always predict legit" optimum, *because* the cluster-vote head ties the objective to cross-rollout consensus (a correctness proxy) and KL-Cov preserves exploration on the rare-fraud decisions that an entropy-collapse would erase.
- **Experiment design:** Baseline = static model retrained only on labeled refreshes. Treatment = RLIF self-training between refreshes + label re-anchoring + a JURY-RL-style verification gate. Offline only. Critically validate on a non-Qwen backbone (the Spurious-Rewards confound means Qwen gains may be artifacts) and with strict out-of-time splits.
- **Datasets/signals:** Unlabeled recent transaction/case stream; delayed chargeback/confirmed-fraud labels for re-anchoring; multiple reasoning rollouts per case.
- **Success metrics:** Drift-adaptation lift (recall@fixed-FPR on the weeks-before-label window); collapse check (entropy/always-legit rate over training); systematic-error (consensus-trap) monitoring; gain vs static baseline after re-anchoring.
- **Effort:** High. **Expected impact:** Medium.
- **Risks:** Preprint, no code, Qwen-only evidence; consensus trap (overconfident systematic errors voting can't catch); training-time only — no inline benefit; must pair with verification/re-anchoring to avoid confidently-wrong drift.

### H12 — Parallel self-verifying subagent swarm for case investigation

- **Source topics/reports:** 12 (Dynamic Workflows / Code-as-harness, propose→refute→converge), with vendor AML-agent context.
- **Hypothesis (falsifiable):** *If* we decompose a flagged case into parallel hypothesis-check subagents (device/IP linkage, velocity, merchant history, chargeback pattern, sanctions, counterparty graph), each with isolated context, then run an adversarial propose→refute→converge loop anchored to **deterministic sensors** (sanctions hits, confirmed chargebacks, concrete graph edges), *then* we produce regulator-ready, citation-grounded SAR narratives with per-hypothesis confidence and reduce analyst time-per-case, *because* clean per-hypothesis contexts plus explicit refutation yield inspectable evidence trails — and the orchestration-as-code program is itself a replayable audit object.
- **Experiment design:** Baseline = single-agent investigation loop / current analyst workflow. Treatment = code-orchestrated subagent swarm with deterministic-sensor convergence (NOT model self-critique consensus, which flips correct answers on easy cases), human-in-the-loop signer, tiered models (cheap for lookups, strong for synthesis), capped concurrency. Offline on historical cases with known outcomes.
- **Datasets/signals:** Case files, entity/transaction history, graph, sanctions/watchlists, chargeback history.
- **Success metrics:** Analyst time-per-case reduction; SAR-narrative regulator-readiness / citation completeness; investigation accuracy vs ground-truth disposition; cost per case; false-conclusion rate.
- **Effort:** Medium–High. **Expected impact:** Medium.
- **Risks:** Self-verification is unreliable unless anchored to deterministic signals (self-critique paradox flips correct answers on tasks the model handles well); token cost scales with subagent count (~80% of performance variance is spend); proprietary runtime (reproduce the pattern, not the Anthropic artifact); humans must own the final filing.

### H13 — Learned offline memory-curation policy credited by sparse fraud outcomes

- **Source topics/reports:** 11 (AgeMem step-wise GRPO, store/update/discard as learned actions), 16 (write–manage–read loop), with MemoryArena evaluation caveat.
- **Hypothesis (falsifiable):** *If* we train an offline policy that decides which weak per-entity signals to persist/decay/promote, credited by eventually-confirmed fraud outcomes via terminal-reward broadcast (step-wise GRPO), *then* a downstream scorer that simply *reads* the curated entity memory improves catch-rate at fixed FPR and ATO lead time versus fixed feature-window/TTL heuristics, *because* fraud's sparse, delayed, discontinuous labels match the credit-assignment structure (an early `store` only pays off at a much later confirmed-fraud outcome), letting the policy learn what is worth remembering about an entity.
- **Experiment design:** Baseline = fixed-window features + heuristic TTL eviction. Treatment = learned curation policy run *offline/async* between events (the agent never enters the 100ms hot path); the online scorer reads a precomputed retrieval-cheap entity memory. Evaluate on *decision-relevant* metrics, not recall benchmarks (MemoryArena's recall-vs-decision gap warning). Strict out-of-time splits.
- **Datasets/signals:** Confirmed-fraud-labeled entity histories; per-entity weak-signal candidates; ATO labels.
- **Success metrics:** Downstream catch-rate@fixed-FPR lift; ATO detection lead time; storage efficiency vs store-everything; decision-relevant memory quality (not recall F1).
- **Effort:** High. **Expected impact:** Medium.
- **Risks:** Research-stage, no official code, small open backbones, low absolute scores; LLM-judge reward components invite reward gaming; persistent learned memory is an attack surface (pair with H2 governance controls); recall benchmarks overstate decision-relevant ability.

---

## Cross-Cutting Themes & Sequencing

**Theme A — The hot path is sacred.** Every report independently concludes the sub-100ms synchronous scorer stays tabular/GNN/sequence-model. All LLM-heavy frontier work lands on the **async/investigative tier**, **offline training/audit**, or **serving infra**. Architectural ideas (constant-state recurrence H3, sparse-indexer memory H5) are the only candidates that could eventually touch near-real-time, and only via clean-room owned models.

**Theme B — Memory is simultaneously the biggest opportunity and the biggest new risk.** Long-horizon entity memory (H3, H5, H6, H13) is the single most-cited fraud opportunity. But sleeper memory poisoning (H2) is an imminent attack on exactly that substrate, amplified by fraud's predictable, goal-adjacent queries and graph-propagating trust. **H2 is a hard dependency for H6 and H13** — do not ship learned/graph entity memory products before the write-time governance controls exist.

**Theme C — Auditability is a recurring, regulator-facing win.** IPT instability metrics (H1), bidirectional premise→conclusion traces (H7), provenance edges (H6), lossless decoding (H8), overthinking-stop rationales (H4), and orchestration-as-code (H12) all produce explainable artifacts. Bundle these into a coherent model-risk-management story.

**Theme D — Verification must anchor to deterministic sensors.** H7 and H12 both depend on grounding verification in concrete signals (sanctions hits, confirmed chargebacks, graph edges), not model self-critique, which the self-critique-paradox literature shows flips correct answers on easy cases.

### Suggested order / dependencies

1. **Wave 1 (quick wins, weeks):** H1 (drift audit), H8 (lossless decode), H9 (cache eviction), H4 (adaptive cutoff). All low-effort, low-coupling, mostly offline/infra. H1 first — it informs retraining cadence for everything else.
2. **Wave 2 (foundational, prerequisite-gated):** H2 (memory governance) **before** any memory product. In parallel, H3 (constant-state encoder) and H6 (graph memory) as the entity-memory architecture spine. H7 (bidirectional verifier) and H10 (adaptive allocator) on the investigative tier.
3. **Wave 3 (ambitious bets):** H5 (long-context entity memory), H12 (subagent swarm investigation), H11 + H13 (offline self-improvement / learned curation). All require Wave-2 governance (H2) and the H1 audit harness as a safety net.

---

## What We Deliberately Skipped

- **SubQ / SSA hosted API for production decisions (report 04).** No technical report, no weights, no independent reproduction, single-run cherry-picked benchmarks (the Opus 4.6 MRCR 32.2-vs-78.3 red flag), uncertain base-model provenance. Unacceptable for regulated model-risk management as-is. We *retain the idea* (sub-quadratic indexer for entity memory) as a research signal inside H5, gated on internal reproduction on owned weights — but reject the vendor product.

- **Parallax as a standalone bet (report 05).** Genuinely interesting (local-linear estimate captures velocity *slopes* not just levels; active subtraction of decoy context), but the headline gains require migrating the entire training stack to the Muon optimizer, the benefit erodes under WSD decay, and it's validated only ≤1.7B dense short-context. The optimizer dependence is a disqualifying production blocker for a near-term bet. Its best ideas (sharper noisy-recall, decoy cancellation) are folded conceptually into H3 rather than pursued as a separate experiment.

- **ZAYA1-8B as a fraud model (report 13).** The model is Apache-2.0 and usable, but benchmarks are math/code/reasoning — not tabular/graph/sequence fraud — and it explicitly *lags* on the agentic/tool-use capability investigative workflows need. The transferable idea (PID-controlled router load as a governable, drift-resistant, auditable utilization signal; 8× KV compression) is interesting but single-source and under-ablated. Worth tracking, not worth a dedicated experiment this cycle; KV-compression value is partially captured by H9.

- **Meta-Soft attention-flow KV compression (report 15) and KVReviver as primary bets.** Gains over Judge Q are small (~0.9 LongBench, ~1.8 RULER), no confirmed code, no extreme-imbalance NIAH ablation (the one test that matters for fraud), and the value-vector mutation creates an *auditability liability* (must instrument routing weights for provenance). Monitor for code + independent reproduction; if pursued, it folds into H5/H3 long-session work rather than standing alone.

- **DeepSeek-V4-Pro (1.6T) for synchronous scoring (report 01).** Serving economics (Ascend-950-gated, "currently very limited" throughput) and measured retrieval degradation below ~520K tokens rule out V4-Pro on any latency-sensitive path. We carry forward only V4-Flash (13B active) on the async tier inside H5.

- **Pure model-self-critique convergence (report 12).** Explicitly skipped as a verification mechanism: the self-critique paradox shows model-on-model consensus net-flips correct answers on cases the model already handles well. H12 keeps the parallel-investigation *structure* but mandates deterministic-sensor anchoring and a human signer.

- **Conformal-guarantee TTC as a standalone fraud SLA (report 18).** The distribution-free guarantee rests on exchangeability/i.i.d. calibration, which adversarial drift — fraud's defining feature — deliberately violates. Folded into H4/H10 as a *monitored, continuously-recalibrated* component, never as a trusted standalone guarantee.
