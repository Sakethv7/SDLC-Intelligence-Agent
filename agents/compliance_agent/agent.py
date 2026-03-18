"""
Compliance Agent
================
Runs a policy checklist when a reviewer is assigned to an MR.
Posts results as an MR comment. Notifies Slack on FAIL.

Trigger: reviewer assigned to MR
"""
from __future__ import annotations

import logging
from typing import Any

from agents.base_agent import BaseAgent
from agents.compliance_agent.prompts import CHECKLIST_PROMPT, SYSTEM_PROMPT
from tools import anthropic_client, gitlab_client, slack_notifier

logger = logging.getLogger(__name__)


def _get_changed_files(project, mr_iid: int) -> tuple[list[str], int]:
    """Return list of changed file paths and total count."""
    try:
        mr = project.mergerequests.get(mr_iid)
        changes = mr.changes()
        files = [c["new_path"] for c in changes.get("changes", [])[:25]]
        total = len(changes.get("changes", []))
        return files, total
    except Exception:
        return [], 0


class ComplianceAgent(BaseAgent):
    name = "compliance"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        context keys:
          - mr_iid      : MR internal ID (required)
          - project_id  : GitLab project ID (optional)
          - post_comment: bool, post checklist to MR (default True)
          - post_slack  : bool, notify Slack on FAIL (default True)
        """
        mr_iid = context["mr_iid"]
        project = gitlab_client.get_project(context.get("project_id"))
        mr = project.mergerequests.get(mr_iid)

        changed_files, file_count = _get_changed_files(project, mr_iid)

        prompt = CHECKLIST_PROMPT.format(
            title=mr.title,
            source_branch=mr.source_branch,
            target_branch=mr.target_branch,
            author=mr.author["name"],
            labels=", ".join(mr.labels) if mr.labels else "none",
            assignees=", ".join(a["name"] for a in mr.assignees) if mr.assignees else "none",
            reviewers=", ".join(r["name"] for r in getattr(mr, "reviewers", [])) if getattr(mr, "reviewers", []) else "none",
            web_url=mr.web_url,
            created_at=mr.created_at,
            description=(mr.description or "(no description provided)")[:2000],
            changed_files="\n".join(f"  - {f}" for f in changed_files) or "  (none listed)",
            file_count=file_count,
        )

        result = anthropic_client.complete(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            temperature=0.1,
        )

        # Determine outcome
        verdict = "PASS"
        if "Overall: FAIL" in result or "**FAIL**" in result:
            verdict = "FAIL"
        elif "Overall: WARN" in result or "**WARN**" in result:
            verdict = "WARN"

        # Post to MR
        if context.get("post_comment", True):
            gitlab_client.post_mr_comment(project, mr_iid, result)
            logger.info("Posted compliance checklist to MR !%s — %s", mr_iid, verdict)

        # Slack notification on FAIL
        if context.get("post_slack", True) and verdict == "FAIL":
            slack_notifier.post_alert(
                title=f"📋 Compliance FAIL — MR !{mr_iid}: {mr.title}",
                body=f"{result[:1200]}\n\n<{mr.web_url}|View MR>",
                footer=f"_MR !{mr_iid} · Compliance Agent_",
            )

        return {
            "status": "ok",
            "output": result,
            "verdict": verdict,
            "file_count": file_count,
        }
