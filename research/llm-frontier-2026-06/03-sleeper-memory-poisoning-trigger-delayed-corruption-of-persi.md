# Sleeper Memory Poisoning: Trigger-Delayed Corruption of Persistent Agent Memory

**Research window:** April 2026 – June 2026 (compiled 2026-06-03)

**Executive summary.** A new attack class crystallized in May 2026 with the paper *Hidden in Memory: Sleeper Memory Poisoning in LLM Agents* (arXiv:2605.15338, v1 May 14 / v2 May 18 2026). It demonstrates that a *single* exposure to adversarial external content (a document, webpage, dispute message, or repository the agent merely reads) can cause a stateful LLM assistant to silently write a *fabricated* memory into its persistent store. That memory lies dormant until a future, attacker-absent session retrieves it via ordinary semantic similarity, at which point it steers the agent's behavior toward an attacker goal. Reported injection rates reach 99.8% on GPT-5.5 and 95% on Kimi-K2.6; among relevant ("goal-adjacent") future queries, retrieved poison drives attacker-intended agentic actions in 60–89% of cases, with decoupled end-to-end success of roughly 41–73.9%. Defenses are only partially effective: GEPA-optimized prompt hardening and spotlighting collapse under adaptive attack on some models, and while activation-probing / LLM document scanners reach >0.95 AUROC for detection, they transfer poorly across models. The work supersedes the query-only MINJA line (arXiv:2601.05504 / 2503.03704) and the single-shot MemoryGraft (arXiv:2512.16962), and lands alongside OWASP's 2026 Agentic Top-10 ASI06 (Memory & Context Poisoning), the Mnemonic Sovereignty survey (arXiv:2604.16548), and Memory Control Flow Attacks (arXiv:2603.15125). The honest caveat: nearly all results are research-bench and decoupled-pipeline; there are no documented real-world CVEs against commercial memory features in this window, though manual confirmations on production web UIs (ChatGPT-5.4, Claude Sonnet 4.6, Kimi-K2.6) were reported at 88–96% success.

---

## What's New in the Window

The April–June 2026 window contains the first concentrated body of work treating *persistent, runtime-writable agent memory* as a primary, durable attack surface rather than a session-bound nuisance.

- **Hidden in Memory: Sleeper Memory Poisoning in LLM Agents** — arXiv:2605.15338, v1 2026-05-14, v2 2026-05-18. Authors: Sidharth Pulipaka, Stanislau Hlebik, Leonidas Raghav, Sahar Abdelnabi, Vyas Raina, Ivaxi Sheth, Mario Fritz (the author set overlaps the CISPA Helmholtz / indirect-prompt-injection research lineage of Abdelnabi and Fritz). This is the centerpiece of the window: the first systematic, *trigger-delayed, cross-session, single-exposure, black-box external-content* memory-poisoning study at scale. Abstract/HTML: https://arxiv.org/abs/2605.15338 and https://arxiv.org/html/2605.15338v2. A code/eval-data artifact is referenced (the `ivaxi0s` / agent-memory-poisoning lineage).

- **A Survey on the Security of Long-Term Memory in LLM Agents: Toward Mnemonic Sovereignty** — arXiv:2604.16548v1, 2026-04-17. Authors: Zehao Lin, Chunyu Li, Kai Chen (MemTensor, Shanghai). Provides the taxonomy that contextualizes sleeper poisoning: a six-phase memory lifecycle (Write, Store & Manage, Retrieve, Execute, Share & Propagate, Forget/Rollback) crossed against four security objectives (Integrity, Confidentiality, Availability, Governance). Notably, it flags that trigger-delayed / sleeper scenarios are *not yet* a mature, well-studied subfield — confirming arXiv:2605.15338's novelty. https://arxiv.org/html/2604.16548v1

- **OWASP Top 10 for Agentic Applications (2026), ASI06: Memory & Context Poisoning** — the standards anchor. The OWASP GenAI Security Project's 2026-05-13 essay "Memory Is a Feature. It Is Also an Attack Surface" frames the threat and uses the **MemoryTrap** vulnerability in Claude Code as a worked example (a one-time repo/dependency action persisting into global hooks and the system-prompt instruction layer across sessions and reboots). https://genai.owasp.org/2026/05/13/memory-is-a-feature-it-is-also-an-attack-surface/ ; project landing: https://owasp.org/www-project-agent-memory-guard/

- **From Storage to Steering: Memory Control Flow Attacks on LLM Agents** — arXiv:2603.15125v1, 2026-03-16 (just outside the strict window but actively cited in May coverage). Authors: Zhenlin Xu, Xiaogang Zhu, Yu Yao, Minhui Xue, Yiliao Song. Shows poisoned memory hijacks *tool selection/order* (control flow), not just content — Override attacks at 91.7–100%, cross-task propagation 97.2–100%. https://arxiv.org/html/2603.15125v1

- **Prompt Persistence Attacks: Long-Term Memory Poisoning in LLM-Based Systems** — Pranav Bhatnagar (SSRN/ResearchGate, 2026). A companion framing emphasizing *incremental, sub-detection-threshold* memory shaping over long horizons. https://papers.ssrn.com/sol3/Delivery.cfm/5995215.pdf?abstractid=5995215

- **Industry inflection coverage** — "When Memory Became the Attack Surface: The May 2026 AI Agent Security Inflection" (LLMS3, 2026-05-28) documents the research-to-defense pipeline, including **OWASP Agent Memory Guard** middleware (SHA-256 write validation, anomaly detection, composite trust scoring with temporal decay, forensic snapshots/rollback). https://llms3.com/blog/when-memory-became-the-attack-surface-may-2026

**Prior art being superseded:**
- **MINJA** (A Practical Memory Injection Attack), arXiv:2503.03704 / and the defense-paired arXiv:2601.05504 ("Memory Poisoning Attack and Defense on Memory-Based LLM-Agents"): query-only injection via "bridging steps" + "progressive shortening," >95% injection / ~70% attack success — but assumes *repeated multi-turn interaction* by the attacker.
- **MemoryGraft** (arXiv:2512.16962): single-shot, indirect, semantic-similarity-activated grafting into RAG experience stores — closest precursor, but framed around experience/trajectory memory rather than user-profile memory and without the universal-payload optimization or the activation-probe defense analysis.

---

## Technical Deep-Dive

### Threat model

The adversary is **black-box and external-content-only**: no access to model weights, system prompts, the memory subsystem's internals, or any future conversation. The attacker controls only some piece of context the victim agent will ingest — a webpage, an uploaded document, an email, a code repository, a support-chat message. This is materially weaker (hence more realistic) than MINJA's repeated query interaction or white-box corpus-editing assumptions.

### The three-stage success condition

The paper formalizes success as the conjunction of three events (its Eqs. 4–6):

1. **Injection** — the adversarial document `d_adv` induces a memory write: `m_adv ∈ W(q, d_adv, M)`, where `W` is the agent's write function over query `q`, document, and current memory `M`.
2. **Retrieval** — in a *later, separate* session `U'` with memory `M'`, the poisoned memory surfaces: `m_adv ∈ R(U', M')`.
3. **Adversarial usage** — the retrieved memory steers the response/action toward the attacker's goal.

The product of the three creates the defining "one-to-many" property: one injection event can influence many downstream sessions, and the attacker need not be present when the payload fires. This is precisely the "sleeper" property — dormancy across sessions, then trigger-on-retrieval.

### Mechanism 1 — Universal payload via Actor–Critic search

Rather than hand-crafting a payload per document, the attack searches for a *reusable template* `P_adv(m_adv)` effective across many (document, goal) pairs:

- An **attacker LLM (actor)** proposes candidate payload templates.
- Each is scored on a batch of (document, goal) pairs.
- A **critic LLM** inspects failures and emits feedback.
- Iterate up to `K` refinement steps; retain high performers; select on held-out evaluation.

The output is a transferable injection string that, embedded in benign-looking content, reliably coaxes the agent's memory-write step into persisting an attacker-chosen "fact about the user."

### Mechanism 2 — Retrieval-aware memory rewriting

To survive dormancy and *re-emerge*, the payload is phrased to maximize semantic similarity to plausible future queries (its Eq. 8):

```
m̃*_adv = argmax  Σ_q  sim( e(m̃_adv), e(q) )
```

where `e(·)` is the embedding used by the memory retriever and the sum runs over anticipated future queries `q`. This explicitly engineers the poison to be retrieved by similarity-based memory systems without any attacker presence later — the key advance over content-only poisoning that ignores retrievability.

### What changed vs prior art

- **vs MINJA / 2601.05504:** drops the requirement for repeated attacker queries and bridging-step shortening; a single external document suffices, and the payload is universal rather than query-specific.
- **vs MemoryGraft:** adds the universal Actor–Critic optimizer, the explicit retrieval-aware rewriting objective, evaluation against *user-profile* memory (not only experience/RAG stores), and a full mechanistic + defense study (activation probes, document scanners).
- **vs Memory Control Flow Attacks (2603.15125):** sleeper poisoning targets *what the agent believes* (content/behavior); MCFA targets *which tools fire and in what order* (control flow). They are complementary corruption channels on the same persistent-memory substrate.

### Mechanistic findings

Injected examples produce strongly **separable activation signatures in middle-to-late decoder layers**, indicating the attack is reflected in the model's internal handling of the memory-write objective, not a shallow tokenization artifact. Attention analysis shows successful attacks correlate with **higher attention mass on the adversarial payload**, but attention is necessary-not-sufficient: some models attend strongly yet refuse to comply (notably Claude Sonnet 4.6). Architecture matters — models with alternating local/global attention show sharp global-layer separations, while dense-attention models show smoother early-layer separation between successful and failed injections.

---

## Evidence & Benchmarks

**Models evaluated:** GPT-5.4, GPT-5.5, Gemini-3.1-Pro, Claude Sonnet 4.6, Kimi-K2.6, DeepSeek-V4-Pro. Two memory regimes were tested: a **tool-based** write regime (the model decides to call a write tool) and an **external memory-manager** regime (a separate component decides what to persist).

**Injection Rate (IR), Table 1:**
- Tool-based, GPT-5.5: **99.8%** (LLM-behavior objective), 91.5% (agent-action objective).
- Tool-based, Kimi-K2.6: **95.0%** behavior, 81.0% agent-action.
- Claude Sonnet 4.6: **64.2%** behavior but only **6.5%** agent-action — substantially more robust, especially at the action level.
- External-manager regime, GPT-5.5: 75.0% behavior, 46.5% agent-action (the manager layer lowers but does not eliminate injection).

**Retrieval Rate (RR) and Adversarial Usage Rate (AUR), Table 2 — the proximity effect:**
- **Goal-adjacent** future queries (poison resembles useful task context): RR 90–95% (behavior) / 94–98% (agent-action); AUR 42–85% (behavior) / **60–89% (agent-action)**.
- **Goal-distant** queries: RR collapses to 3–8% / 13–18%; AUR ~0–6% / 6–17%.
- Interpretation: poison is dangerous precisely when it is *topically relevant* to what the user later asks — it hides among genuinely useful memories. This is the most important practical nuance and also a natural limiter.

**End-to-end (coupled) success, Appendix I:** single-attack, external-manager retrieval, goal-adjacent — **41.0–73.9%** for the LLM-behavior objective and up to ~66% for agent-action. Most headline numbers (IR/RR/AUR) are reported *decoupled* to isolate where failures occur; the coupled product is the honest end-to-end figure.

**Production confirmation (manual):** ChatGPT-5.4 24/25 (96%), Claude Sonnet 4.6 24/25 (96%), Kimi-K2.6 22/25 (88%) on live web interfaces — small-n but notable.

**Defenses tested:**
- *Naive prompt hardening:* wildly unstable, 0–96.8% residual IR depending on model.
- *GEPA (evolutionary) hardening:* near-zero IR on Claude/Gemini (0–0.2%), but under adaptive attack Kimi-K2.6 jumps 6.2%→64.6% and DeepSeek-V4 0.4%→25.2%. Conclusion: not model-agnostic, not adaptation-robust.
- *Extreme spotlighting* (`<untrusted_content>` wrapping + reminders): 4.6–84% IR reduction, inconsistent.
- *Hybrid hardening+spotlighting:* similarly variable.
- *LLM document scanner / activation probing (detection):* single-layer probes 0.93–0.99 AUROC; multi-layer fused often **>0.95**; a Gemma-4-26B scanner achieves >0.96 payload-localization. **But** cross-model transfer is weak — shared-PCA alignment 0.48–0.54 AUROC; Orthogonal-Procrustes alignment 0.74–0.85; target-native ceiling 0.77–0.88. Probes must be trained per target model.

**Limitations and contested points (stated and inferred):**
- Metrics are *decoupled by design*; the true operational risk is the coupled product, which is meaningfully lower than the 99.8% headline.
- Retrieval analysis assumes semantic-similarity or LLM-managed retrieval; keyword/temporal/hybrid retrievers are untested and could change RR substantially.
- Memory-pool density (sparse vs crowded stores) was not swept; real stores with many competing memories may dilute poison.
- Only six current frontier models; generalization to future architectures is asserted, not proven.
- Goal taxonomy (~15 document sources, ~13 adversarial goal categories) is broad but non-exhaustive.
- No documented in-the-wild exploitation or CVE in this window; production claims rest on manual UI tests, not telemetry from real attacks.

---

## Maturity Assessment

**Stage: research-grade, rapidly standardizing — not yet a documented production incident class.** The science is strong and reproducible-in-principle (formal objective, released artifacts, manual production confirmations), and it has *already crossed into standards*: OWASP's 2026 Agentic Top-10 lists ASI06 Memory & Context Poisoning, and an open-source defense (OWASP Agent Memory Guard) exists with concrete primitives. That said:

- **Compute/data:** The attack itself is cheap — the Actor–Critic search is a handful of LLM calls to derive a universal template, then zero-cost reuse. The *defense* side (activation probing) needs per-model probe training on labeled benign/injected activations, plus a document-scanner model (e.g., Gemma-4-26B) inline — non-trivial latency and ops cost.
- **Reproducibility:** Artifact references exist and the math/threat model are fully specified; the chief reproducibility risk is that frontier model versions (GPT-5.5, Kimi-K2.6, etc.) drift, and that vendors may have already partially hardened memory-write paths since the manual tests.
- **Realism gradient:** Highest-credibility claims are *injection* into tool-based write regimes; *end-to-end* operational impact (41–73.9%, goal-adjacent only) is real but conditional. The proximity effect means an attacker needs to anticipate the victim's future query topic — a real but non-trivial constraint.
- **Net:** Treat as an imminent, design-level threat to *any* system with runtime-writable persistent entity/profile memory, not a hypothetical. Defenses should be layered now; do not rely on prompt hardening alone.

---

## PayPal Fraud/Risk Implications

PayPal's Fraud & Risk stack increasingly leans on **cross-session entity memory** (per-account, per-merchant, per-device "what we know about this entity") and on **agentic investigation/case-review workflows** that ingest free text from disputes, merchant descriptions, support chats, and KYC documents. That is exactly the substrate this attack targets. Concrete implications:

1. **The fraudster's playbook becomes a *delayed* one.** Today's indirect prompt injection mostly bites within a session. Sleeper poisoning lets an adversary seed benign-looking content — a dispute narrative, a merchant "about us" blurb, an uploaded KYC PDF, a support-chat line — that an investigation agent *summarizes and persists* as an entity memory ("this merchant is a verified low-risk reseller," "this account holder previously cleared manual review"). Weeks later, when an analyst-agent pulls up that entity, the planted memory nudges it to **whitelist, lower a risk score, or auto-approve** — with the attacker long gone. The goal-adjacency/proximity effect is *worse* here, not better: investigation queries are highly predictable ("is this account high risk?", "should this dispute be granted?"), so an attacker can phrase poison to maximize retrieval against exactly those queries.

2. **Persisted entity-memory writes are the choke point — gate them.** The single highest-value control is **write-time provenance + sanitization** on any agent-derived entity memory. Every persisted memory should carry source metadata (which document/channel produced it, ingestion timestamp, trust tier of the source), and externally-sourced claims should never be promoted to "verified fact" without an independent corroboration path. This mirrors OWASP ASI06's mitigations (provenance tracking, per-tenant segmentation, expiry of unverified data) and the Mnemonic Sovereignty survey's "validate provenance before write" primitive.

3. **Activation-probe / document-scan monitors on the write path.** The paper's >0.95 AUROC detector and >0.96 payload localization are directly deployable as an *inline write-time gate*: before an investigation agent persists a memory derived from untrusted text, run a probe/scan on the source span. Because probes transfer poorly across models, PayPal would train per-model probes against whatever LLM backs the investigation agent — feasible given an in-house, version-pinned model. Latency budget: this is *not* on the sub-100ms real-time scoring path; it belongs on the asynchronous memory-write/consolidation path where a few hundred ms is acceptable.

4. **Separate "real-time scoring" from "agentic memory."** The sub-100ms transaction scorer should *not* read free-form, agent-writable narrative memory as a feature without a trust gate. Keep poisoned-narrative risk out of the latency-critical path; let graph/sequence/tabular signals drive real-time decisions and confine agent-written memory to the slower investigative tier where it can be provenance-checked.

5. **Graph and propagation amplification.** PayPal's graph (accounts ↔ devices ↔ IPs ↔ merchants) makes the "one-to-many" property dangerous: a single poisoned merchant memory could propagate trust along graph edges to linked entities, and the Mnemonic Sovereignty survey's "social/shared-store contagion" warning applies directly to shared organizational memory used across analysts. Mitigate with **per-entity memory isolation, provenance-weighted retrieval (composite trust scoring with temporal decay)**, and explicit blocking of trust-transfer from low-provenance memories.

6. **Control-flow variant matters for tool-using investigation agents.** The companion Memory Control Flow Attacks (2603.15125, Override 91.7–100%) means poisoned memory could also hijack *which investigative tools an agent invokes* (e.g., skip a sanctions check, reorder steps to grant a dispute before verification). Role-based memory segregation helped but left 8.3–63.9% residual — so segregation must be paired with write-time validation, not used alone.

7. **Explainability/auditability angle (regulatory).** Every risk decision an agent makes from memory must be traceable to the *source* of that memory. Provenance tags double as the audit trail regulators expect: "this account was de-risked because of memory X, which originated from untrusted source Y on date Z" is both a defense and a compliance artifact. Forensic snapshots / rollback (OWASP Agent Memory Guard) give a remediation path when a poisoned memory is later identified.

8. **Adversarial-drift framing.** Treat memory poisoning as adversarial *drift in the agent's belief state*, analogous to feature drift in the scorer. Monitor for sudden memory-driven risk-score deltas on an entity that aren't supported by transaction-graph evidence — a memory says "low risk" while behavioral/sequence signals say otherwise is a high-value detection signal and a probe-trigger.

**Bottom line for PayPal:** the actionable controls are (a) provenance tags on every agent-persisted entity memory, (b) write-time sanitization + per-model activation/document-scan gating on memory writes from untrusted text, (c) provenance-weighted, temporally-decayed retrieval with per-entity isolation, (d) strict separation of agent-writable narrative memory from the real-time sub-100ms scorer, and (e) memory-vs-graph-signal contradiction monitors. None of these depend on the headline 99.8% being operationally real — they are justified even at the more honest 41–73.9% end-to-end, goal-adjacent figure.

---

## Sources

- Hidden in Memory: Sleeper Memory Poisoning in LLM Agents — arXiv:2605.15338 — https://arxiv.org/abs/2605.15338 ; HTML v2 https://arxiv.org/html/2605.15338v2
- A Survey on the Security of Long-Term Memory in LLM Agents: Toward Mnemonic Sovereignty — arXiv:2604.16548v1 — https://arxiv.org/html/2604.16548v1
- OWASP GenAI Security Project, "Memory Is a Feature. It Is Also an Attack Surface" (ASI06), 2026-05-13 — https://genai.owasp.org/2026/05/13/memory-is-a-feature-it-is-also-an-attack-surface/
- OWASP Agent Memory Guard project — https://owasp.org/www-project-agent-memory-guard/
- OWASP Top 10 for Agentic Applications (2026), launch post — https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/
- From Storage to Steering: Memory Control Flow Attacks on LLM Agents — arXiv:2603.15125v1 — https://arxiv.org/html/2603.15125v1
- Memory Poisoning Attack and Defense on Memory-Based LLM-Agents — arXiv:2601.05504 — https://arxiv.org/abs/2601.05504 ; PDF https://arxiv.org/pdf/2601.05504
- A Practical Memory Injection Attack against LLM Agents (MINJA) — arXiv:2503.03704 — https://arxiv.org/abs/2503.03704
- MemoryGraft: Persistent Compromise of LLM Agents via Poisoned Experience Retrieval — arXiv:2512.16962 — https://ar5iv.labs.arxiv.org/html/2512.16962 ; PDF https://arxiv.org/pdf/2512.16962
- Prompt Persistence Attacks: Long-Term Memory Poisoning in LLM-Based Systems (Bhatnagar, SSRN) — https://papers.ssrn.com/sol3/Delivery.cfm/5995215.pdf?abstractid=5995215
- When Memory Became the Attack Surface: The May 2026 AI Agent Security Inflection (LLMS3, 2026-05-28) — https://llms3.com/blog/when-memory-became-the-attack-surface-may-2026
- SuperLocalMemory: Privacy-Preserving Multi-Agent Memory with Bayesian Trust Defense Against Memory Poisoning — arXiv:2603.02240 — https://arxiv.org/pdf/2603.02240
