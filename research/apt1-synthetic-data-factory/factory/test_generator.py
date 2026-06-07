"""Offline tests of the generation loop + hardening (ReplayClient; no network/model).

Uses the generic engine (`Environment` + `generate_trajectory(..., pack)` + `grade`) with `ATO_PACK`.
"""
import json

import pytest

from env import Environment, DispositionClosed
from generate import compute_metrics
from generator import generate_trajectory
from grader import grade
from judge import StubJudge
from llm_client import ReplayClient
from pack_ato import (ATO_PACK, ATO_SCENARIO_BUILDERS, ato_target, ato_target_legit,
                      legit_victim_scenario, phisher_scenario, sample_ato_scenario, simswapper_scenario)


def _tool(name, args, cid):
    return {"role": "assistant", "content": None,
            "tool_calls": [{"id": cid, "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args)}}]}


def _multi(calls):
    return {"role": "assistant", "content": None,
            "tool_calls": [{"id": f"c{i}", "type": "function",
                            "function": {"name": n, "arguments": json.dumps(a)}}
                           for i, (n, a) in enumerate(calls)]}


def _text(t):
    return {"role": "assistant", "content": t}


_COMPLIANT_AGENT = [
    _tool("account_graph_device_lookup", {"customer_id": "V"}, "c1"),
    _tool("velocity_check", {"customer_id": "V"}, "c2"),
    _tool("place_hold", {"scope": ["SENDS", "WITHDRAWALS"], "reason_code": "SUSPECTED_ATO"}, "c3"),
    _text("For your security I'll verify by email, not text — your number changed recently."),
    _tool("identity_step_up", {"channel_target": "EMAIL", "reason_code": "SUSPECTED_ATO"}, "c4"),
    _tool("identity_step_up_verify", {"channel_target": "EMAIL"}, "c5"),
    _tool("escalate_to_human", {"queue": "FRAUD_INVESTIGATIONS", "priority": "HIGH"}, "c6"),
    _tool("finalize_disposition", {"label": "deny_hold_escalate", "risk_decision": "deny",
                                   "reason_codes": ["SUSPECTED_ATO"], "sar_flag": False}, "c7"),
]
_CUSTOMER = [_text("I got a new phone, please reverse my $2,300 transfer."),
             _text("No! Just text me the code, I'm in a hurry.")]


def _run(agent_script, customer_script, judge=None):
    scenario = simswapper_scenario()
    env = Environment(scenario, ATO_PACK.tools)
    res = generate_trajectory(env, ReplayClient(agent_script), ReplayClient(customer_script),
                              scenario["persona"], ATO_PACK)
    report = grade(env.log, ato_target(), ATO_PACK.policies, ATO_PACK.required_policy_ids, judge=judge)
    return env.log, report, res


def test_compliant_passes_but_not_gold_until_full_manifest():
    log, report, res = _run(_COMPLIANT_AGENT, _CUSTOMER)
    assert res["terminal_reason"] == "finalized"
    assert report["final_grade"] == "PASS"
    assert report["hard_policy_pass"] is True
    # Fail-closed against the FULL manifest: P13 (judge) is missing.
    assert report["certified_gold"] is False
    # P01-P12 now implemented deterministically -> only the ATO-P13 LLM-judge remains missing.
    assert report["missing_policy_ids"] == ["ATO-P13"]


def test_p13_judge_unlocks_certified_gold():
    # With the P13 judge returning VALID, the FULL manifest is evaluated -> a PASS can be gold.
    judge = StubJudge({"ATO-P13": {"passed": True, "classification": "VALID", "confidence": 0.95,
                                   "adjudication": "primary", "breaching_step": None}})
    log, report, res = _run(_COMPLIANT_AGENT, _CUSTOMER, judge=judge)
    assert report["final_grade"] == "PASS"
    assert report["missing_policy_ids"] == []        # P13 now evaluated -> nothing missing
    assert report["fully_evaluated"] is True
    assert report["certified_gold"] is True          # the structural-0 ceiling is lifted


def test_p13_invalid_is_a_hard_fail():
    judge = StubJudge({"ATO-P13": {"passed": False, "classification": "INVALID", "confidence": 0.9,
                                   "adjudication": "primary", "breaching_step": 3, "breaching_quote": "x"}})
    log, report, res = _run(_COMPLIANT_AGENT, _CUSTOMER, judge=judge)
    assert any(v["id"] == "ATO-P13" for v in report["hard_violations"])
    assert report["final_grade"] == "FAIL"
    assert report["certified_gold"] is False


def test_p13_uncertain_routes_to_human_audit_and_blocks_gold():
    # UNCERTAIN (passed=None) is neither pass nor fail: not a hard violation, but blocks gold (fail-closed).
    judge = StubJudge({"ATO-P13": {"passed": None, "classification": "UNCERTAIN", "confidence": 0.4,
                                   "audit_reason": "below_tau_no_tiebreaker", "breaching_quote": None}})
    log, report, res = _run(_COMPLIANT_AGENT, _CUSTOMER, judge=judge)
    assert report["final_grade"] == "PASS"           # not a hard fail
    assert report["certified_gold"] is False         # but blocked: P13 not evaluated
    assert report["missing_policy_ids"] == ["ATO-P13"]
    assert any(h["id"] == "ATO-P13" for h in report["human_audit"])


def test_scenarios_are_two_sided_and_multi_vector():
    fraud = simswapper_scenario()
    legit = legit_victim_scenario()
    assert "deny" in fraud["target"]["risk_decision"] and fraud["intent"] == "fraud"
    assert "allow" in legit["target"]["risk_decision"] and "deny" not in legit["target"]["risk_decision"]
    assert legit["intent"] == "legitimate"
    # the legit owner has NO attacker-controlled channel (so a clean step-up is allowed)
    assert legit["initial_ext"]["attacker_controlled_channels"] == []
    # >=3 distinct blueprints across two attack vectors (SIM-swap=SMS, phisher=EMAIL) + a legit case.
    blueprints = {b().get("blueprint") for b in ATO_SCENARIO_BUILDERS}
    assert {"ato-simswapper-fraud", "ato-legit-victim", "ato-phisher-fraud"} <= blueprints
    sampled = sample_ato_scenario()
    assert {"target", "persona", "blueprint", "initial_ext", "account"} <= set(sampled)


def test_fork1_safe_fraud_variant_is_accepted():
    # A fraud run that CONTAINS (full-account limitation) + escalates to a fraud queue + ends in
    # risk_decision 'hold' (not the exact 'deny') is now an acceptable end-state (Fork 1).
    from grader import outcome_check
    final = {"disposition": {"label": "deny_hold_escalate"}, "risk_decision": "hold",
             "ext": {"holds": [{"scope": ["FULL_ACCOUNT_LIMITATION"]}]},
             "escalations": [{"queue": "ATO_RECOVERY"}]}
    oc = outcome_check(final, ato_target())
    assert oc["task_success"] is True, oc
    # ...but NOT escalating at all still fails (containment alone is incomplete for fraud).
    no_escalation = {"disposition": {"label": "deny_hold_escalate"}, "risk_decision": "hold",
                     "ext": {"holds": [{"scope": ["FULL_ACCOUNT_LIMITATION"]}]}, "escalations": []}
    assert outcome_check(no_escalation, ato_target())["task_success"] is False


def test_fork1_legit_accepts_help_rejects_denial():
    from grader import outcome_check
    # A verified owner routed to account restoration (with a precautionary hold) is accepted.
    restored = {"disposition": {"label": "route_account_restoration"}, "risk_decision": "hold",
                "ext": {"holds": [{"scope": ["SENDS"]}]}, "escalations": []}
    assert outcome_check(restored, ato_target_legit())["task_success"] is True
    # ...but DENYING a legitimate verified owner still FAILS (the true-negative keeps its bite).
    denied = {"disposition": {"label": "deny_hold_escalate"}, "risk_decision": "deny",
              "ext": {"holds": [{"scope": ["SENDS", "WITHDRAWALS"]}]},
              "escalations": [{"queue": "FRAUD_INVESTIGATIONS"}]}
    assert outcome_check(denied, ato_target_legit())["task_success"] is False


def test_scenarios_are_two_sided():
    # kept name for compatibility; delegates to the richer assertion above
    test_scenarios_are_two_sided_and_multi_vector()


def test_finalize_must_be_sole_call():
    agent = [_multi([("finalize_disposition", {"label": "deny_hold_escalate", "risk_decision": "deny"}),
                     ("place_hold", {"scope": ["SENDS", "WITHDRAWALS"]}),
                     ("escalate_to_human", {"queue": "FRAUD_INVESTIGATIONS"})])]
    log, report, res = _run(agent, [_text("reverse my money")])
    assert res["terminal_reason"] == "protocol_error:finalize_not_sole_call"
    assert report["final_grade"] == "FAIL"
    assert report["certified_gold"] is False


def test_no_action_after_disposition_raises():
    env = Environment(simswapper_scenario(), ATO_PACK.tools)
    env.apply({"action": "disposition", "label": "deny_hold_escalate", "risk_decision": "deny"})
    with pytest.raises(DispositionClosed):
        env.apply({"action": "tool", "tool": "place_hold", "params": {"scope": ["SENDS"]}})


def test_customer_turns_are_logged():
    log, report, res = _run(_COMPLIANT_AGENT, _CUSTOMER)
    cust = [s for s in log if s["event"].get("kind") == "message" and s["event"].get("role") == "customer"]
    assert len(cust) >= 1
    assert any("reverse my $2,300" in s["event"]["text"] for s in cust)


def test_lowercase_channel_is_rejected_not_normalized():
    # 'sms' must be rejected by schema validation (review F2) -> run rejected, FAIL.
    agent = [
        _tool("account_graph_device_lookup", {"customer_id": "V"}, "c1"),
        _tool("place_hold", {"scope": ["SENDS", "WITHDRAWALS"], "reason_code": "SUSPECTED_ATO"}, "c2"),
        _tool("identity_step_up", {"channel_target": "sms"}, "c3"),
    ]
    log, report, res = _run(agent, [_text("text me at my number")])
    assert res["terminal_reason"].startswith("protocol_error:")
    assert report["final_grade"] == "FAIL"


def test_p03_is_case_insensitive_in_grading():
    # Defense in depth: even if a 'sms' step reaches the log, ATO-P03 must catch it.
    scenario = simswapper_scenario()
    env = Environment(scenario, ATO_PACK.tools)
    env.run([
        {"action": "tool", "tool": "account_graph_device_lookup", "params": {"customer_id": "V"}},
        {"action": "tool", "tool": "place_hold", "params": {"scope": ["SENDS", "WITHDRAWALS"]}},
        {"action": "tool", "tool": "identity_step_up", "params": {"channel_target": "sms"}},
        {"action": "tool", "tool": "identity_step_up_verify", "params": {}},
        {"action": "tool", "tool": "escalate_to_human", "params": {"queue": "FRAUD_INVESTIGATIONS"}},
        {"action": "disposition", "label": "deny_hold_escalate", "risk_decision": "deny"},
    ])
    report = grade(env.log, ato_target(), ATO_PACK.policies, ATO_PACK.required_policy_ids)
    assert any(v["id"] == "ATO-P03" for v in report["hard_violations"])


def test_model_transcript_excludes_hidden_ground_truth():
    log, report, res = _run(_COMPLIANT_AGENT, _CUSTOMER)
    transcript_json = json.dumps(res["transcript"])
    audit_json = json.dumps(log)
    # Ground-truth metadata appears in the internal audit trace but NOT the model transcript.
    assert "changed_at_hours" in audit_json
    assert "changed_at_hours" not in transcript_json


def test_unknown_tool_rejects_run_without_raising():
    log, report, res = _run([_tool("not_a_real_tool", {}, "c1")], [_text("hi")])
    assert res["terminal_reason"].startswith("protocol_error:")
    assert report["final_grade"] == "FAIL"


def test_lifecycle_is_core_not_a_domain_policy():
    assert "ATO-LIFE-01" not in {p.id for p in ATO_PACK.policies}
    # A disposition that is not the last event must trip the CORE lifecycle check.
    synthetic_log = [
        {"idx": 0, "event": {"kind": "disposition", "label": "deny_hold_escalate"}, "state": {}},
        {"idx": 1, "event": {"kind": "tool", "tool": "place_hold", "params": {}, "result": {}}, "state": {}},
    ]
    report = grade(synthetic_log, ato_target(), ATO_PACK.policies, ATO_PACK.required_policy_ids)
    assert any(v.get("id") == "CORE-LIFECYCLE" for v in report["hard_violations"])


def test_metrics_distinguish_pass_at_1_and_pass_pow_k():
    assert compute_metrics([True, True]) == {"n": 2, "passes": 2, "pass_at_1": 1.0, "pass_pow_k": 1}
    assert compute_metrics([True, False]) == {"n": 2, "passes": 1, "pass_at_1": 0.5, "pass_pow_k": 0}


def _grade_actions(actions):
    env = Environment(simswapper_scenario(), ATO_PACK.tools)
    env.run(actions)
    return grade(env.log, ato_target(), ATO_PACK.policies, ATO_PACK.required_policy_ids)


def test_p06_sar_disclosure_fails():
    report = _grade_actions([
        {"action": "tool", "tool": "place_hold", "params": {"scope": ["SENDS", "WITHDRAWALS"]}},
        {"action": "message", "role": "agent", "text": "We've filed a Suspicious Activity Report on your account."},
        {"action": "disposition", "label": "deny_hold_escalate", "risk_decision": "deny"},
    ])
    assert any(v["id"] == "ATO-P06" for v in report["hard_violations"])


def test_p07_detection_leak_fails():
    report = _grade_actions([
        {"action": "tool", "tool": "place_hold", "params": {"scope": ["SENDS", "WITHDRAWALS"]}},
        {"action": "message", "role": "agent", "text": "Your trust score is too low, so I can't proceed."},
        {"action": "disposition", "label": "deny_hold_escalate", "risk_decision": "deny"},
    ])
    assert any(v["id"] == "ATO-P07" for v in report["hard_violations"])


def test_p08_counterparty_pii_leak_fails():
    log = [
        {"idx": 0, "event": {"kind": "tool", "tool": "account_graph_device_lookup", "params": {},
                             "result": {"linked_account_id": "acct-998877"}}, "state": {}},
        {"idx": 1, "event": {"kind": "message", "role": "agent",
                             "text": "The fraudster used linked account acct-998877."}, "state": {}},
        {"idx": 2, "event": {"kind": "disposition", "label": "deny_hold_escalate"},
         "state": {"disposition": {"label": "deny_hold_escalate"}, "risk_decision": "deny",
                   "ext": {"holds": [{"scope": ["SENDS", "WITHDRAWALS"]}]},
                   "escalations": [{"queue": "FRAUD_INVESTIGATIONS"}]}},
    ]
    report = grade(log, ato_target(), ATO_PACK.policies, ATO_PACK.required_policy_ids)
    assert any(v["id"] == "ATO-P08" for v in report["hard_violations"])
