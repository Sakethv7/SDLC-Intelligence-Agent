"""
Insight Agent
=============
Analyses pipeline failure patterns and suggests concrete fixes.
Posts analysis to Slack #security-review alerts channel.
Posts analysis as an MR comment if a linked MR is found.
Writes an HTML report to disk for use as a CI artifact.
Optionally posts a trend report to the failed MR if available.

Trigger: pipeline failure event
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent
from agents.insight_agent.prompts import ANALYSIS_PROMPT, PATTERN_PROMPT, SYSTEM_PROMPT
from agents.insight_agent.report import render_html_report
from tools import anthropic_client, gcs_client, gitlab_client, slack_notifier

logger = logging.getLogger(__name__)


def _extract_risk(analysis: str) -> str:
    """
    Parse the recurrence risk level from Claude's structured output.

    SYSTEM_PROMPT asks for: ### Recurrence Risk\n**LOW / MEDIUM / HIGH** — ...
    We match that section specifically rather than scanning the whole text,
    which prevents false positives like "HIGH confidence" or "LOW priority"
    triggering the wrong risk level.

    Falls back to MEDIUM if the section is missing or unparseable.
    """
    # Primary: match the markdown bold on the line after the heading
    m = re.search(
        r"Recurrence Risk\s*\n\*\*(LOW|MEDIUM|HIGH)\*\*",
        analysis,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).upper()

    # Fallback: first HIGH/MEDIUM/LOW that appears after "Recurrence Risk"
    m = re.search(
        r"Recurrence Risk.{0,120}?(HIGH|MEDIUM|LOW)",
        analysis,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        return m.group(1).upper()

    return "MEDIUM"


def _fmt_jobs_detail(failed_jobs: list[dict]) -> str:
    lines = []
    for j in failed_jobs:
        lines.append(
            f"### [{j['stage']}] {j['name']}\n"
            f"- Failure reason: {j['failure_reason']}\n"
            f"- Duration: {j['duration']}s\n"
            f"- URL: {j['web_url']}\n"
            f"- Log tail:\n```\n{j['log_tail'][-1500:]}\n```"
        )
    return "\n\n".join(lines)


def _fmt_history(pipelines: list[dict]) -> str:
    if not pipelines:
        return "No recent failures found on this branch."
    lines = [
        f"- Pipeline #{p['id']} | {p['branch']} | {p['created_at'][:10]} | {p['duration']}s"
        for p in pipelines[:20]
    ]
    return "\n".join(lines)


class InsightAgent(BaseAgent):
    name = "insight"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        context keys:
          - pipeline_id : GitLab pipeline ID (required)
          - project_id  : GitLab project ID (optional)
          - post_slack  : bool, post to Slack (default True)
          - trend_days  : int, days of history for pattern analysis (default 7)
        """
        pipeline_id = int(context["pipeline_id"])
        project = gitlab_client.get_project(context.get("project_id"))
        trend_days = int(context.get("trend_days", 7))

        # ── Fetch pipeline detail ─────────────────────────────────────────────
        detail = gitlab_client.get_pipeline_detail(project, pipeline_id)

        if not detail["failed_jobs"]:
            return {"status": "ok", "output": "No failed jobs found.", "pipeline_id": pipeline_id}

        # ── Fetch recent failure history for pattern context ──────────────────
        history = gitlab_client.get_recent_pipeline_failures(
            project, branch=detail["branch"], days=trend_days
        )

        # ── Build prompt ──────────────────────────────────────────────────────
        prompt = ANALYSIS_PROMPT.format(
            pipeline_id=pipeline_id,
            project_name=os.environ.get("GITLAB_PROJECT_ID", "unknown"),
            branch=detail["branch"],
            triggered_by=detail["triggered_by"],
            duration=detail["duration"],
            pipeline_url=detail["web_url"],
            job_count=len(detail["failed_jobs"]),
            jobs_detail=_fmt_jobs_detail(detail["failed_jobs"]),
            history_count=len(history),
            failure_history=_fmt_history(history),
        )

        # ── Call Claude ───────────────────────────────────────────────────────
        analysis = anthropic_client.complete(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            model="claude-sonnet-4-6",
            max_tokens=2048,
            temperature=0.3,
        )

        # ── Determine recurrence risk for Slack title ─────────────────────────
        # Parse from the structured "### Recurrence Risk\n**HIGH**" section
        # that SYSTEM_PROMPT instructs Claude to emit. Avoids false positives
        # from "HIGH confidence" or "LOW priority" appearing elsewhere in the
        # analysis text (the old string-match approach).
        risk = _extract_risk(analysis)

        risk_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(risk, "🟡")

        # ── Post to Slack ─────────────────────────────────────────────────────
        if context.get("post_slack", True):
            slack_notifier.post_alert(
                title=f"{risk_emoji} Pipeline #{pipeline_id} Failed — {detail['branch']} [{risk} recurrence risk]",
                body=f"{analysis[:1800]}\n\n<{detail['web_url']}|View Pipeline>",
                footer=f"_Pipeline #{pipeline_id} · {len(detail['failed_jobs'])} failed job(s) · Insight Agent_",
            )
            logger.info("Posted pipeline analysis to Slack for pipeline #%s", pipeline_id)

        # ── Post MR comment if a linked MR exists ────────────────────────────
        mr_iid = context.get("mr_iid")
        if mr_iid:
            comment = (
                f"## 🤖 Insight Agent — Pipeline #{pipeline_id} Failed\n\n"
                f"{analysis}\n\n"
                f"---\n_Recurrence Risk: **{risk}** · [View Pipeline]({detail['web_url']})_"
            )
            try:
                gitlab_client.post_mr_comment(project, int(mr_iid), comment)
                logger.info("Posted analysis comment on MR !%s", mr_iid)
            except Exception:
                logger.exception("Failed to post MR comment on !%s", mr_iid)

        # ── Write HTML report artifact ────────────────────────────────────────
        report_path = context.get("report_path", "pipeline_report.html")
        html = render_html_report(
            pipeline_id=pipeline_id,
            branch=detail["branch"],
            triggered_by=detail["triggered_by"],
            pipeline_url=detail["web_url"],
            failed_jobs=detail["failed_jobs"],
            analysis=analysis,
            risk=risk,
            history=history,
        )
        Path(report_path).write_text(html, encoding="utf-8")
        logger.info("HTML report written to %s", report_path)

        # ── Upload to Google Cloud Storage if configured ──────────────────────
        gcs_url = gcs_client.upload_report(pipeline_id, html)
        if gcs_url:
            logger.info("Report available at %s", gcs_url)

        # ── Optional trend report if multiple failures ─────────────────────────
        trend_report = None
        if len(history) >= 3:
            trend_prompt = PATTERN_PROMPT.format(
                count=len(history),
                days=trend_days,
                history=_fmt_history(history),
            )
            trend_report = anthropic_client.complete(
                prompt=trend_prompt,
                system="You are a DevOps reliability engineer. Be concise and actionable.",
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                temperature=0.3,
            )
            if context.get("post_slack", True):
                slack_notifier.post_alert(
                    title=f"📊 Pipeline Trend Report — {detail['branch']} ({len(history)} failures in {trend_days}d)",
                    body=trend_report,
                    footer=f"_Insight Agent · trend analysis_",
                )

        return {
            "status": "ok",
            "output": analysis,
            "pipeline_id": pipeline_id,
            "branch": detail["branch"],
            "failed_jobs": len(detail["failed_jobs"]),
            "recurrence_risk": risk,
            "trend_report": trend_report,
            "report_path": report_path,
            "report_gcs_url": gcs_url,
        }
