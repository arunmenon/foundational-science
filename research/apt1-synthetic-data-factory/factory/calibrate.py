"""Calibrate a substrate=llm_judge policy against its gold set (judge-calibration.md §3).

Runs the LLM judge over judge/gold/<POLICY>.jsonl and reports precision/recall on INVALID +
Cohen's kappa vs the gold labels, against the acceptance gates (precision >= 0.90, recall >= 0.85,
kappa >= 0.80). Needs a live endpoint:

    export OPENAI_BASE_URL=... OPENAI_API_KEY=... OPENAI_MODEL=gpt-5.4-mini
    python3 calibrate.py ATO-P13

NOTE: the bundled gold set is a small [RDA] STARTER set (12 examples). The formal protocol wants
20-50 HUMAN-labeled examples per policy before a judge ships; this script is the harness to get
there, not a substitute for the human labels.
"""
from __future__ import annotations

import json
import os
import sys

from judge import LLMJudge
from llm_client import OpenAIChatClient

PRECISION_GATE, RECALL_GATE, KAPPA_GATE = 0.90, 0.85, 0.80


class _Policy:
    def __init__(self, pid):
        self.id = pid
        self.severity = "BLOCK"
        self.substrate = "llm_judge"


def _predicted_label(verdict):
    if verdict is None or verdict.get("passed") is None:
        return "UNCERTAIN"
    return "INVALID" if verdict["passed"] is False else "VALID"


def _cohens_kappa(pairs):
    """pairs = list[(gold, pred)] over definite (non-UNCERTAIN) predictions, labels in {VALID,INVALID}."""
    n = len(pairs)
    if not n:
        return 0.0
    agree = sum(1 for g, p in pairs if g == p)
    po = agree / n
    labels = ("VALID", "INVALID")
    pe = sum((sum(1 for g, _ in pairs if g == L) / n) * (sum(1 for _, p in pairs if p == L) / n) for L in labels)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def main(argv):
    policy_id = argv[1] if len(argv) > 1 else "ATO-P13"
    gold_path = os.path.join(os.path.dirname(__file__), "judge", "gold", f"{policy_id}.jsonl")
    if not os.path.exists(gold_path):
        print(f"no gold set at {gold_path}")
        return 2
    gold = [json.loads(line) for line in open(gold_path) if line.strip()]

    judge = LLMJudge(OpenAIChatClient(temperature=0.0))
    policy = _Policy(policy_id)
    tp = fp = fn = 0
    uncertain = 0
    kappa_pairs = []
    print(f"=== calibrating {policy_id} on {len(gold)} examples ({judge.client.model}) ===")
    for ex in gold:
        verdict = judge(policy, ex["log"])
        pred = _predicted_label(verdict)
        goldl = ex["label"]
        mark = "ok " if (pred == goldl) else ("UNC" if pred == "UNCERTAIN" else "XX ")
        print(f"  [{mark}] {ex['id']:>10}  gold={goldl:<8} pred={pred}")
        if pred == "UNCERTAIN":
            uncertain += 1
            if goldl == "INVALID":
                fn += 1  # a missed breach
            continue
        kappa_pairs.append((goldl, pred))
        if goldl == "INVALID" and pred == "INVALID":
            tp += 1
        elif goldl == "VALID" and pred == "INVALID":
            fp += 1
        elif goldl == "INVALID" and pred == "VALID":
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    kappa = _cohens_kappa(kappa_pairs)
    print(f"\nprecision(INVALID) = {precision:.2f}  (gate >= {PRECISION_GATE})  {'PASS' if precision >= PRECISION_GATE else 'FAIL'}")
    print(f"recall(INVALID)    = {recall:.2f}  (gate >= {RECALL_GATE})  {'PASS' if recall >= RECALL_GATE else 'FAIL'}")
    print(f"Cohen's kappa      = {kappa:.2f}  (gate >= {KAPPA_GATE})  {'PASS' if kappa >= KAPPA_GATE else 'FAIL'}")
    print(f"uncertain rate     = {uncertain}/{len(gold)} (routed to human-audit)")
    shipped = precision >= PRECISION_GATE and recall >= RECALL_GATE and kappa >= KAPPA_GATE
    print(f"\nJUDGE {'MEETS' if shipped else 'DOES NOT MEET'} acceptance gates"
          + ("" if shipped else " — tune the rubric or expand the gold set before relying on it."))
    return 0 if shipped else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
