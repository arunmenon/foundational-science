# Action-Space Gap-Analysis Prompt (external cross-check)

**Purpose:** Independent cross-check of a domain pack's **action space (Tool schema)** — the parallel to [taxonomy-gap-analysis-prompt.md](taxonomy-gap-analysis-prompt.md). Breaks the same circularity ([02 §4A](../docs/02-ppa-and-taxonomy.md)): our tools were AI-generated from the same source as everything else, so we validate them against **external fraud-ops playbooks**.

**Run it on a different model family** than the one that generated the pack, for independence.

**Two things to remember about action spaces specifically:**
- The external reviewer answers *"what actions **should** a fraud agent be able to take here?"* (best practice). It **cannot** know *"which tools actually exist in PayPal's systems"* — that's internal + SME, a later step.
- Run this **after** the pack's action space has been refreshed to match taxonomy v2, so the reviewer sees a current menu, not a stale one.

**How to use:** paste everything below the line into the LLM, filling the four `===` blocks at the end.

---

You are a senior fraud-operations and payments-platform expert who designs the **tools and runbooks** that customer-facing fraud agents use. Your job is a rigorous, adversarial **gap analysis of an AGENT ACTION SPACE (a "Tool schema")** for one fraud/commerce domain. The action space was AI-generated from public sources and may be incomplete or under-specified. Do NOT assume it is complete.

## What an "action space" is here
It is the fixed menu of tools the agent may call. Each tool in our standard has: a `name`, `args`, `returns` (where **each returned field is classified** `public | customer_disclosable | internal_pii | detection_signal | sar_related`, with a `customer_disclosable` true/false), and a `side_effect_class` ∈ `READ_ONLY | WRITE | MONEY_MOVEMENT`. Dangerous actions (WRITE/MONEY_MOVEMENT) are expected to be gated by policy and, where sensitive, require dual-control (an approver token).

## Inputs (pasted at the end)
1. `=== ACTION SPACE ===` — the pack's Tool schema (the menu to critique).
2. `=== TAXONOMY SUBTYPES THIS PACK MUST HANDLE ===` — the fraud subtypes (from taxonomy v2) this pack is responsible for. Coverage must be judged against these.
3. `=== POLICIES (optional) ===` — the pack's rules, so you can check the menu exposes what the policies need to enforce.
4. `=== OUR TOOL STANDARD ===` — the required tool metadata (so structural checks are precise).

## External anchors to triangulate against (use the ones relevant to this domain)
- **ATO recovery playbook** (NIST/industry): contain money movement → verify identity out-of-band on a clean channel → reset credentials/sessions/MFA → quarantine recently-changed contact methods → inventory changes → file unauthorized claim → post-recovery monitoring.
- **Scam / APP recovery**: recall/cancel pending payment → beneficiary-bank recall request → reimbursement-eligibility determination per jurisdiction (UK PSR mandatory vs US authorized-no-RegE) → scam report → repeated-payment intervention/cooling-off → victim education.
- **Card disputes / chargebacks** (Visa/Mastercard/Stripe): reason-code lookup → evidence/representment packet → deadline tracking → refund/credit issuance.
- **AML/CFT & SAR handling**: place/lift hold → escalate to compliance/FIU → SAR-safe language (no tipping-off) → document collection → sanctions/watchlist screening → no-disclosure-of-detection-logic.
- **KYC / identity**: tiered step-up → document/liveness submission → manual-review routing.
- **Generic platform**: place_hold/release_hold, escalate_to_human, send_verification_challenge, account-graph/device lookup, velocity check.

## What to do
1. **Action coverage map** — for each standard step in the relevant external playbook(s), find a matching tool. Quote the tool `name`, or mark **MISSING / PARTIAL**.
2. **Scenario coverage** — for EACH taxonomy subtype this pack must handle, decide: can the agent reach the correct outcome **within policy** using only the current menu? List subtypes with **no viable path** = coverage gaps. (This is the "feasibility" test.)
3. **Missing tools** — list actions the agent needs but the menu lacks.
4. **Structural / metadata quality** — for each EXISTING tool, flag: missing or wrong `args`/`returns`; missing/incorrect `side_effect_class`; missing **field-level data classification** (which returns are `internal_pii`/`detection_signal`/`sar_related` and must be `customer_disclosable:false`); and whether dangerous (WRITE/MONEY_MOVEMENT) actions are **gated/dual-controlled**.
5. **Granularity / redundancy** — tools that are too coarse, too fine, overlapping, or redundant.
6. **Safety & disclosure** — dangerous actions lacking guardrails; tools whose returns could leak PII/detection-signals/SAR status if not tagged; missing "never-disclose" classification.

## Output format (use these sections exactly)
### A. Action coverage map
Table: `External playbook step | Mapped tool? (quote name, or MISSING/PARTIAL) | Notes`.
### B. Scenario coverage
Table: `Taxonomy subtype | Solvable with current menu within policy? (YES / PARTIAL / NO) | Missing capability`.
### C. Proposed new tools (the gaps)
For each: `name`; `purpose` (1-2 sentences); `args`; `returns` (with per-field classification); `side_effect_class`; `gated_by` (which policy/guardrail; dual-control?); `which_subtype_or_playbook_step_needs_it`; `confidence` (high|med|low); `priority` (high|med|low).
### D. Structural / metadata fixes
Per existing tool: the missing/incorrect arg, return, classification, side-effect class, or guardrail, with the fix.
### E. Safety & disclosure issues
Dangerous-action guardrail gaps + data-leak risks (returns that should be `customer_disclosable:false`).
### F. Verdict
Overall sufficiency of the action space; the top missing tools; and SEPARATELY: "standard actions clearly missing (high confidence)" vs "edge/speculative".

## Rules
- Ground every proposed gap in a NAMED external playbook/standard or a concrete scenario — not vague intuition.
- Distinguish **"should exist (best practice)"** from **"exists internally (unknown — out of your scope)."** You are assessing what a good fraud agent *needs*, not what PayPal has built.
- Do NOT claim a tool exists unless you can quote its `name`; if unsure, mark MISSING/PARTIAL.
- Do NOT invent real internal API details, endpoints, or thresholds.
- Be over-inclusive in section C (candidate list for human/SME review, not final decisions).

=== ACTION SPACE ===
<PASTE the "Artifact 2 — Tool Schema" section of the pack here, e.g. from 04-ato-domain-pack.md>

=== TAXONOMY SUBTYPES THIS PACK MUST HANDLE ===
<PASTE the relevant subtypes from 02 §2.v2 for this pack, e.g. ATO attack-vectors + recovery>

=== POLICIES (optional) ===
<PASTE the pack's "Artifact 1 — Policy Pack" so coverage can be checked against what rules require>

=== OUR TOOL STANDARD ===
Each tool must declare: name; args; returns where every field has {classification ∈ public|customer_disclosable|internal_pii|detection_signal|sar_related, customer_disclosable: bool}; side_effect_class ∈ READ_ONLY|WRITE|MONEY_MOVEMENT. WRITE/MONEY_MOVEMENT actions must be gated by a policy; sensitive ones require a dual-control approver token. (Full schema: pack_schema.json; data-classification convention: contract.md §8.)
