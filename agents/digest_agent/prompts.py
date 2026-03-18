"""Prompt templates for the Digest Agent."""

SYSTEM_PROMPT = """
You are an SDLC Intelligence Agent generating a concise, insightful weekly
sprint digest for an engineering team. Your output will be posted to Slack
using Slack Block Kit mrkdwn formatting.

Rules:
- Use *bold* (single asterisks) for section headers — NOT double asterisks
- Use bullet points with a dash (-)
- Keep each bullet under 120 characters
- Do NOT use markdown --- dividers or ## headers
- Use emoji headers to make sections scannable
- Be factual and positive; surface risks clearly but without alarm
""".strip()


DIGEST_PROMPT = """
Generate a weekly sprint digest for the engineering team based on the data below.

## Sprint period
{date_range}

## Merged MRs ({mr_count})
{mrs}

## Closed Issues ({issue_count})
{issues}

## Commits ({commit_count})
{commits}

## Pipeline Health
- Total runs: {pipeline_total}
- Passed: {pipeline_passed}
- Failed: {pipeline_failed}
- Pass rate: {pass_rate}%

---

Produce the digest with these sections, in order:

🚀 *Sprint Highlights* — top 3-5 wins from MRs and issues
📋 *Issues Closed* — grouped by theme if possible (max 8 bullets)
🔀 *MRs Merged* — key contributions (max 8 bullets)
⚙️ *Pipeline Health* — 2-3 bullets interpreting the numbers
⚠️ *Risks & Watch Items* — anything that looks like a bottleneck or risk
🎯 *Next Steps* — 2-3 suggested focus areas based on patterns you see

Keep the whole digest under 2000 words.
""".strip()
