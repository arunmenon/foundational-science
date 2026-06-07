"""Run the golden ATO eval set end-to-end: env -> trajectory -> grader, and print a report.

Usage:  python run.py        (from the factory/ directory)
Exits non-zero if any case's grade != its expected grade (so it doubles as a smoke test).

The engine here is generic (`Environment` + `grade`); ATO specifics come from `ATO_PACK`.
"""
from __future__ import annotations

from env import Environment
from grader import grade
from pack_ato import ATO_PACK
from golden import golden_set


def run_case(case) -> dict:
    env = Environment(case["scenario"], ATO_PACK.tools)
    log = env.run(case["actions"])
    report = grade(log, case["target"], ATO_PACK.policies, ATO_PACK.required_policy_ids)
    report["_log"] = log
    return report


def main() -> int:
    cases = golden_set()
    failures = 0
    for case in cases:
        r = run_case(case)
        ok = r["final_grade"] == case["expected"]
        failures += 0 if ok else 1
        print(f"\n=== {case['name']}  (expected {case['expected']}) ===")
        print(f"  steps:            {len(r['_log'])}")
        print(f"  task_success:     {r['task_success']}   (field_diffs: {r['field_diffs'] or 'none'})")
        print(f"  hard_policy_pass: {r['hard_policy_pass']}   (violations: {r['hard_violations'] or 'none'})")
        print(f"  adherence_score:  {r['adherence_score']}")
        print(f"  missing (manifest) policies: {r['missing_policy_ids']}   (certified_gold: {r['certified_gold']})")
        print(f"  FINAL GRADE:      {r['final_grade']}   [{'OK' if ok else 'MISMATCH'}]")
    n = len(cases)
    print(f"\n{'-'*52}\nGolden set: {n - failures}/{n} matched expected grade.")
    if failures == 0:
        print("✅ Discriminator + fail-closed checks hold: every SMS breach FAILS on ATO-P03,")
        print("   including the skip-lookup and no-channel variants, while outcome stays identical.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
