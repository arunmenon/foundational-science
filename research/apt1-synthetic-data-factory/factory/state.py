"""Core state + trajectory data model for the fraud-CX synthetic-data factory.

This is a REDUCED in-memory model aligned to (not 1:1 with) contract.md v1.1 §2
(BaseCaseState + per-pack extension). The base fields below are domain-agnostic; anything a
specific pack needs (ATO's verified_identity / holds / attacker_controlled_channels, a disputes
pack's claim ledger, ...) lives in `ext`, a free-form dict the pack owns. The engine never reads
`ext` directly — only pack predicates and pack tool handlers do, via helpers like `hold_scopes`.

A trajectory is a list of Steps; each Step records the event and a snapshot of the CaseState
*after* the event was applied (so checkers can read state at any step).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class CaseState:
    """BaseCaseState (contract §2) + a pack-owned `ext` extension dict."""

    session_id: str
    subdomain: str = "GENERIC"

    # BaseCaseState (domain-agnostic)
    contact_auth_context: dict = field(
        default_factory=lambda: {
            "authenticated": True,
            "auth_level": "standard",
            "contacting_party_role": "unknown",
        }
    )
    evidence: list = field(default_factory=list)            # [{signal, value, source_tool}]
    actions_taken: list = field(default_factory=list)       # [{tool, params, result}]
    customer_actions_coached: list = field(default_factory=list)
    escalations: list = field(default_factory=list)         # [{queue, priority, status}]
    risk_decision: Optional[str] = None                     # allow|step_up|hold|deny
    disposition: Optional[dict] = None                      # {label, reason_codes, sar_flag}

    # Pack-owned extension (e.g. ATO: verified_identity / holds / attacker_controlled_channels).
    ext: dict = field(default_factory=dict)

    def snapshot(self) -> dict:
        """Deep, plain-dict copy of the state for the trajectory log."""
        return copy.deepcopy(asdict(self))


# A trajectory log is list[Step]; a Step is a plain dict to keep checkers simple:
#   {"idx": int, "event": Event, "state": <CaseState snapshot dict>}
# Event is one of:
#   {"kind": "tool", "tool": str, "params": {...}, "result": {...}}
#   {"kind": "message", "role": "agent", "text": str}
#   {"kind": "disposition", "label": str, "reason_codes": [str], "sar_flag": bool}


# ---- shared state helpers (read the pack `ext`; safe on any state dict) ----
def _ext(state: dict) -> dict:
    return state.get("ext") or {}


def verified_level(state: dict) -> int:
    vi = _ext(state).get("verified_identity")
    return (vi or {}).get("level", 0)


def hold_scopes(state: dict) -> set:
    scopes: set = set()
    for h in _ext(state).get("holds", []):
        scopes.update(h.get("scope", []))
    return scopes


def evidence_signals(state: dict) -> dict:
    return {e["signal"]: e["value"] for e in state.get("evidence", [])}


def attacker_channel_set(state: dict) -> set:
    """Channel identifiers known (from ground truth) to be attacker-controlled."""
    out = set()
    for c in _ext(state).get("attacker_controlled_channels", []):
        out.add(c["channel"] if isinstance(c, dict) else c)
    return out
