"""Generic pack interface — the engine consumes a Pack; it never names a domain.

A domain pack (ATO, scams, disputes, ...) is just an instance of `Pack`. The engine
(env + grader + generator) is parameterized by it, so adding a bucket = writing one pack module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Policy:
    id: str
    severity: str          # BLOCK | SCORE | ALERT
    substrate: str         # python | ltl | llm_judge
    text: str
    predicate: Optional[Callable] = None   # (log) -> (passed, breaching_step); None for llm_judge stub
    weight: float = 0.0    # soft rules only
    extends: Optional[str] = None


@dataclass
class Pack:
    pack_id: str
    policies: list                         # list[Policy]
    required_policy_ids: list              # certification manifest
    tools: dict                            # name -> handler(env, params) -> result
    agent_tool_specs: list                 # OpenAI function specs handed to the agent
    target: dict                           # T_target for the (single) blueprint, for now
    scenario: Callable                     # () -> scenario dict (will become a sampler)
    disposition_labels: list = field(default_factory=list)
    agent_instructions: str = ""           # pack-specific system preamble (role/brief) for the agent
