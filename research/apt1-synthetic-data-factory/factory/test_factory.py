"""Tests: golden cases grade as expected, and the ATO-P03 checker is robust to bypasses.

Run:  pytest        (or just `python3 run.py`, which also asserts)

Uses the generic engine (`Environment` + `grade`) parameterized by `ATO_PACK`.
"""
from env import Environment
from grader import grade
from pack_ato import ATO_PACK
from golden import golden_set


def _grade(case):
    env = Environment(case["scenario"], ATO_PACK.tools)
    log = env.run(case["actions"])
    return grade(log, case["target"], ATO_PACK.policies)


def _by_name():
    return {c["name"]: c for c in golden_set()}


def test_golden_grades_match_expected():
    for case in golden_set():
        report = _grade(case)
        assert report["final_grade"] == case["expected"], (case["name"], report)


def test_breach_is_traceless():
    cases = _by_name()
    comp = _grade(cases["ato-simswapper-compliant"])
    breach = _grade(cases["ato-simswapper-breach-sms"])
    # Identical final outcome ...
    assert comp["task_success"] is True
    assert breach["task_success"] is True
    # ... but only the breach fails the trajectory-level policy check, on ATO-P03.
    assert comp["hard_policy_pass"] is True
    assert breach["hard_policy_pass"] is False
    assert any(v["id"] == "ATO-P03" for v in breach["hard_violations"])


def test_p03_cannot_be_bypassed():
    """All SMS/no-channel breaches must FAIL on ATO-P03 — even skipping the discovery lookup."""
    cases = _by_name()
    for name in ("ato-simswapper-breach-sms", "ato-breach-skip-lookup", "ato-breach-no-channel"):
        r = _grade(cases[name])
        assert r["final_grade"] == "FAIL", (name, r)
        assert any(v["id"] == "ATO-P03" for v in r["hard_violations"]), (name, r)
        # The outcome still looks correct — proving these are trace-less policy failures.
        assert r["task_success"] is True, (name, r)
