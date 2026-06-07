"""CLI: generate + eval-gate trajectories for a pack against a live OpenAI-compatible endpoint.

Pick the pack with PACK (default "ato"); set your endpoint, then run `python3 generate.py`:
    export OPENAI_BASE_URL="https://your-endpoint/v1"
    export OPENAI_API_KEY="..."
    export OPENAI_MODEL="gpt-4o"        # or your deployed model name
    export GEN_K=8                       # trajectories to attempt (default 4)
    export PACK=ato                      # which domain pack to generate for

Eval-gating is FAIL-CLOSED: a trajectory is CERTIFIED GOLD only if it PASSes AND every policy in the
pack's certification manifest was actually evaluated. The ATO deterministic slice leaves the
llm_judge policy (ATO-P13) unevaluated, so nothing is certified gold yet — by design.

Each record stores both an `audit_trace` (internal: state snapshots + ground-truth-derived fields)
and a `model_transcript` (only what the models saw). Only the transcript is safe for SFT export.
"""
from __future__ import annotations

import json
import os
import time
import uuid

from generator import generate_and_grade
from judge import LLMJudge
from llm_client import OpenAIChatClient
from pack_ato import ATO_PACK

# Pack registry — add sibling packs here as they are built (scams, disputes, ...).
PACKS = {"ato": ATO_PACK}

OUTDIR = os.path.join(os.path.dirname(__file__), "generated")
MAX_STEPS = 24
PROMPT_VERSION = "agent/2026-06-05"


def compute_metrics(pass_flags: list) -> dict:
    """pass@1 = mean over ALL attempts; pass^k = did ALL k attempts pass (errors count as not-pass)."""
    n = len(pass_flags)
    passes = sum(1 for p in pass_flags if p)
    return {"n": n, "passes": passes,
            "pass_at_1": round(passes / n, 3) if n else 0.0,
            "pass_pow_k": int(n > 0 and passes == n)}


def _base_provenance(run_id, pack, agent, customer):
    return {
        "run_id": run_id,
        "pack": pack.pack_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "versions": {"contract": "v1.1", "pack": pack.pack_id,
                     "prompt": PROMPT_VERSION, "target": "blueprint1"},
        "model": {"agent": agent.model, "agent_temp": agent.temperature,
                  "customer": customer.model, "customer_temp": customer.temperature},
        "max_steps": MAX_STEPS,
    }


def _atomic_write(path, records):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    os.replace(tmp, path)


def main() -> int:
    pack_key = os.environ.get("PACK", "ato")
    pack = PACKS.get(pack_key)
    if pack is None:
        print(f"unknown PACK '{pack_key}'; known: {sorted(PACKS)}")
        return 2

    agent = OpenAIChatClient(temperature=0.0)
    customer = OpenAIChatClient(temperature=0.7)
    # Calibrated LLM judge for substrate=llm_judge policies (ATO-P13). Wired by default so certified
    # gold is reachable; set JUDGE_DISABLED=1 to skip it (then P13 stays unevaluated -> no gold).
    judge = None
    if not os.environ.get("JUDGE_DISABLED"):
        judge = LLMJudge(OpenAIChatClient(temperature=0.0, model=os.environ.get("JUDGE_MODEL")))
    k = int(os.environ.get("GEN_K", "4"))
    batch = uuid.uuid4().hex[:8]
    slug = pack.pack_id.lower()
    os.makedirs(OUTDIR, exist_ok=True)

    gold, candidates, pass_flags, errors = [], [], [], 0
    for i in range(k):
        run_id = f"{batch}-{slug}-{i}"
        rec = _base_provenance(run_id, pack, agent, customer)
        try:
            log, report, transcript = generate_and_grade(pack, agent, customer, judge=judge)
        except Exception as e:  # per-run boundary (review F5); errors count as not-pass (review F4)
            errors += 1
            pass_flags.append(False)
            rec.update({"terminal_reason": f"exception:{type(e).__name__}", "error": str(e),
                        "certified_gold": False})
            candidates.append(rec)
            print(f"run {i+1}/{k}: ERROR {type(e).__name__}: {e}")
            continue
        rec.update({
            "terminal_reason": report.get("terminal_reason"),
            "blueprint": report.get("scenario_blueprint"),
            "intent": report.get("scenario_intent"),
            "grade": {kk: vv for kk, vv in report.items() if not kk.startswith("_")},
            "missing_policy_ids": report.get("missing_policy_ids", []),
            "certified_gold": report.get("certified_gold", False),
            "model_transcript": transcript,   # model-visible: safe basis for SFT export
            "audit_trace": log,               # INTERNAL: includes state snapshots + ground truth
        })
        candidates.append(rec)
        pass_flags.append(report["final_grade"] == "PASS")
        if report.get("certified_gold"):
            gold.append(rec)
        print(f"run {i+1}/{k}: [{report.get('scenario_blueprint')}] {report['final_grade']}  "
              f"certified_gold={report.get('certified_gold')}  terminal={report.get('terminal_reason')}  "
              f"missing={report.get('missing_policy_ids')}  violations={report['hard_violations']}")

    _atomic_write(os.path.join(OUTDIR, f"{slug}.{batch}.candidates.jsonl"), candidates)
    _atomic_write(os.path.join(OUTDIR, f"{slug}.{batch}.gold.jsonl"), gold)

    m = compute_metrics(pass_flags)
    print(f"\nBatch {batch} (pack {pack.pack_id}): attempted {k}, {errors} errored.")
    print(f"pass@1 (mean over ALL attempts): {m['pass_at_1']}")
    print(f"pass^k (all {m['n']} attempts passed): {bool(m['pass_pow_k'])}")
    print(f"CERTIFIED GOLD (PASS + full manifest evaluated): {len(gold)}")
    print(f"Candidates written (incl. uncertified/errored): {len(candidates)}")
    missing_seen = sorted({p for c in candidates for p in c.get("missing_policy_ids", [])})
    if missing_seen:
        print(f"NOTE: manifest policies not evaluated -> {missing_seen}. PASSes are NOT promoted to "
              f"gold (fail-closed). Wire these (e.g. the llm_judge policy) to unlock gold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
