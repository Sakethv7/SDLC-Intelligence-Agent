"""
Compliance Agent
================
Runs a policy checklist when a reviewer is assigned to an MR.

Trigger: reviewer assigned to MR
TODO: load policy checklist from config / RAG store
"""
from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent
from tools import anthropic_client, gitlab_client

SYSTEM_PROMPT = """
You are a compliance officer reviewing a merge request against engineering
policy. Check: branch naming, required labels, test coverage mention,
linked issue, docs update, changelog entry. Output a markdown checklist
with ✅ or ❌ for each item and a one-line summary.
""".strip()

CHECKLIST_TEMPLATE = """
MR title: {title}
Labels: {labels}
Source branch: {source_branch}
Description excerpt:
{description}

Run the compliance checklist above.
""".strip()


class ComplianceAgent(BaseAgent):
    name = "compliance"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        mr_iid = context["mr_iid"]
        project = gitlab_client.get_project(context.get("project_id"))
        mr = project.mergerequests.get(mr_iid)

        prompt = CHECKLIST_TEMPLATE.format(
            title=mr.title,
            labels=", ".join(mr.labels) or "none",
            source_branch=mr.source_branch,
            description=(mr.description or "")[:1500],
        )
        result = anthropic_client.complete(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            temperature=0.2,
        )

        gitlab_client.post_mr_comment(
            project, mr_iid,
            f"## 📋 Compliance Check (SDLC Intelligence Agent)\n\n{result}"
        )

        return {"status": "ok", "output": result}
