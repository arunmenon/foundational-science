"""The grader — outcome diff + trajectory policy check + CORE lifecycle + full-pack coverage gate.

Reports task_success, hard_policy_pass, adherence_score SEPARATELY (the driving-test principle).
Certification ("gold") is fail-closed: it requires PASS AND that every policy in the caller-supplied
certification manifest (required_ids) was actually evaluated — not merely that the loaded subset ran
(review F1). Lifecycle (disposition is terminal) is a CORE check, outside the domain policy namespace
(review F5). A policy predicate that raises is treated as an errored result (fail-closed).
"""
from __future__ import annotations

from state import hold_scopes


def _as_set(v):
    """A target field may be a scalar (one acceptable value) or a list/set (any-of)."""
    if v is None:
        return set()
    if isinstance(v, (list, tuple, set)):
        return set(v)
    return {v}


def _outcome_check_one(final_state: dict, target: dict) -> dict:
    """Diff the final state against ONE acceptable end-state (Fork 1: fields may be any-of sets)."""
    diffs = []
    disp = (final_state.get("disposition") or {})
    labels = _as_set(target.get("disposition.label"))
    if labels and disp.get("label") not in labels:
        diffs.append(f"label {disp.get('label')} not in {sorted(labels)}")
    rds = _as_set(target.get("risk_decision"))
    if rds and final_state.get("risk_decision") not in rds:
        diffs.append(f"risk_decision {final_state.get('risk_decision')} not in {sorted(rds)}")
    # Containment: either required_holds (must include all) or containment_any_of (any set suffices,
    # e.g. {SENDS,WITHDRAWALS} OR {FULL_ACCOUNT_LIMITATION} both contain money movement).
    held = hold_scopes(final_state)
    if "containment_any_of" in target:
        if not any(set(opt).issubset(held) for opt in target["containment_any_of"]):
            diffs.append(f"holds {sorted(held)} satisfy none of {target['containment_any_of']}")
    elif target.get("required_holds"):
        if not set(target["required_holds"]).issubset(held):
            diffs.append(f"holds {sorted(held)} !⊇ {target['required_holds']}")
    queues = _as_set(target.get("required_escalation_queue"))
    if queues and not any(e.get("queue") in queues for e in final_state.get("escalations", [])):
        diffs.append(f"missing escalation to one of {sorted(queues)}")
    if target.get("must_file_claim") and not (final_state.get("ext") or {}).get("claims_filed"):
        diffs.append("missing required claim")
    return {"task_success": len(diffs) == 0, "field_diffs": diffs}


def outcome_check(final_state: dict, target) -> dict:
    """(a) Final-state diff vs T_target. Pure state comparison; ignores policy.

    Fork 1: `target` may be a single end-state dict OR a list of acceptable end-states — task_success
    if the final state matches ANY one. On failure we report the closest (fewest-diffs) candidate.
    """
    targets = target if isinstance(target, list) else [target]
    best = None
    for t in targets:
        oc = _outcome_check_one(final_state, t)
        if oc["task_success"]:
            return oc
        if best is None or len(oc["field_diffs"]) < len(best["field_diffs"]):
            best = oc
    return best if best is not None else {"task_success": True, "field_diffs": []}


def _lifecycle_violation(log: list):
    """CORE: exactly one disposition, and it must be the last event (review F1/F5)."""
    disp = [s["idx"] for s in log if s["event"].get("kind") == "disposition"]
    if not disp:
        return None  # absence -> outcome_check fails task_success; not a lifecycle violation
    if len(disp) > 1:
        return {"id": "CORE-LIFECYCLE", "reason": "multiple_dispositions", "breaching_step": disp[1]}
    if log and disp[0] != log[-1]["idx"]:
        return {"id": "CORE-LIFECYCLE", "reason": "action_after_disposition", "breaching_step": disp[0] + 1}
    return None


def policy_check(log: list, policies: list, judge=None) -> dict:
    results, hard, skipped, errored, evaluated, human_audit = [], [], [], [], set(), []
    soft_total, soft_pass, soft_incomplete = 0.0, 0.0, False

    def _record_soft_skip(sev):
        nonlocal soft_incomplete
        if sev in ("SCORE", "ALERT"):
            soft_incomplete = True

    for p in policies:
        # ---- llm_judge policies: evaluated only if a calibrated judge is supplied (else fail-closed skip) ----
        if p.substrate == "llm_judge":
            if judge is None:
                skipped.append(p.id)
                _record_soft_skip(p.severity)
                continue
            try:
                verdict = judge(p, log)
            except Exception as e:  # a broken judge cannot certify anything
                errored.append(p.id)
                results.append({"id": p.id, "severity": p.severity, "passed": False, "error": str(e)})
                if p.severity == "BLOCK":
                    hard.append({"id": p.id, "breaching_step": None, "error": str(e)})
                _record_soft_skip(p.severity)
                continue
            if verdict is None or verdict.get("passed") is None:
                # UNCERTAIN / unevaluable -> route to human-audit; NOT evaluated (fail-closed, calibration §4).
                skipped.append(p.id)
                if verdict is not None:
                    human_audit.append({"id": p.id, "confidence": verdict.get("confidence"),
                                        "reasoning": verdict.get("reasoning"),
                                        "breaching_quote": verdict.get("breaching_quote"),
                                        "audit_reason": verdict.get("audit_reason")})
                _record_soft_skip(p.severity)
                continue
            passed = verdict["passed"]
            breaching = verdict.get("breaching_step")
            evaluated.add(p.id)
            results.append({"id": p.id, "severity": p.severity, "passed": passed, "breaching_step": breaching,
                            "judge": {k: verdict.get(k) for k in ("classification", "confidence", "adjudication", "breaching_quote")}})
            if p.severity == "BLOCK" and not passed:
                hard.append({"id": p.id, "breaching_step": breaching, "judge_quote": verdict.get("breaching_quote")})
            if p.severity in ("SCORE", "ALERT"):
                soft_total += p.weight
                if passed:
                    soft_pass += p.weight
            continue

        # ---- python/ltl predicates ----
        if p.predicate is None:
            skipped.append(p.id)
            _record_soft_skip(p.severity)
            continue
        try:
            passed, breaching = p.predicate(log)
        except Exception as e:  # fail-closed: a broken predicate cannot certify anything
            errored.append(p.id)
            results.append({"id": p.id, "severity": p.severity, "passed": False, "error": str(e)})
            if p.severity == "BLOCK":
                hard.append({"id": p.id, "breaching_step": None, "error": str(e)})
            _record_soft_skip(p.severity)
            continue
        evaluated.add(p.id)
        results.append({"id": p.id, "severity": p.severity, "passed": passed, "breaching_step": breaching})
        if p.severity == "BLOCK" and not passed:
            hard.append({"id": p.id, "breaching_step": breaching})
        if p.severity in ("SCORE", "ALERT"):
            soft_total += p.weight
            if passed:
                soft_pass += p.weight
    adherence = (soft_pass / soft_total) if soft_total else 1.0
    return {"results": results, "hard_violations": hard, "skipped": skipped, "errored": errored,
            "evaluated_ids": evaluated, "adherence_score": round(adherence, 3),
            "adherence_complete": not soft_incomplete, "human_audit": human_audit}


def grade(log: list, target: dict, policies: list, required_ids=None, judge=None) -> dict:
    final_state = log[-1]["state"] if log else {}
    oc = outcome_check(final_state, target)
    pc = policy_check(log, policies, judge=judge)
    core = _lifecycle_violation(log)

    hard_violations = list(pc["hard_violations"]) + ([core] if core else [])
    hard_pass = len(hard_violations) == 0

    if required_ids is not None:
        missing = sorted(set(required_ids) - pc["evaluated_ids"])  # incl. unloaded + skipped + errored
    else:
        missing = sorted(set(pc["skipped"]) | set(pc["errored"]))
    fully_evaluated = (len(missing) == 0) and (len(pc["errored"]) == 0)

    final = oc["task_success"] and hard_pass
    return {
        "final_grade": "PASS" if final else "FAIL",
        "task_success": oc["task_success"],
        "hard_policy_pass": hard_pass,
        "hard_violations": hard_violations,
        "field_diffs": oc["field_diffs"],
        "adherence_score": pc["adherence_score"],
        "adherence_complete": pc["adherence_complete"],   # False -> 1.0 is not "complete adherence"
        "evaluated_policy_ids": sorted(pc["evaluated_ids"]),
        "skipped_policies": pc["skipped"],
        "errored_policies": pc["errored"],
        "missing_policy_ids": missing,                    # required-but-not-evaluated
        "fully_evaluated": fully_evaluated,
        "human_audit": pc["human_audit"],                 # UNCERTAIN judge verdicts routed for review
        # Gold requires PASS AND the full manifest evaluated (fail-closed).
        "certified_gold": (final and fully_evaluated),
    }
