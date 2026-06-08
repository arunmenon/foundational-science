# Introspection & Contract Revision — Review of Artifacts 00–04

**Date:** 2026-06-04
**Status:** Self-review before code (P2). Triggered by the decision to author a 2nd domain pack (APP/scams) as a generalization test. **→ ADOPTED:** these revisions are now canonical in [contract.md](../spec/contract.md) `v1.0` and applied to packs 04/06/07. This file is retained as the historical record of *why* the contract changed.
**Reviewed:** 00 (research) · 01 (factory design) · 02 (taxonomy) · 03 (SOP→predicate methodology) · 04 (ATO pack).

This is a deliberately critical pass. The artifacts were authored partly in parallel by separate agents, so the highest risk is **drift between documents** and **ATO-shaped abstractions masquerading as general**. Findings are severity-ranked. Each has evidence + fix. The canonical reconciliations feed directly into the APP/scams pack (06) and any P2 code.

---

## Severity 1 — must fix before code

### F1. Policy-ID collision: the same ID means different rules across docs
Three documents use three **incompatible** ATO policy-numbering schemes. Any code that references a policy by ID would silently grade against the wrong rule.

| ID | 01 §7 / 03 §8 say… | 04 (ATO pack) says… |
|---|---|---|
| ATO-P01 | identity-before-disclosure | **contain money movement first** |
| ATO-P03 | no reversal before verification | **never use recently-changed channel** |
| ATO-P04 | (n/a) | no reversal before verified ≥2 |
| ATO-P07 | SIM-swap → hold/escalate | **no threshold/score leakage** |
| ATO-P09 | (n/a) | SIM-swap → hold/escalate |
| ATO-P11 | hold-removal needs supervisor | **sanctions → AML** |
| ATO-P12 | (n/a) | hold-removal gate |
| ATO-P14 | social-engineering resistance | **(absent)** |

**Decision: `04` is canonical** (it is the most complete, research-grounded instantiation). 01 §7 and 03 §8 are the older illustrative scheme and must be renumbered to 04.

**Canonical old→new map** (apply to 01 §4.3/§7 and 03 §8):
`01/03 P01 → P02` · `01/03 P03 → P04` · `01/03 P07 → P09` · `01/03 P11 → P12` · `03 P14 → new P13` (see F2).

### F2. Gap: no explicit social-engineering-resistance policy in the ATO pack
04's own worked trajectory is a sim-swapper *pressuring* the agent, yet 04 has **no explicit predicate** for "don't waive steps under pressure" — it's left implicit in personas. 03 §8.5 already wrote the rule (as P14, LLM-judge). For ATO specifically, social engineering is *the* attack vector, so it must be a first-class rule.
**Fix: add `ATO-P13` to 04** — "Do not waive/skip/defer identity verification or required steps because the caller claims urgency, authority, or inconvenience" — `severity: ALERT`, `substrate: llm_judge`, weight ~0.8 (the body already exists in 03 §8.5).

---

## Severity 2 — fix before scaling past one pack

### F3. The base-policy library (defined in 02 §3) is not actually applied in 04
02 §3 defines a shared `BASE-AUTH/ESC/DISC/FUNDS/AUDIT` library and says packs "import + extend" it. But 04 was written in parallel and only *notes in prose* which rules are "base-policy primitives" (P02/P06/P08/P10/P11) — it does not express them as `BASE-*` specializations. So the composition model exists on paper but isn't instantiated.
**Fix (enforced by pack #2):** every pack policy declares `extends: BASE-XXX | null`. Cross-cutting rules (anti-tipping-off, disclosure limits, hold/reverse/claim decisioning, escalation, audit) live **once** in the base and are specialized per pack. The ATO pack's P06/P07/P08 → `BASE-DISC`; P09/P10/P11 → `BASE-ESC`; P01/P04/P05 → `BASE-FUNDS`; P02/P03/P13 → `BASE-AUTH`. **Pack #2 is authored this way from the start, and proves the base is real.**

### F4. CaseState is ATO-shaped (the central generalization risk)
04's CaseState spine is **identity-centric**: `verified_identity`, `attacker_controlled_channels`, `holds`, identity-gated disclosure. That is the right shape for ATO, where the core question is *"is the contacting party the real owner?"* It is the **wrong** shape for APP/scams, where the contacting party **is** the verified owner who **authorized** the payment — identity verification is nearly irrelevant; the question is *"is my own customer being scammed?"*
**Fix: split the contract into `BaseCaseState` + per-pack extension.**
- `BaseCaseState` (truly shared): `session_id, subdomain, evidence[], actions_taken[], customer_actions_coached[], escalations[], disposition{label, reason_codes, sar_flag}`.
- ATO extension: `verified_identity, attacker_controlled_channels, holds, claims_filed`.
- APP extension (pack #2): `payment_stage, payee_novelty, scam_typology, coercion_indicators, warnings_given, reimbursement_eligibility, recovery_attempted`.
`disposition.label` is a **per-pack enum**, not a global one. This is the most important structural correction and the core reason authoring pack #2 *before* code was the right call.

### F5. Adversary model is ATO-specific
04 assumes the **adversary is the contacting party** (impostor to be detected). In APP/scams the **adversary is absent** and acts *through* a cooperative-seeming, authenticated victim (the scammer coaches the victim off-channel). So "adversarial robustness" means two different things: ATO = *detect the impostor*; APP = *protect the customer from themselves under third-party coercion*. The factory's persona/adversarial-metric definition (01 §6, 04 Artifact 3) must be **generalized to "adversarial pressure source ∈ {contacting_party, absent_third_party}"**, not hard-coded to "fraudster persona = caller."

---

## Severity 3 — cleanups / consistency

- **F6. Metric-name drift.** 01 §9 "policy-adherence rate"; 03 "hard-policy pass + adherence_score"; 04 "policy_pass + adherence_score". **Standardize on 03's:** `task_success`, `hard_policy_pass`, `adherence_score`, `pass^k`. Update 01 §9 and 04 Artifact 5 wording.
- **F7. Recency-window knob.** 04 hard-codes 72h for `attacker_controlled_channels`; 02 BASE-AUTH says "24–72h". **Make it a named pack constant** `RECENCY_WINDOW_H` (default 72, assumption) referenced by ATO-P03.
- **F8. `risk_decision` modeling wrinkle.** 04 Blueprint 2 writes `risk_decision: "step_up"→"allow"`, but the field is described as single-valued in a monotonic state. **Clarify:** `risk_decision` is the *final* decision; intermediate transitions live in `actions_taken`. (Or make it append-only history.)
- **F9. Known open item to carry, not fix now:** 03 §7.4 correctly flags that the exact tau-bench `r_action`/`r_output` code and APIGen-MT committee threshold were not in fetched abstracts — must be read from the GitHub source before P2 implementation. Keep as a P2 prerequisite.

---

## What held up well (keep)
- The **trajectory-level policy grading decoupled from final-state** (03) is the strongest idea and is correctly the spine of both 03 and 04; the worked "correct-outcome-but-policy-violating FAILS" trajectory (04) is exactly right.
- **Substrate-by-checkability** (Python/Rego vs LTL vs LLM-judge) (03 §2) generalizes cleanly to APP.
- **Sourcing discipline** (public-verified vs `[RDA]`) is consistent and rigorous across 02/03/04 — keep enforcing it.
- **Eval-gated** flow (01 §5) and the **5-artifact pack contract** (01 §3) are sound; only the *contents* needed the base/extension split (F4).

---

## Revised contract (the version pack #2 and P2 build against)

1. **Canonical policy IDs = 04's scheme** + new ATO-P13 (F1, F2).
2. **Every policy declares `extends: BASE-* | null`;** cross-cutting rules live in the base library (F3).
3. **`BaseCaseState` + per-pack extension; `disposition.label` is per-pack** (F4).
4. **Adversary model parameterized:** `pressure_source ∈ {contacting_party, absent_third_party, none}` (F5).
5. **Metrics:** `task_success`, `hard_policy_pass`, `adherence_score`, `pass^k` (F6).
6. **Assumption knobs are named constants** (`RECENCY_WINDOW_H`, `HIGH_VALUE_THRESHOLD`, …) (F7).

**Follow-up edits — APPLIED:** 01 §4.3/§7 and 03 §8 renumbered to canonical IDs; ATO-P13 added to 04; 04 policies retagged with `extends: BASE-*`; metric names + adherence-score formula standardized; `BASE-FUNDS` split 3-way and `BASE-ELIG` added. The canonical contract now lives in [contract.md](../spec/contract.md); remaining implementation cleanup (machine-readable `pack.yaml`, unit tests, golden eval set) is tracked in [README.md](../README.md).
