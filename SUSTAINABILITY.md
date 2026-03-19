# Green Agent — Sustainability Design

SDLC Intelligence Agent is designed to minimise computational waste at every layer. This document explains the concrete choices made to reduce token consumption, avoid redundant inference, and prefer efficient models.

## Model Selection Strategy

The project uses two Claude models with deliberate intent:

| Task | Model | Rationale |
|---|---|---|
| Security review (RAG + OWASP analysis) | claude-sonnet-4-6 | Complex multi-step reasoning over policy context requires a capable model |
| Pipeline failure analysis | claude-sonnet-4-6 | Log interpretation + root cause classification benefits from higher accuracy |
| Weekly digest generation | claude-sonnet-4-6 | Synthesis of diverse data into narrative requires coherent long-form output |
| Pipeline trend analysis | claude-haiku-4-5-20251001 | Pattern summarisation over structured data is a simpler task — haiku is sufficient and ~12× cheaper |
| Compliance checklist review | claude-haiku-4-5-20251001 | Structured metadata evaluation maps cleanly to a smaller model's strengths |

**Rule:** use the least capable model that produces acceptable output for the task. Haiku is selected wherever the task is structured, short-context, or classification-oriented.

## Input Truncation

Sending unnecessary tokens to the LLM is the single biggest source of waste. Every data-fetch path has an explicit limit:

- **MR diffs** (`gitlab_client.get_mr_diff`): capped at 20 files, 5 diff hunks per file. Large monorepo MRs do not cause unbounded prompt growth.
- **Pipeline logs** (`gitlab_client.get_pipeline_detail`): last 60 lines of each failed job log. Full multi-MB CI logs are never sent.
- **Pipeline failure history** (`_fmt_history`): capped at 20 entries before formatting.
- **Slack messages**: chunked at 2800 chars per block; LLM output is not re-processed or re-sent.
- **Trend analysis** (`PATTERN_PROMPT`): max_tokens=600 — tightly bounded because the output is a short summary.

## RAG over Full-Document Retrieval

The Security Agent uses retrieval-augmented generation over local policy documents rather than injecting all policy content into every prompt. Only the top-k most relevant chunks (cosine similarity threshold ≥ 0.2) are included. This means:

- Typical prompt contains ~2-4 policy chunks (~1,600–3,200 characters) instead of the full policy corpus (~12,000 characters).
- Estimated token reduction per security scan: **60–80%** of policy context.

## Event-Driven Execution (No Polling)

Agents run only when a GitLab event fires. There are no background polling loops, no scheduled health checks that call LLMs, and no keep-alive inference. The system is idle between events.

Comparison:
- A polling-based agent checking for MR activity every 60s would issue ~1,440 LLM calls/day for a single project doing nothing.
- This project: **0 calls/day** when no events occur.

## Token Usage Tracking

Every completion call records input and output token counts via `tools/token_tracker.py`. Usage is written to `token_usage.jsonl` as a CI artifact, giving teams visibility into inference cost per pipeline run.

The tracker also computes estimated USD cost using published Anthropic pricing, enabling teams to set budgets or alert thresholds.

## CI Artifact Scope

HTML pipeline reports are written once as CI artifacts rather than rendered server-side on every view request. If Google Cloud Storage is configured, the report is uploaded and the local file is kept as a CI artifact — no re-generation.

## Summary

| Design choice | Token/compute impact |
|---|---|
| Haiku for simple tasks | ~12× cheaper per call vs Sonnet |
| Diff capped at 20 files / 5 hunks | Prevents unbounded prompt growth |
| Log tail at 60 lines | Avoids sending MB-scale CI logs |
| RAG chunk retrieval | 60–80% reduction in policy context tokens |
| Event-driven (no polling) | Zero idle inference |
| max_tokens bounded per task | Prevents over-generation |
| Token usage logged as artifact | Enables cost accountability |
