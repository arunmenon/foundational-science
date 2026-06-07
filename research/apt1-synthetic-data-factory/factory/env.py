"""Deterministic simulated tool environment — domain-agnostic.

Per contract.md: the environment + ground truth are CODE (not an LLM), so grading has a
trustworthy basis. `Environment` is generic: it holds the scenario's ground-truth AccountDB and a
CaseState, and executes agent actions. The *tools* are supplied by the pack as a name -> handler
map (each handler is `handler(env, params) -> result` and may mutate `env.state` / read
`env.account`). The env itself names no domain.

An executor (`run`) replays a fixed list of agent actions (a golden trajectory); `apply` runs a
single action so the generator can interleave LLM turns and see tool results incrementally.

NOTE: [RDA] tool names/shapes live in the pack and are research-derived assumptions.
"""
from __future__ import annotations

import copy

from state import CaseState


class DispositionClosed(Exception):
    """Raised if any action is attempted after a final disposition (disposition is terminal)."""


class Environment:
    def __init__(self, scenario: dict, tools: dict):
        self.account = scenario.get("account", {})    # ground truth, hidden from the agent
        self.tools = tools                             # name -> handler(env, params) -> result
        self.state = CaseState(session_id=scenario.get("session_id", "sess-1"),
                               subdomain=scenario.get("subdomain", "GENERIC"))
        # FAIL-CLOSED (review F1): pack-owned ground-truth extension state (e.g. ATO's
        # attacker_controlled_channels) is materialized by the scenario and copied in at session
        # start, independent of whether the agent runs any discovery tool.
        self.state.ext = copy.deepcopy(scenario.get("initial_ext", {}))
        self._seq: dict = {}
        self._tick = 0
        self.log: list = []   # accumulated trajectory steps (supports incremental generation)

    # ---- helpers exposed to tool handlers ----
    def now(self) -> str:
        self._tick += 1
        return f"t{self._tick}"  # deterministic monotonic tick (no wall clock)

    def seq(self, key: str) -> int:
        self._seq[key] = self._seq.get(key, 0) + 1
        return self._seq[key]

    def add_evidence(self, signal, value, source_tool):
        self.state.evidence.append({"signal": signal, "value": value,
                                    "source_tool": source_tool, "ts": self.now()})

    # ---- executor ----
    def apply(self, action: dict) -> dict:
        """Execute ONE agent action, append a Step to self.log, and return it.

        Used both by run() (replay a full list) and by the generator (incremental, so the
        LLM agent can see tool results before deciding its next action).
        """
        # Disposition is TERMINAL (review F1): once set, no further action is permitted.
        if self.state.disposition is not None:
            raise DispositionClosed("no action permitted after a final disposition")
        kind = action["action"]
        if kind == "tool":
            tool = action["tool"]
            params = action.get("params", {})
            handler = self.tools.get(tool)
            if handler is None:
                raise ValueError(f"unknown tool: {tool}")
            result = handler(self, params)
            self.state.actions_taken.append({"tool": tool, "args": params, "result": result, "ts": self.now()})
            event = {"kind": "tool", "tool": tool, "params": params, "result": result}
        elif kind == "message":
            # role defaults to agent; the generator logs customer turns with role="customer".
            event = {"kind": "message", "role": action.get("role", "agent"), "text": action.get("text", "")}
        elif kind == "disposition":
            self.state.disposition = {"label": action["label"],
                                      "reason_codes": action.get("reason_codes", []),
                                      "sar_flag": action.get("sar_flag", False)}
            if "risk_decision" in action:
                self.state.risk_decision = action["risk_decision"]
            event = {"kind": "disposition", **self.state.disposition}
        else:
            raise ValueError(f"unknown action kind: {kind}")
        step = {"idx": len(self.log), "event": event, "state": self.state.snapshot()}
        self.log.append(step)
        return step

    def run(self, actions: list) -> list:
        for action in actions:
            self.apply(action)
        return self.log
