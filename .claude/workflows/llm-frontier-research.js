export const meta = {
  name: 'llm-frontier-research',
  description: 'Frontier-LLM research pipeline: discover topics, deep-dive each, synthesize fraud/risk experiment hypotheses. Run one phase per invocation (human checkpoints between).',
  whenToUse: 'Monthly scan of bleeding-edge LLM advancements (architecture, attention, memory, efficiency, reasoning/RL, agents) mapped to fraud/risk experiments. Invoke with args.phase = discover | deepdive | synthesize. Pass args.domainContext to target a specific platform.',
  phases: [
    { title: 'Discover', detail: 'One researcher per frontier area surfaces candidate topics from the last ~2 months' },
    { title: 'DeepDive', detail: 'One deep-researcher per approved topic writes a persisted report' },
    { title: 'Synthesize', detail: 'Read all reports, produce Fraud/Risk experiment hypotheses' },
  ],
}

// ---------- configuration (overridable via args) ----------
// args may arrive as a real object OR as a JSON-encoded string depending on the caller; handle both.
let config = {}
if (args && typeof args === 'object') {
  config = args
} else if (typeof args === 'string' && args.trim()) {
  try { config = JSON.parse(args) } catch (parse_error) { config = {} }
}
const phase_to_run = config.phase || 'discover'
const output_directory = config.outDir
  || '/Users/arunmenon/projects/Foundation-Science/research/llm-frontier-2026-06'
const research_window = config.window || 'the last 2 months (April 2026 through June 2026)'
const today = config.today || '2026-06-03'
// Domain context used to score relevance and frame the synthesis. Override via args.domainContext
// to target a specific platform; the default is a generic payments fraud & risk ML setting.
const fraud_risk_context = config.domainContext || `Domain context for relevance scoring: a payments fraud & risk
ML platform. This includes real-time transaction risk scoring (sub-100ms latency, extreme class imbalance,
adversarial/evolving fraud patterns), account-takeover and bot detection, behavioral/sequence modeling of user
and payment-event streams, graph-structured relationships (accounts, devices, IPs, merchants), entity memory
across sessions, tabular + text + sequence multimodal signals, model explainability/auditability for regulatory
review, and investigative/agentic workflows for case review. When scoring relevance, prefer advances that
plausibly improve fraud detection accuracy, lower scoring latency/cost, strengthen long-horizon entity memory,
harden against adversarial drift, or enable agentic investigation.`

// ---------- schemas ----------
const CANDIDATE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    area: { type: 'string', description: 'The frontier area this researcher covered' },
    topics: {
      type: 'array',
      description: 'Candidate deep-dive topics surfaced from the research window',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          title: { type: 'string', description: 'Concise, specific topic title' },
          summary: { type: 'string', description: '2-3 sentence description of the advancement' },
          whyFrontier: { type: 'string', description: 'What specifically is new in the research window; name papers/models/releases and approximate dates' },
          keyDevelopments: { type: 'array', items: { type: 'string' }, description: 'Specific papers, models, or releases (with venue/lab if known)' },
          sources: { type: 'array', items: { type: 'string' }, description: 'URLs or arXiv IDs' },
          fraudRiskRelevance: { type: 'string', description: 'Concrete hypothesis for how this could matter to fraud/risk' },
          noveltyScore: { type: 'integer', minimum: 1, maximum: 5, description: '5 = brand-new frontier in the window; 1 = incremental' },
          fraudRelevanceScore: { type: 'integer', minimum: 1, maximum: 5, description: '5 = directly actionable for fraud/risk; 1 = tangential' },
        },
        required: ['title', 'summary', 'whyFrontier', 'fraudRiskRelevance', 'noveltyScore', 'fraudRelevanceScore'],
      },
    },
  },
  required: ['area', 'topics'],
}

const DEEPDIVE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    title: { type: 'string' },
    reportPath: { type: 'string', description: 'Absolute path of the markdown report this agent wrote' },
    wrote: { type: 'boolean', description: 'True if the report file was successfully written' },
    summary: { type: 'string', description: '3-4 sentence executive summary' },
    keyFindings: { type: 'array', items: { type: 'string' } },
    fraudRiskHooks: { type: 'array', items: { type: 'string' }, description: 'Specific hooks into the fraud/risk domain' },
  },
  required: ['title', 'reportPath', 'wrote', 'summary'],
}

const SYNTHESIS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    slatePath: { type: 'string', description: 'Absolute path of the written experiment-slate markdown' },
    wrote: { type: 'boolean' },
    hypotheses: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          id: { type: 'string' },
          title: { type: 'string' },
          hypothesis: { type: 'string', description: 'Falsifiable statement: "If we apply X, then fraud/risk metric Y improves because Z"' },
          sourceTopics: { type: 'array', items: { type: 'string' } },
          experimentDesign: { type: 'string', description: 'Concrete experiment: baseline, treatment, data, offline/online' },
          datasetsOrSignals: { type: 'array', items: { type: 'string' } },
          successMetrics: { type: 'array', items: { type: 'string' }, description: 'e.g. AUC-PR at fixed FPR, recall@k, p99 latency, $ loss avoided' },
          effort: { type: 'string', enum: ['low', 'medium', 'high'] },
          expectedImpact: { type: 'string', enum: ['low', 'medium', 'high'] },
          risks: { type: 'array', items: { type: 'string' } },
        },
        required: ['id', 'title', 'hypothesis', 'experimentDesign', 'successMetrics', 'effort', 'expectedImpact'],
      },
    },
  },
  required: ['slatePath', 'wrote', 'hypotheses'],
}

// ====================================================================
// PHASE 1 — DISCOVER
// ====================================================================
if (phase_to_run === 'discover') {
  phase('Discover')
  log(`Discovering frontier LLM topics from ${research_window}. Today is ${today}.`)

  const frontier_areas = [
    {
      key: 'architecture',
      brief: 'Model architecture: new backbones, hybrid/SSM-Transformer designs, Mixture-of-Experts routing, sub-quadratic sequence models, normalization/positional-encoding advances.',
    },
    {
      key: 'attention',
      brief: 'Attention mechanisms: linear/sparse/sliding attention, latent/grouped-query variants, attention-free token mixing, hardware-aware attention kernels.',
    },
    {
      key: 'memory-long-context',
      brief: 'Model memory & long context: persistent/episodic memory, memory layers, retrieval-augmented memory, KV-cache compression for million-token context, test-time memory.',
    },
    {
      key: 'efficiency-inference',
      brief: 'Efficiency & inference: quantization, KV-cache optimization, speculative/parallel decoding, serving systems, low-latency high-throughput inference.',
    },
    {
      key: 'reasoning-rl',
      brief: 'Reasoning & RL post-training: test-time compute, RL-from-verifiable-rewards, process reward models, self-improvement, reasoning-distillation.',
    },
    {
      key: 'agents-tool-use',
      brief: 'Agentic architectures & tool use: planning, multi-agent systems, tool/function-calling reliability, long-horizon autonomy, agent memory.',
    },
  ]

  const discovery_prompt = (area) => `You are a frontier-LLM research scout. Use web search aggressively.

YOUR AREA: ${area.key}
SCOPE OF THIS AREA: ${area.brief}

TASK: Surface the 3-4 most significant, genuinely BLEEDING-EDGE advancements in this area published or released within ${research_window}. Today's date is ${today}, so only count work from that window as "frontier" — older foundational work is background only.

REQUIREMENTS:
- Run multiple targeted web searches (arXiv, lab blogs, major conferences, release notes). Prefer primary sources.
- For each topic give: a specific title, a 2-3 sentence summary, exactly what is new in the window (name papers/models/releases with approximate dates), key developments, source URLs/arXiv IDs.
- Score each topic on noveltyScore (1-5) and fraudRelevanceScore (1-5).
- For fraudRiskRelevance, write a concrete, specific hypothesis (not generic) tying the advance to fraud/risk.

${fraud_risk_context}

Return ONLY the structured object. Do not write any files.`

  const area_results = await parallel(
    frontier_areas.map((area) => () =>
      agent(discovery_prompt(area), {
        label: `scout:${area.key}`,
        phase: 'Discover',
        schema: CANDIDATE_SCHEMA,
        agentType: 'deep-researcher',
      })
    )
  )

  const all_candidate_topics = area_results
    .filter(Boolean)
    .flatMap((result) => (result.topics || []).map((topic) => ({ ...topic, area: result.area })))

  // Rank by combined novelty + fraud relevance (deterministic; no Math.random)
  const ranked_topics = all_candidate_topics
    .map((topic) => ({ ...topic, combinedScore: (topic.noveltyScore || 0) + (topic.fraudRelevanceScore || 0) }))
    .sort((first, second) => second.combinedScore - first.combinedScore)

  log(`Surfaced ${ranked_topics.length} candidate topics across ${frontier_areas.length} areas.`)

  return {
    phase: 'discover',
    window: research_window,
    outputDirectory: output_directory,
    areaCount: frontier_areas.length,
    candidateTopics: ranked_topics,
  }
}

// ====================================================================
// PHASE 2 — DEEP DIVE  (args.topics = approved topic objects or titles)
// ====================================================================
if (phase_to_run === 'deepdive') {
  phase('DeepDive')
  const approved_topics = Array.isArray(config.topics) ? config.topics : []
  if (approved_topics.length === 0) {
    throw new Error('deepdive phase requires args.topics (array of approved topics)')
  }
  log(`Deep-diving ${approved_topics.length} approved topics. Reports persist to ${output_directory}`)

  const slugify = (text) =>
    String(text).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60)

  const deepdive_prompt = (topic, index) => {
    const title = typeof topic === 'string' ? topic : topic.title
    const context_block = typeof topic === 'string'
      ? ''
      : `\nCONTEXT FROM DISCOVERY PHASE:\n- Summary: ${topic.summary || ''}\n- Why frontier: ${topic.whyFrontier || ''}\n- Key developments: ${(topic.keyDevelopments || []).join('; ')}\n- Known sources: ${(topic.sources || []).join(', ')}\n- Fraud/Risk relevance hint: ${topic.fraudRiskRelevance || ''}\n`
    const report_path = `${output_directory}/${String(index + 1).padStart(2, '0')}-${slugify(title)}.md`
    return `You are a senior LLM researcher writing a definitive deep-dive report. Use web search extensively to ground every claim.

TOPIC: ${title}
RESEARCH WINDOW: ${research_window} (today is ${today}).
${context_block}
${fraud_risk_context}

WRITE A COMPREHENSIVE MARKDOWN REPORT and SAVE IT to exactly this absolute path using the Write tool:
${report_path}

The report MUST contain these sections:
1. # Title and a one-paragraph executive summary
2. ## What's New in the Window — the specific papers/models/releases (with dates, labs, arXiv IDs/links)
3. ## Technical Deep-Dive — how it works, key mechanisms, math/architecture where relevant, what changed vs prior art
4. ## Evidence & Benchmarks — reported results, ablations, limitations, open questions, contested claims
5. ## Maturity Assessment — research-only vs production-ready, compute/data requirements, reproducibility
6. ## Fraud/Risk Implications — concrete, specific ways this could apply (latency, accuracy, memory, adversarial robustness, graph/sequence signals, explainability)
7. ## Sources — full list of URLs/arXiv IDs actually used

Ground claims in primary sources; cite inline. Be specific and technical, not generic. Be honest about uncertainty and hype.

After writing the file, return the structured object (set wrote=true and reportPath to the exact path above).`
  }

  const reports = await pipeline(
    approved_topics,
    (topic, _original, index) =>
      agent(deepdive_prompt(topic, index), {
        label: `deep-dive:${slugify(typeof topic === 'string' ? topic : topic.title)}`,
        phase: 'DeepDive',
        schema: DEEPDIVE_SCHEMA,
        agentType: 'deep-researcher',
      })
  )

  const written = reports.filter(Boolean)
  log(`Completed ${written.length}/${approved_topics.length} deep-dive reports.`)

  return {
    phase: 'deepdive',
    outputDirectory: output_directory,
    reports: written,
  }
}

// ====================================================================
// PHASE 3 — SYNTHESIZE  (read all reports -> Fraud/Risk experiment slate)
// ====================================================================
if (phase_to_run === 'synthesize') {
  phase('Synthesize')
  const slate_path = config.slatePath || `${output_directory}/00-experiment-slate.md`
  log(`Synthesizing fraud/risk experiment slate from reports in ${output_directory}`)

  const synthesis_prompt = `You are a principal applied scientist on a fraud & risk team. You have a folder of frontier-LLM deep-dive reports and must turn them into a prioritized, runnable experiment slate.

STEP 1 — READ EVERY REPORT: List and read all markdown files in this directory (use Glob then Read):
${output_directory}
(Read every *.md report except any file starting with "00-". There may be ${config.reportCount || 'several'} reports.)

${fraud_risk_context}

STEP 2 — SYNTHESIZE: Produce a set of 8-15 actionable, FALSIFIABLE hypotheses. Each must be a real experiment a fraud/risk team could run. Span quick wins and ambitious bets. For each hypothesis provide:
- A falsifiable statement ("If we apply X, then metric Y improves because Z")
- Which source topics/reports it draws from
- A concrete experiment design (baseline, treatment, offline vs online/shadow, data needed)
- Datasets/signals (e.g. transaction event streams, device graph, ATO labels, chargeback labels)
- Success metrics appropriate to fraud (AUC-PR at fixed low FPR, recall@k, p99 scoring latency, $ loss avoided, alert precision)
- Effort (low/medium/high) and expected impact (low/medium/high) and key risks

STEP 3 — WRITE THE SLATE as markdown and SAVE to exactly this absolute path using the Write tool:
${slate_path}

The slate document MUST contain:
- # Title + executive summary (top 3 recommended bets and why)
- ## Prioritization Matrix — a table ranking hypotheses by impact vs effort
- ## Hypotheses — one detailed subsection per hypothesis with all fields above
- ## Cross-Cutting Themes & Sequencing — suggested order / dependencies
- ## What We Deliberately Skipped — frontier work judged not relevant to fraud/risk and why

After writing the file, return the structured object (wrote=true, slatePath = exact path above, and the hypotheses array).`

  const synthesis = await agent(synthesis_prompt, {
    label: 'synthesize:fraud-risk-experiments',
    phase: 'Synthesize',
    schema: SYNTHESIS_SCHEMA,
    agentType: 'master-orchestrator',
  })

  log(`Synthesis complete: ${synthesis && synthesis.hypotheses ? synthesis.hypotheses.length : 0} hypotheses.`)

  return {
    phase: 'synthesize',
    slatePath: synthesis ? synthesis.slatePath : slate_path,
    hypotheses: synthesis ? synthesis.hypotheses : [],
  }
}

throw new Error(`Unknown phase: ${phase_to_run}. Use one of: discover | deepdive | synthesize`)
