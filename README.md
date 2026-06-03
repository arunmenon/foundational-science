# Foundational Science — Frontier LLM Research

A reusable, checkpointed research pipeline that scans bleeding-edge LLM advances
and turns them into runnable experiment hypotheses for a fraud/risk context.

## Pipeline

The workflow ([`.claude/workflows/llm-frontier-research.js`](.claude/workflows/llm-frontier-research.js))
runs in three phases, one invocation each, with a human checkpoint between them:

1. **Discover** — six `deep-researcher` scouts (architecture, attention, memory,
   efficiency/inference, reasoning/RL, agents) sweep the last ~2 months and surface
   candidate topics, each scored on novelty and fraud/risk relevance.
2. **DeepDive** — one `deep-researcher` per approved topic writes a full,
   source-grounded report.
3. **Synthesize** — a `master-orchestrator` reads every report and produces a
   prioritized, falsifiable experiment slate.

## Contents

| Path | What |
| ---- | ---- |
| `.claude/workflows/llm-frontier-research.js` | The reusable phase-routed workflow |
| `research/llm-frontier-2026-06/00-experiment-slate.md` | Synthesized experiment slate |
| `research/llm-frontier-2026-06/01-18-*.md` | 18 deep-dive reports |

## Window

This run covers **April–June 2026**.
