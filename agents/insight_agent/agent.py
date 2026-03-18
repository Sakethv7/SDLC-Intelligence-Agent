"""
Insight Agent
=============
Analyses pipeline failure patterns and suggests fixes.

Trigger: pipeline failure event
"""
from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent
from tools import anthropic_client, gitlab_client, slack_notifier

SYSTEM_PROMPT = """
You are a DevOps engineer analysing CI/CD pipeline failures. Given a list of
failed jobs, identify the likely root cause, classify the failure type
(flaky test / config error / dependency issue / infra problem), and suggest
a concrete remediation step. Keep it under 200 words.
""".strip()


class InsightAgent(BaseAgent):
    name = "insight"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        pipeline_id = int(context["pipeline_id"])
        project = gitlab_client.get_project(context.get("project_id"))

        failed_jobs = gitlab_client.get_failed_jobs(project, pipeline_id)
        if not failed_jobs:
            return {"status": "ok", "output": "No failed jobs found."}

        jobs_text = "\n".join(
            f"- [{j['stage']}] {j['name']}: {j['failure_reason']}" for j in failed_jobs
        )
        prompt = f"Failed jobs in pipeline #{pipeline_id}:\n{jobs_text}\n\nAnalyse and suggest fixes."

        analysis = anthropic_client.complete(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            model="claude-sonnet-4-6",
            max_tokens=1024,
            temperature=0.4,
        )

        slack_notifier.post_alert(
            title=f"🔴 Pipeline #{pipeline_id} Failed — Analysis",
            body=analysis,
            footer=f"_Pipeline #{pipeline_id} · Insight Agent_",
        )

        return {"status": "ok", "output": analysis}
