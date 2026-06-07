# factory/ — generic engine + ATO pack (runnable)

Code slice of the synthetic-data factory. Proves the engine end-to-end on the ATO
sim-swapper blueprint: **deterministic simulated env → trajectory → 3 checkers → grade**.

**Generic engine + domain packs.** The engine (`state` + `env` + `grader` + `generator`) names no
domain — it is parameterized by a `Pack` (`pack.py`): policies, tool handlers, agent tool specs,
scenario, and `T_target`. ATO is the first *conforming* pack (`pack_ato.py` → `ATO_PACK`). Adding a
bucket (scams, disputes, ...) = writing one sibling pack module; the engine is untouched.

## Run
```bash
python3 run.py        # runs the golden set, prints a report, exits non-zero on mismatch
python3 -m pytest -q  # same assertions as tests
```
(Use `python3` — `python` may not be aliased on your shell.)

## Generate (live, against an OpenAI-compatible endpoint)
The generator uses the LLM for the *talking* (customer + agent), while the env + grader stay
deterministic code. Set your endpoint, then run:
```bash
export OPENAI_BASE_URL="https://your-endpoint/v1"
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-4o"     # or your deployed model name
export GEN_K=8                    # trajectories to attempt
export PACK=ato                   # which domain pack to generate for (registry in generate.py)
python3 generate.py
```
It generates K trajectories for the chosen pack, grades each with the code checkers, and
**eval-gates fail-closed** (files named `<pack>.<batch>.*.jsonl`):
- **Certified gold** (`generated/ato.<batch>.gold.jsonl`) = PASS **and** every policy in the pack's
  manifest evaluated. Because `ATO-P13` (llm_judge) is still a TODO, *nothing is certified gold yet*
  — that is intentional (you cannot certify text-safety without running the judge).
- **Candidates** (`generated/ato.<batch>.candidates.jsonl`) = every run (incl. uncertified
  PASSes and errored runs) with full provenance (model/temps/versions/grade/terminal_reason).

Metrics are reported as **pass@1** (mean over runs) and **pass^k** (did *all* k identical runs
pass — Pass100-style consistency), kept distinct. Per-run errors are caught so one bad response
never aborts the batch. The whole loop is verified offline by `test_generator.py` (ReplayClient —
no network), including: finalize-must-be-sole-call, no-action-after-disposition, customer turns
logged, unknown-tool rejection, and the metric distinction.

## Files
| File | Role |
| ---- | ---- |
| `pack.py` | **generic** `Pack` interface + `Policy` dataclass (the engine consumes this; it names no domain) |
| `state.py` | **generic** `CaseState` (BaseCaseState + a pack-owned `ext` dict) + trajectory helpers |
| `env.py` | **generic** `Environment` + executor; tools are pack-provided handlers (`handler(env, params)`) |
| `grader.py` | **generic** 3 checkers: outcome diff, trajectory-level policy check (incl. `substrate=llm_judge` via an injected judge), final grade + fail-closed gate |
| `generator.py` | **generic** LLM customer ↔ LLM agent ↔ code env → trajectory; parameterized by a `Pack` |
| `judge.py` | **generic** LLM-judge for `llm_judge` policies (ATO-P13): τ=0.70 + tie-breaker + UNCERTAIN→human-audit + verbatim-quote check (judge-calibration.md). Sees only model-facing conduct, never the answer key. `StubJudge` for offline tests |
| `pack_ato.py` | the first **conforming pack** (`ATO_PACK`): policies as predicates (**P01–P12 deterministic** + **P13 via the judge**) + tool handlers + agent specs + manifest + targets + a **scenario sampler** (fraud sim-swapper **and** legitimate true-negative) |
| `golden.py` | 6 trajectories: sim-swapper compliant (PASS) + 3 breaches (FAIL on ATO-P03) + **legit owner compliant (PASS) + legit wrongly-denied (FAIL on over-denial)** |
| `run.py` / `test_factory.py` | golden runner / checker tests |
| `llm_client.py` | `OpenAIChatClient` (OpenAI-compatible, stdlib-only) + `ReplayClient` (offline fixture) |
| `generate.py` | CLI: pick a `PACK`, generate N trajectories against a live endpoint, grade (with the P13 judge), **eval-gate**, write gold |
| `calibrate.py` + `judge/gold/ATO-P13.jsonl` | calibrate a judge against its gold set vs the acceptance gates (precision ≥ .90 / recall ≥ .85 / κ ≥ .80). Bundled gold is a small **[RDA] starter** set — formal gates need human labels |
| `test_generator.py` / `test_judge.py` | offline replay test of the generation loop + judge adjudication logic (no network) |

## What it demonstrates
Both golden trajectories reach the **same final outcome** (`deny_hold_escalate`, account held,
escalated). The compliant one steps up on a clean channel (EMAIL); the breach one caves to
pressure and steps up on the attacker-controlled SMS. **Final state is identical**, so a
naïve outcome-only grader passes both — but the trajectory-level policy checker catches the
breach on **ATO-P03** at the offending step. `task_success` is True for both; only the breach
has `hard_policy_pass == False`. That is the whole thesis, in code.

## Scope / caveats
- **Deterministic code only** (env + checkers) per contract — no LLM in the loop here.
- `ATO-P13` (no-waiver-under-pressure) is `substrate: llm_judge` → **skipped with a TODO**; it
  needs the calibrated judge (judge-calibration.md). Not faked.
- Tools/thresholds are **[RDA]** research-derived assumptions, not real PayPal APIs.
- This is a thin slice: a subset of ATO policies + tools, one blueprint, two trajectories.
  The engine is now **generic** (Level 1: packs as Python modules conforming to `Pack`). Next:
  a scenario *sampler* (breadth: legitimate/true-negative cases, attack-vectors, personas,
  difficulty), the ATO-P13 judge, sibling packs (scams/disputes), and eventually declarative
  `pack.yaml` (Level 2, contract §8A) with a generic predicate interpreter.
