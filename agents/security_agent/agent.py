"""
Security Agent
==============
Scans MR diffs for security risks using RAG over policy docs + Claude.
Ported from github.com/Sakethv7/RAG_mini-phase-2.

Trigger: merge_request_event (any MR opened/updated)
TODO: implement RAG store, policy doc ingestion, risk scoring
"""
from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent
from tools import anthropic_client, gitlab_client, slack_notifier

SYSTEM_PROMPT = """
You are a security-focused code reviewer. Analyse the provided MR diff and
identify security risks: injection flaws, secrets exposure, auth bypasses,
insecure dependencies, OWASP Top-10 issues. Rate each finding LOW/MEDIUM/HIGH.
Be concise — one bullet per finding.
""".strip()


class SecurityAgent(BaseAgent):
    name = "security"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        mr_iid = context["mr_iid"]
        project = gitlab_client.get_project(context.get("project_id"))

        diff = gitlab_client.get_mr_diff(project, mr_iid)
        if not diff.strip():
            return {"status": "ok", "output": "No diff to analyse."}

        prompt = (
            f"Review this MR diff for security issues:\n\n{diff[:12000]}"
        )
        findings = anthropic_client.complete(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            model="claude-sonnet-4-6",
            max_tokens=2048,
            temperature=0.3,
        )

        # Post to MR as a comment
        gitlab_client.post_mr_comment(
            project, mr_iid,
            f"## 🔐 Security Scan (SDLC Intelligence Agent)\n\n{findings}"
        )

        # Alert Slack if HIGH findings present
        if "HIGH" in findings:
            slack_notifier.post_alert(
                title=f"🔐 Security Alert — MR !{mr_iid}",
                body=findings,
                footer=f"_MR !{mr_iid} · Security Agent_",
            )

        return {"status": "ok", "output": findings}
