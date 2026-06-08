# APT-1 / Scaled Cognition — Deep Research (First Principles)

**Date:** 2026-06-04
**Method:** deep-research harness — 6 angles, 23 sources fetched, 106 claims extracted, 25 adversarially verified (3-vote, 2/3 to kill). **Result: 25 confirmed, 0 refuted.**
**Purpose:** First-principles understanding of agentic-pretraining + synthetic-data construction, to transfer into a PayPal fraud (and commerce) synthetic-data "factory."

---

## ⚠️ The hard boundary: documented vs inferred

**Everything concrete about APT-1 itself is first-party marketing.** Scaled Cognition has published *no* audited disclosure of APT-1's architecture, parameter count, training objective, agentic-pretraining mechanics, or synthetic-data structure. The transferable "how" below comes **entirely from independent academic papers** (Salesforce, Tencent, Microsoft, Eigen AI, Sierra) that do **not** mention APT-1. Treat these as first-principles inference of *what they are likely doing*, not disclosures.

---

## 1. What is documented about Scaled Cognition / APT-1 (high confidence)

- **Founders / pedigree:** Dan Roth (CEO), Dan Klein (CTO, UC Berkeley professor), Damon Pender (CFO). Same team behind **Semantic Machines** (acquired by Microsoft 2018) → deep conversational-AI lineage. [scaledcognition.com/about, LinkedIn, theorg.com]
- **APT-1 positioning:** flagship "Agentic Pretrained Transformer," reportedly built for **under $11M** by a **~20-person** team. Launched **Feb 12, 2025** as a *research preview*. Positioned for production CX agents that follow business policy, execute actions, and avoid hallucination. [scaledcognition.com, getcoai, together.ai]
- **"Pass100" reliability standard:** their self-defined bar = the *same correct answer across 100 identical scenarios* (consistency, not just accuracy). This is **company terminology, not an industry metric.**
- **Partnership:** Genesys (Oct 2025) for agentic CX orchestration.
- **NOT substantiated:** any specific banking/finance or fraud capability beyond generic "powers production CX agents." The `/industries/banking-and-finance` page yielded no verifiable specific capability. Pass100 results and any benchmark leadership are **not independently audited.**

**Takeaway:** APT-1 is a **motivating market signal, not an independently verified result** — the *claim* is that a small team reached strong *agentic reliability* for a fraction of the cost by specializing on policy-following + action execution + consistency, but benchmark leadership and "Pass100" are not independently audited. The implementable blueprint therefore comes from the independent agent-eval and synthetic-data literature, not from APT-1 disclosures; the plausible moat is a **data factory**, which we reconstruct from first principles.

---

## 2. The transferable blueprint (first-principles, from the literature)

The literature converges on a coherent recipe for an agentic synthetic-data factory. Mapped to your four axes:

### BREADTH — task/domain/intent coverage
- **APIGen-MT** (Salesforce, NeurIPS 2025, arXiv:2504.03601): two-phase pipeline. **Phase 1** generates task *blueprints* with ground-truth actions, validated by rule-based checks + a **committee of LLM reviewers** with iterative feedback. **Phase 2** turns blueprints into full trajectories via simulated human-agent interplay + rejection sampling. Models trained on this (xLAM-2, 1B-70B) **beat GPT-4o** on tau-bench and BFCL multi-turn — *small models trained on good synthetic data beat raw scale.* This is the central breadth+verifiability mechanism.
- **Persona Hub** (Tencent, arXiv:2406.20094): ~**1 billion personas** auto-curated from web ("distributed carriers of world knowledge"). Drives breadth/diversity by tapping nearly every perspective. (Caveat: coverage is aspirational; bias/privacy/depth limits documented.)

### DEPTH — trajectory length / multi-turn / long-horizon tool use
- **tau-bench** (Sierra, arXiv:2406.12045): dynamic multi-turn conversations between an LLM-simulated user and an agent with domain API tools + **explicit policy guidelines**; graded by **comparing final database state to an annotated goal state**. SOTA agents (GPT-4o mid-2024) passed **<50%** of tasks, pass^8 **<25%** in retail — empirical proof of the reliability gap Pass100 targets.
- **tau2-bench** (Sierra, arXiv:2506.07982): **dual-control Dec-POMDP** — *both* agent and user act on shared state; performance drops sharply single→dual control. **Directly relevant to fraud:** an agent that must *coach the customer to act* (verify identity, confirm/reverse a transaction) is a distinct, harder capability.

### DIVERSITY — persona/scenario/edge-case/adversarial variation
- Persona-driven generation (above) + **EigenData** (Eigen AI — *separate company, not APT-1*, arXiv:2601.22607): self-evolving hierarchical multi-agent pipeline producing task specs, tool traces, dialogues, and **checkers**; auto-critiques and feeds structured feedback back to worker prompts and workflow plans. Difficulty knobs (seeds) govern **# tool calls, branching, ambiguity, error-prone params**; a **TaskValidationAgent** runs a tool-grounded feasibility probe ("Execute, Don't Assume") before accepting a task.

### ACTION / POLICY / STATE representation — the core
- **Explicit state objects** (arXiv:2601.15290): task state = two structured objects **T_current** (confirmed items) and **T_target** (desired final state), with **monotonic update constraints** (only add/remove, never implicit mutation) and completion test **T_current ⊇ T_target**. Persona/behavior = a **discrete attribute vector** `{mood_tone, task_execution_style, exploration_style, task_completion_status}` generated per response. This is the most directly transferable answer to action/policy/state supervision.
- **Multi-agent user simulator** (same paper): decompose simulation into a **User Agent** (orchestration), a **State Tracking Agent** (structured task state), and a **Message Attributes Generation Agent** (per-persona behavior).
- **Simia** (Microsoft, arXiv:2511.01824): reasoning models **simulate the environment** (state transitions + tool interactions) **without real APIs**. Simia-SFT anchors generation to **formal tool/API specs embedded in the prompt** (keeps actions valid); Simia-RL uses the LLM simulator as both environment feedback **and reward**. Qwen2.5-32B fine-tuned on simulated trajectories surpassed GPT-4o and xLAM-2-70B on tau2-bench.

### Policy adherence & verifiable reward
- Supervision target = **verifiable final-state outcome** (tau-bench) + **executable state-based reward functions** (Simia-RL, EigenData checkers). **Key caveat for fraud:** state-based grading only *partially* captures policy adherence — an agent can pass while violating a policy that left no DB trace. Compliance/guardrail violations in fraud may be exactly this kind. So we need **explicit policy-violation checkers**, not just final-state diff.

---

## 3. Open questions (unresolved — genuinely opaque)
1. APT-1's actual architecture, size, training objective; what "agentic pretraining" does differently from pretraining + RLHF.
2. APT-1's concrete banking/finance + fraud offerings and how it encodes/enforces compliance guardrails.
3. Scaled Cognition's real data-factory methodology and how close it is to the APIGen-MT / persona / simulator / verifiable-reward patterns above.
4. Whether Pass100 or any benchmark leadership has been independently reproduced.

---

## 4. Sources (primary unless noted)
- Scaled Cognition: /about, /ai-info, /blog/apt-1, /industries/banking-and-finance (primary, marketing)
- APIGen-MT — arXiv:2504.03601 · Persona Hub — arXiv:2406.20094 · Multi-agent state sim — arXiv:2601.15290 · Simia — arXiv:2511.01824 · EigenData — arXiv:2601.22607 (Eigen AI, distinct) · tau-bench — arXiv:2406.12045 · tau2-bench — arXiv:2506.07982
- Microsoft/Semantic Machines acquisition (2018); Genesys partnership (Oct 2025); Together AI customer page; getcoai
