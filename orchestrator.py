"""
Orchestrator
============
Routes trigger events to the correct sub-agent(s) and returns results.
Can be called directly (CLI / cron) or invoked by server.py (webhook).
"""
from __future__ import annotations

import logging
from typing import Any

from agents.digest_agent.agent import DigestAgent
from agents.security_agent.agent import SecurityAgent
from agents.compliance_agent.agent import ComplianceAgent
from agents.insight_agent.agent import InsightAgent

logger = logging.getLogger(__name__)

_AGENTS = {
    "digest": DigestAgent(),
    "security": SecurityAgent(),
    "compliance": ComplianceAgent(),
    "insight": InsightAgent(),
}


def dispatch(event: str, context: dict[str, Any]) -> dict[str, Any]:
    """
    Route an event to the appropriate agent(s).

    event values:
      "weekly_digest"       → DigestAgent
      "mr_opened"           → SecurityAgent + ComplianceAgent (parallel-ish)
      "reviewer_assigned"   → ComplianceAgent
      "pipeline_failed"     → InsightAgent
    """
    results: dict[str, Any] = {}

    if event == "weekly_digest":
        results["digest"] = _run("digest", context)

    elif event == "mr_opened":
        results["security"] = _run("security", context)
        results["compliance"] = _run("compliance", context)

    elif event == "reviewer_assigned":
        results["compliance"] = _run("compliance", context)

    elif event == "pipeline_failed":
        results["insight"] = _run("insight", context)

    else:
        logger.warning("Unknown event: %s", event)
        results["error"] = f"Unknown event '{event}'"

    return results


def _run(agent_name: str, context: dict[str, Any]) -> dict[str, Any]:
    agent = _AGENTS[agent_name]
    logger.info("Running agent: %s", agent_name)
    try:
        return agent.run(context)
    except Exception as exc:
        logger.exception("Agent %s failed", agent_name)
        return {"status": "error", "output": str(exc)}
