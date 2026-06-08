"""CLI: generate + eval-gate trajectories for a pack against a live OpenAI-compatible endpoint.

Pick the pack with PACK (default "ato"); set your endpoint, then run `python3 generate.py`:
    export OPENAI_BASE_URL="https://your-endpoint/v1"   # the AGENT + CUSTOMER model endpoint
    export OPENAI_API_KEY="..."
    export OPENAI_MODEL="gpt-4o"                          # or your deployed model name
    export GEN_K=8                                        # trajectories to attempt (default 4)
    export GEN_CONCURRENCY=8                              # run this many in parallel (default 1)
    export PACK=ato

JUDGE (substrate=llm_judge policies, e.g. ATO-P13):
    - JUDGE_DISABLED=1                  -> skip the judge entirely (no certified gold; fail-closed)
    - JUDGE_BASE_URL / JUDGE_API_KEY / JUDGE_MODEL  -> run the judge on a DIFFERENT endpoint than the
      agent (e.g. agent on a local self-hosted vLLM, judge on the calibrated gpt-5.4-mini). Each falls
      back to the agent's OPENAI_* env if unset.

Eval-gating is FAIL-CLOSED: a trajectory is CERTIFIED GOLD only if it PASSes AND every policy in the
pack's manifest was evaluated. Records are written INCREMENTALLY (append + fsync per trajectory) to the
output volume, so a crash/teardown only ever loses the in-flight item — completed work is durable.

Each record stores an `audit_trace` (internal: state snapshots + ground-truth) and a
`model_transcript` (only what the models saw). Only the transcript is safe for SFT export.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def _append_jsonl(path, record, lock):
    """Durable incremental write: append one record, flush + fsync so a crash can't lose it."""
    line = json.dumps(record)
    with lock:
        with open(path, "a") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())


def _build_judge():
    """LLM judge for substrate=llm_judge policies, optionally on a separate endpoint (calibrated judge)."""
    if os.environ.get("JUDGE_DISABLED"):
        return None
    return LLMJudge(OpenAIChatClient(
        base_url=os.environ.get("JUDGE_BASE_URL"),   # None -> falls back to OPENAI_BASE_URL
        api_key=os.environ.get("JUDGE_API_KEY"),     # None -> falls back to OPENAI_API_KEY
        model=os.environ.get("JUDGE_MODEL"),         # None -> falls back to OPENAI_MODEL
        temperature=0.0))


def _run_one(i, pack, agent, customer, judge, batch, slug):
    """Generate + grade ONE trajectory. Returns (record, passed, errored). Never raises."""
    run_id = f"{batch}-{slug}-{i}"
    rec = _base_provenance(run_id, pack, agent, customer)
    try:
        log, report, transcript = generate_and_grade(pack, agent, customer, judge=judge)
    except Exception as e:  # per-run boundary; errors count as not-pass
        rec.update({"terminal_reason": f"exception:{type(e).__name__}", "error": str(e),
                    "certified_gold": False})
        return rec, False, True
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
    return rec, report["final_grade"] == "PASS", False


def main() -> int:
    pack_key = os.environ.get("PACK", "ato")
    pack = PACKS.get(pack_key)
    if pack is None:
        print(f"unknown PACK '{pack_key}'; known: {sorted(PACKS)}")
        return 2

    agent = OpenAIChatClient(temperature=0.0)
    # Customer role-play can run on a CHEAP model/endpoint (it doesn't need the agent's quality).
    # CUSTOMER_MODEL / CUSTOMER_BASE_URL / CUSTOMER_API_KEY fall back to the agent's OPENAI_* env.
    customer = OpenAIChatClient(temperature=0.7,
                                base_url=os.environ.get("CUSTOMER_BASE_URL"),
                                api_key=os.environ.get("CUSTOMER_API_KEY"),
                                model=os.environ.get("CUSTOMER_MODEL"))
    judge = _build_judge()
    k = int(os.environ.get("GEN_K", "4"))
    concurrency = max(1, int(os.environ.get("GEN_CONCURRENCY", "1")))
    batch = uuid.uuid4().hex[:8]
    slug = pack.pack_id.lower()
    os.makedirs(OUTDIR, exist_ok=True)
    cand_path = os.path.join(OUTDIR, f"{slug}.{batch}.candidates.jsonl")
    gold_path = os.path.join(OUTDIR, f"{slug}.{batch}.gold.jsonl")
    open(cand_path, "a").close()
    open(gold_path, "a").close()  # ensure both files exist even with 0 gold

    lock = threading.Lock()
    pass_flags, errors, gold_n, done = [], 0, 0, 0
    judge_desc = "off" if judge is None else (os.environ.get("JUDGE_MODEL")
                 or ("split:" + os.environ["JUDGE_BASE_URL"] if os.environ.get("JUDGE_BASE_URL") else agent.model))
    print(f"batch {batch} | pack {pack.pack_id} | k={k} concurrency={concurrency} | "
          f"agent={agent.model} judge={judge_desc}")

    def handle(result):
        nonlocal errors, gold_n, done
        rec, passed, errored = result
        # INCREMENTAL CHECKPOINT: append to the volume as each trajectory completes (crash-safe).
        _append_jsonl(cand_path, rec, lock)
        if rec.get("certified_gold"):
            _append_jsonl(gold_path, rec, lock)
        with lock:
            pass_flags.append(passed)
            errors += 1 if errored else 0
            gold_n += 1 if rec.get("certified_gold") else 0
            done += 1
            tag = "ERROR" if errored else rec.get("grade", {}).get("final_grade")
            print(f"[{done}/{k}] {rec.get('blueprint','?'):<22} {tag:<5} "
                  f"gold={rec.get('certified_gold')} term={rec.get('terminal_reason')} "
                  f"missing={rec.get('missing_policy_ids')}")

    if concurrency == 1:
        for i in range(k):
            handle(_run_one(i, pack, agent, customer, judge, batch, slug))
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = [ex.submit(_run_one, i, pack, agent, customer, judge, batch, slug) for i in range(k)]
            for fut in as_completed(futs):
                handle(fut.result())

    m = compute_metrics(pass_flags)
    print(f"\nBatch {batch} (pack {pack.pack_id}): attempted {k}, {errors} errored, concurrency {concurrency}.")
    print(f"pass@1 (mean over ALL attempts): {m['pass_at_1']}")
    print(f"pass^k (all {m['n']} attempts passed): {bool(m['pass_pow_k'])}")
    print(f"CERTIFIED GOLD: {gold_n}  ->  {gold_path}")
    print(f"Candidates (incremental, crash-safe): {cand_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
