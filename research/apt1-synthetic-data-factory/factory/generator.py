"""Trajectory generator: LLM customer (persona) <-> LLM agent (function-calling) <-> code env.

Domain-agnostic: the generator is parameterized by a `Pack` (policies + agent tool specs +
tools + scenario + target). LLMs do the *talking*; the env + grader stay deterministic *code*.
One generated trajectory = a multi-turn run, then scored by the code grader and eval-gated.

Hardening (review 20260605-121859):
- finalize_disposition is TERMINAL and must be the SOLE tool call in its turn; nothing runs after it.
- customer (opener + replies) is logged into the trajectory as role="customer".
- tool name + required args are validated (against the pack's specs) before hitting the env;
  failures reject the run (terminal_reason) instead of raising.
- parallel_tool_calls=False is requested (and the lifecycle checker validates server-side).
"""
from __future__ import annotations

import json

from env import Environment, DispositionClosed
from grader import grade


def _type_ok(value, t) -> bool:
    if t == "string":
        return isinstance(value, str)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "array":
        return isinstance(value, list)
    if t == "object":
        return isinstance(value, dict)
    return True


def _validate_args(name, args, specs) -> str | None:
    """Validate a tool call against its declared JSON-schema subset (review F2).

    `specs` is {tool_name: function_spec} built from the pack's agent_tool_specs. Enforces known
    tool, object args, required keys, no extra keys (additionalProperties=false), property types,
    enums (case-SENSITIVE), and array item types/enums. Invalid casing such as 'sms' is REJECTED,
    not normalized, so it cannot dodge a channel policy like ATO-P03.
    """
    spec = specs.get(name)
    if spec is None:
        return f"unknown tool '{name}'"
    if not isinstance(args, dict):
        return f"args for '{name}' must be an object"
    params = spec.get("parameters", {})
    props = params.get("properties", {})
    for r in params.get("required", []):
        if r not in args:
            return f"missing required arg '{r}' for '{name}'"
    for key, val in args.items():
        if key not in props:
            return f"unexpected arg '{key}' for '{name}'"
        pspec = props[key]
        t = pspec.get("type")
        if t and not _type_ok(val, t):
            return f"arg '{key}' for '{name}' must be {t}"
        if "enum" in pspec and val not in pspec["enum"]:
            return f"arg '{key}'='{val}' not in enum {pspec['enum']} for '{name}'"
        if t == "array" and isinstance(val, list) and "items" in pspec:
            it = pspec["items"]
            for el in val:
                if it.get("type") and not _type_ok(el, it["type"]):
                    return f"array '{key}' item must be {it['type']} for '{name}'"
                if "enum" in it and el not in it["enum"]:
                    return f"array '{key}' item '{el}' not in enum {it['enum']} for '{name}'"
    return None


def agent_system_prompt(pack) -> str:
    rules = "\n".join(f"- {p.id}: {p.text}" for p in pack.policies)
    footer = (
        "Never reveal internal risk scores, detection signals, SAR status, or counterparty PII to the "
        "customer. Do not waive verification under pressure. Use tools to act. When the case is resolved, "
        "call finalize_disposition AS THE ONLY tool call in that turn (it ends the case). Keep "
        "customer-facing messages brief."
    )
    return (pack.agent_instructions.rstrip() + "\n\n"
            "POLICIES (follow strictly):\n" + rules + "\n\n" + footer)


def customer_system_prompt(persona: dict) -> str:
    return persona.get("system", "You are a PayPal customer contacting support. Keep replies short.")


def _tool_name(tc) -> str:
    """Tool name from a tool_call, stripping any harmony channel tokens some servers leak
    (e.g. gpt-oss emits 'finalize_disposition<|channel|>commentary' via vLLM's generic parser)."""
    return (tc.get("function", {}).get("name") or "").split("<|")[0].strip()


def _hist(msg: dict) -> dict:
    h = {"role": "assistant"}
    if msg.get("tool_calls"):
        h["content"] = msg.get("content")
        h["tool_calls"] = msg["tool_calls"]
    else:
        h["content"] = msg.get("content") or ""
    return h


def generate_trajectory(env: Environment, agent, customer, persona: dict, pack, max_steps: int = 24) -> dict:
    """Run one LLM customer <-> LLM agent <-> code-env conversation for a given pack.

    Returns {"log": env.log, "transcript": agent_msgs, "terminal_reason": <str>}.
    """
    tool_specs = {t["function"]["name"]: t["function"] for t in pack.agent_tool_specs}
    agent_msgs = [{"role": "system", "content": agent_system_prompt(pack)}]
    cust_msgs = [{"role": "system", "content": customer_system_prompt(persona)}]

    opener = customer.complete(cust_msgs + [{"role": "user", "content": "Begin the call with your request."}])
    opener_text = opener.get("content") or ""
    cust_msgs.append({"role": "assistant", "content": opener_text})
    agent_msgs.append({"role": "user", "content": opener_text})
    env.apply({"action": "message", "role": "customer", "text": opener_text})  # log the customer turn

    terminal_reason = "max_steps"
    steps = 0
    while steps < max_steps:
        msg = agent.complete(agent_msgs, tools=pack.agent_tool_specs, parallel_tool_calls=False)
        agent_msgs.append(_hist(msg))
        tool_calls = msg.get("tool_calls") or []

        if tool_calls:
            names = [_tool_name(tc) for tc in tool_calls]
            # finalize must be the SOLE tool call in its turn (review F1).
            if "finalize_disposition" in names and len(tool_calls) > 1:
                terminal_reason = "protocol_error:finalize_not_sole_call"
                break

            stop = False
            for tc in tool_calls:
                name = _tool_name(tc)
                try:
                    args = json.loads(tc["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    terminal_reason = "protocol_error:bad_json_arguments"
                    stop = True
                    break
                err = _validate_args(name, args, tool_specs)
                if err:
                    terminal_reason = f"protocol_error:{err}"
                    stop = True
                    break

                if name == "finalize_disposition":
                    env.apply({"action": "disposition", "label": args.get("label"),
                               "risk_decision": args.get("risk_decision"),
                               "reason_codes": args.get("reason_codes", []),
                               "sar_flag": args.get("sar_flag", False)})
                    agent_msgs.append({"role": "tool", "tool_call_id": tc.get("id"),
                                       "content": json.dumps({"status": "finalized"})})
                    terminal_reason = "finalized"
                    stop = True
                    break  # TERMINAL: ignore any later calls, end the run

                try:
                    step = env.apply({"action": "tool", "tool": name, "params": args})
                except DispositionClosed:
                    terminal_reason = "protocol_error:action_after_disposition"
                    stop = True
                    break
                agent_msgs.append({"role": "tool", "tool_call_id": tc.get("id"),
                                   "content": json.dumps(step["event"]["result"])})
                steps += 1
            if stop:
                break
            continue

        # No tool calls -> assistant content is a message to the customer.
        content = msg.get("content") or ""
        env.apply({"action": "message", "role": "agent", "text": content})
        steps += 1
        cust_msgs.append({"role": "user", "content": content})
        creply = customer.complete(cust_msgs)
        ctext = creply.get("content") or ""
        cust_msgs.append({"role": "assistant", "content": ctext})
        agent_msgs.append({"role": "user", "content": ctext})
        env.apply({"action": "message", "role": "customer", "text": ctext})  # log the customer turn

    # `log` is the INTERNAL audit trace (state snapshots incl. hidden ground truth). `transcript`
    # is the model-visible thread (system/user/assistant/tool only) — review F3.
    return {"log": env.log, "transcript": agent_msgs, "terminal_reason": terminal_reason}


def generate_and_grade(pack, agent, customer, judge=None) -> tuple:
    """Generate one trajectory for `pack` and grade it against the SCENARIO's target + manifest.

    The sampler may emit different blueprints (fraud vs legitimate), each carrying its own target;
    we grade against `scenario["target"]` (falling back to the pack default). `judge` (optional) is
    the calibrated LLM judge for substrate=llm_judge policies (e.g. ATO-P13)."""
    scenario = pack.scenario()
    env = Environment(scenario, pack.tools)
    res = generate_trajectory(env, agent, customer, scenario.get("persona", {}), pack)
    target = scenario.get("target", pack.target)
    report = grade(env.log, target, pack.policies, required_ids=pack.required_policy_ids, judge=judge)
    report["terminal_reason"] = res["terminal_reason"]
    report["scenario_blueprint"] = scenario.get("blueprint")
    report["scenario_intent"] = scenario.get("intent")
    return env.log, report, res["transcript"]
