# APT-1 → PayPal Fraud/Commerce CX Synthetic-Data Factory

**Canonical contract version:** `v1.0` — see **[contract.md](spec/contract.md)** (authoritative source of truth).
Where any document below disagrees with `contract.md`, the contract wins.

A research → design package for an **eval-gated synthetic-trajectory factory** that trains and measures customer-facing fraud/commerce CX agents, grading **both** final-state outcome **and** trajectory-level policy adherence, with domain logic isolated in declarative **domain packs**.

## Repository layout
```
docs/         design & research narrative — read 00 → 08
spec/         canonical contracts — contract.md, pack_schema.json, predicate_language.md, judge-calibration.md
validation/   external gap-analyses + reusable prompts (circularity-breaking cross-checks)
factory/      runnable code — generic engine + ATO pack + LLM-judge + tests
              (RESULTS.md = teacher-model bake-off; pilot.md + runpod_setup.sh = self-hosting runbook)
```

## Read in this order
| # | File | Status |
|---|------|--------|
| — | **[contract.md](spec/contract.md)** | **canonical (v1.1)** — state/policy/metric/handoff + §8A action-space standard (from 3 external reviews) |
| — | [pack_schema.json](spec/pack_schema.json) | canonical — machine-readable pack schema |
| — | [predicate_language.md](spec/predicate_language.md) | canonical — executable predicate grammar (Past+Future LTL) |
| — | [judge-calibration.md](spec/judge-calibration.md) | canonical — LLM-judge protocol |
| 00 | [deep-research-apt1.md](docs/00-deep-research-apt1.md) | current — APT-1 first-principles research |
| 01 | [fraud-cx-factory-design.md](docs/01-fraud-cx-factory-design.md) | historical — architecture (state/checker examples superseded by contract.md) |
| 02 | [ppa-and-taxonomy.md](docs/02-ppa-and-taxonomy.md) | current — **taxonomy v2** (§2.v2; externally cross-checked 2026-06-04, scope = customer+merchant fraud-CX) + base-policy library (families superseded by contract.md §3) |
| — | [taxonomy-gap-analysis-external-2026-06-04.md](validation/taxonomy-gap-analysis-external-2026-06-04.md) | external cross-check evidence (independent LLM vs ACFE/FATF/UK-PSR/Visa-MC/OWASP/NRF/Fed) |
| — | [taxonomy-gap-analysis-prompt.md](validation/taxonomy-gap-analysis-prompt.md) | reusable gap-analysis prompt — taxonomy (re-run for the next cross-check) |
| — | [action-space-gap-analysis-prompt.md](validation/action-space-gap-analysis-prompt.md) | reusable gap-analysis prompt — a pack's action space (Tool schema) |
| — | [action-space-gap-analysis-ato-external-2026-06-04.md](validation/action-space-gap-analysis-ato-external-2026-06-04.md) | external cross-check of the **ATO** action space (18 proposed tools + cross-cutting contract fixes) |
| — | [action-space-gap-analysis-scams-external-2026-06-04.md](validation/action-space-gap-analysis-scams-external-2026-06-04.md) | external cross-check of the **scams** action space (22 proposed tools; confirms cross-cutting fixes) |
| — | [action-space-gap-analysis-disputes-external-2026-06-04.md](validation/action-space-gap-analysis-disputes-external-2026-06-04.md) | external cross-check of the **disputes** action space (23 proposed tools; confirms cross-cutting fixes a 3rd time) |
| 03 | [sop-to-predicate-methodology.md](docs/03-sop-to-predicate-methodology.md) | current — predicate methodology |
| 04 | [ato-domain-pack.md](docs/04-ato-domain-pack.md) | current pack — ATO (reference) |
| 05 | [introspection-and-contract-revision.md](docs/05-introspection-and-contract-revision.md) | historical — produced the v1.0 contract (now adopted) |
| 06 | [app-scams-domain-pack.md](docs/06-app-scams-domain-pack.md) | current pack — APP/scams |
| 07 | [commerce-disputes-domain-pack.md](docs/07-commerce-disputes-domain-pack.md) | current pack — Commerce/Disputes |
| 08 | [training-strategy.md](docs/08-training-strategy.md) | current — training recipe (open base → agentic CPT → SFT → RL-with-grader) + experiment plan. Objective (§2A), RL recipe (§5), consistency (§7, measure via Cover@τ) now evidenced; **reward-hacking mitigations the one remaining OPEN gap** |
| — | [factory/](factory/) | **runnable code (build started)** — ATO thin slice: deterministic sim env + 3 checkers + golden set. `python factory/run.py` → 2/2; proves the trace-less-breach discriminator |

## Status
- **Concept/architecture:** validated across 3 packs over 2 domains; contract converged (only additive `BASE-ELIG`).
- **Implementation readiness:** canonical layer in place (this pass). **Remaining before P2 code:** machine-readable `pack.yaml` per pack, unit tests per hard predicate, and a golden eval set (10 ATO / 10 APP / 10 Disputes, each with ≥1 clean + ≥1 violating trajectory). Carried prerequisite: confirm `tau-bench`/`tau2`/APIGen-MT reward mechanics from source.
- **PPA pack:** do **not** build until the internal "PPA" acronym is confirmed (see [02](docs/02-ppa-and-taxonomy.md) §1).

## Scope note
All PayPal-specific SOPs/tools/thresholds are **research-derived assumptions `[RDA]`** from public sources — not verified internal documents (pending SME sign-off).

**Provenance & circularity (important):** the taxonomy, SOPs, tools, and action spaces all share **one origin** — AI research over public sources — so they **cannot independently validate each other**. "Coverage against our taxonomy" is an internal-consistency check, not a completeness proof. Real completeness needs an **independent anchor**: external published fraud typologies (do now) then internal taxonomy/logs + SME sign-off (gold standard). See [02 §4A](docs/02-ppa-and-taxonomy.md) and the reusable [taxonomy-gap-analysis-prompt.md](validation/taxonomy-gap-analysis-prompt.md).
