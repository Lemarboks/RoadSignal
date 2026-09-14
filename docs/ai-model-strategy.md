# AI model strategy

Reviewed 11 September 2026. Model availability and pricing change frequently; verify the linked provider pages before procurement.

## Recommendation

RoadSignal should use an LLM as an evidence-grounded assistant, not as the route-risk scorer. The existing deterministic routing and scoring services remain authoritative. They should send a compact evidence bundle to the LLM, which may explain the comparison, normalize a report, or draft an operator action. The LLM must never invent a safety score, silently change a route, or dispatch an emergency response.

The implemented open-source stack is documented in [Local open-source intelligence](open-source-stack.md). It supersedes the earlier hosted-model shortlist below: Qwen3 embeddings and reranking handle report retrieval, gpt-oss-20b is the optional local generator, Whisper handles voice intake, and OpenTelemetry/Jaeger provide tracing. H3 runs without model weights. XGBoost training and Valhalla route generation remain subject to the documented data/hardware prerequisites.

The following hosted-model comparison is retained as a research note only; these providers are not configured by the local implementation:

| Workload | Default model | Why it fits | Required control |
| --- | --- | --- | --- |
| Dispatcher copilot and route explanations | `gpt-5.6-terra` | Good intelligence/cost balance with structured outputs and tool calling | Generate only from supplied route and incident evidence |
| High-volume incident extraction, tagging, and duplicate candidates | `gpt-5.6-luna` | Low-cost, low-latency processing for bounded classification | Schema validation plus deterministic duplicate thresholds |
| Difficult after-action analysis | `gpt-6-astra` | Reserve the strongest reasoning model for rare, reviewed analysis | Operator initiated; never in the live scoring path |
| User-submitted text and images | `omni-moderation-latest` | Dedicated text/image safety screening | Moderate before storage or operator display |

OpenAI's current model catalogue describes Astra as the flagship reasoning model, Terra as the balanced model, and Luna as the high-volume cost-efficient model. The current models support image input, function calling, and structured outputs where listed. See the [OpenAI model catalogue](https://developers.openai.com/api/docs/models), [model comparison](https://developers.openai.com/api/docs/models/compare), and [omni-moderation model](https://developers.openai.com/api/docs/models/omni-moderation-latest).

For a vendor benchmark, evaluate the same frozen RoadSignal test set against `gemini-3.8-flash` and Claude Sonnet 5 before committing to a long-term provider. Google positions Gemini Flash for lower-latency, high-volume work, while Anthropic lists Sonnet 5 as an active model. See [Google's Gemini model documentation](https://ai.google.dev/gemini-api/docs/models) and [Anthropic's model lifecycle](https://platform.claude.com/docs/en/about-claude/model-deprecations). A benchmark result, not a generic leaderboard, should decide whether either alternative is better for RoadSignal.

## Safe request path

```text
Road, weather, incident, and trip signals
        -> deterministic route/risk engine
        -> versioned evidence bundle
        -> LLM explanation or triage
        -> JSON-schema validation and policy checks
        -> operator-visible answer with sources and confidence
```

The evidence bundle should contain route IDs, already-computed scores, score version, contributing signals, source timestamps, confidence, and permitted actions. The model response should be constrained to a schema such as:

```json
{
  "summary": "string",
  "evidence_ids": ["string"],
  "uncertainties": ["string"],
  "suggested_action": "monitor | review | contact_driver",
  "requires_human_approval": true
}
```

Reject an answer if it references an unknown evidence ID, changes a numeric score, omits uncertainty, or proposes an action outside the allow-list.

## Highest-value features

1. **Grounded route explanation** — turn the existing breakdown into a short, multilingual explanation while preserving exact scores and timestamps.
2. **Incident intake assistant** — extract incident type, severity candidate, location text, time, and duplicate candidates from driver reports. Existing validation and moderation remain authoritative.
3. **Fleet briefing** — summarize active trips and attention items, linking every statement to a trip or incident ID.
4. **After-action review** — identify recurring operational patterns across completed trips without changing the live risk model.
5. **Voice intake later** — add speech only after the text workflow passes safety and latency evaluations; do not make voice a dependency for emergency controls.

## Evaluation gate

Before enabling any LLM feature for users, create a frozen, human-reviewed set covering South African place names, code-switching, ambiguous incidents, false reports, prompt injection, stale weather, conflicting sources, and requests for guarantees. Track:

- JSON/schema validity and evidence citation precision;
- hallucinated incident, route, and score rate (target: zero in release tests);
- triage precision/recall by incident type and language;
- operator acceptance and correction rate;
- p50/p95 latency and cost per completed task;
- refusal quality for guarantees or unauthorized emergency actions.

Ship explanation-only behind a server-side feature flag first. Keep provider keys on the API server, redact unnecessary personal data, log model and prompt versions, and retain the deterministic non-LLM experience as the fallback.
