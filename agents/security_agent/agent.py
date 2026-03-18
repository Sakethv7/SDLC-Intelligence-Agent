"""
Security Agent
==============
Scans MR diffs for security risks using RAG over policy docs + Claude.
Ported from github.com/Sakethv7/RAG_mini-phase-2.

Trigger: merge_request_event (MR opened or updated)
"""
from __future__ import annotations

import logging
import os
from typing import Any

from agents.base_agent import BaseAgent
from agents.security_agent import rag_store
from agents.security_agent.prompts import SCAN_PROMPT, SYSTEM_PROMPT
from tools import anthropic_client, gitlab_client, slack_notifier

logger = logging.getLogger(__name__)


def _ensure_policies_loaded() -> None:
    """Ingest policy docs if the store is empty."""
    if rag_store.store_size() == 0:
        doc_dir = os.environ.get("POLICY_DOCS_DIR", "policy_docs")
        results = rag_store.ingest_directory(doc_dir)
        total = sum(results.values())
        logger.info("Ingested %d policy chunks from %s", total, doc_dir)


def _build_policy_context(diff: str) -> str:
    """Retrieve relevant policy chunks for the diff."""
    # Query with multiple angles to maximize recall
    queries = [
        diff[:500],                          # first 500 chars of diff
        "security vulnerabilities injection hardcoded secrets",
        "authentication authorization access control",
    ]
    seen, chunks = set(), []
    for q in queries:
        for r in rag_store.retrieve(q, top_k=4):
            key = (r["source"], r["chunk_index"])
            if key not in seen:
                seen.add(key)
                chunks.append(f"### {r['source']} (relevance: {r['score']:.2f})\n{r['text']}")

    return "\n\n".join(chunks) if chunks else "No specific policy matches found — apply general security best practices."


class SecurityAgent(BaseAgent):
    name = "security"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        context keys:
          - mr_iid      : MR internal ID (required)
          - project_id  : GitLab project ID (optional, falls back to env)
          - post_comment: bool, post findings to MR (default True)
          - post_slack  : bool, alert Slack on HIGH (default True)
        """
        mr_iid = context["mr_iid"]
        project = gitlab_client.get_project(context.get("project_id"))

        # Load policy docs into RAG store if needed
        _ensure_policies_loaded()

        # Fetch the MR diff
        diff = gitlab_client.get_mr_diff(project, mr_iid)
        if not diff.strip():
            return {"status": "ok", "output": "No diff to analyse.", "verdict": "APPROVE"}

        # Build RAG-augmented prompt
        policy_context = _build_policy_context(diff)
        prompt = SCAN_PROMPT.format(
            diff=diff[:10000],
            policy_context=policy_context,
        )

        # Run Claude
        findings = anthropic_client.complete(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            model="claude-sonnet-4-6",
            max_tokens=2048,
            temperature=0.2,
        )

        # Extract verdict
        verdict = "APPROVE"
        if "BLOCK" in findings:
            verdict = "BLOCK"
        elif "REQUEST_CHANGES" in findings:
            verdict = "REQUEST_CHANGES"

        # Post to MR as a comment
        if context.get("post_comment", True):
            gitlab_client.post_mr_comment(project, mr_iid, findings)
            logger.info("Posted security findings to MR !%s", mr_iid)

        # Alert Slack on HIGH severity or BLOCK verdict
        if context.get("post_slack", True) and (verdict in ("BLOCK", "REQUEST_CHANGES") or "🔴 HIGH" in findings):
            mr_url = f"{os.environ.get('GITLAB_URL', 'https://gitlab.com')}/{os.environ.get('GITLAB_PROJECT_ID', '')}/merge_requests/{mr_iid}"
            slack_notifier.post_alert(
                title=f"🔐 Security Scan: {verdict} — MR !{mr_iid}",
                body=f"{findings[:1500]}\n\n<{mr_url}|View MR>",
                footer=f"_MR !{mr_iid} · Security Agent · RAG policy scan_",
            )

        return {
            "status": "ok",
            "output": findings,
            "verdict": verdict,
            "policy_chunks_used": rag_store.store_size(),
        }
