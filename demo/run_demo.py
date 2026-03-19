"""
SDLC Intelligence Agent — Full Demo Runner
==========================================
Single command. No flags needed.

What it does:
  1. Creates a real GitLab branch + MR with intentionally vulnerable code
  2. Runs Security Agent  → posts BLOCK findings to MR + Slack alert
  3. Runs Compliance Agent → posts checklist table to MR + Slack alert
  4. Runs Digest Agent    → posts weekly sprint summary to Slack
  5. Writes demo/DEMO_REPORT.md  (open in Obsidian or any markdown viewer)

Usage:
    python -m demo.run_demo

    # Reuse an existing MR (skip creation):
    python -m demo.run_demo --mr-iid 3

    # Also demo Insight Agent (needs a real failed pipeline ID):
    python -m demo.run_demo --pipeline-id 12345
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
# Silence noisy third-party loggers
for _noisy in ("httpx", "sentence_transformers", "urllib3", "httpcore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger("demo")

REPORT_PATH = Path(__file__).parent / "DEMO_REPORT.md"
_report_sections: list[str] = []
_start_time = datetime.now(timezone.utc)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _banner(step: int, title: str) -> None:
    print(f"\n\033[1;36m{'━'*60}\033[0m")
    print(f"\033[1;36m  STEP {step} — {title}\033[0m")
    print(f"\033[1;36m{'━'*60}\033[0m\n")


def _ok(msg: str) -> None:
    print(f"  \033[32m✔\033[0m  {msg}")


def _info(msg: str) -> None:
    print(f"  \033[34m→\033[0m  {msg}")


def _section(title: str, body: str) -> None:
    """Append a section to the Obsidian report."""
    _report_sections.append(f"## {title}\n\n{body.strip()}\n")


def _write_report(mr_iid: int, mr_url: str) -> None:
    now = _start_time.strftime("%Y-%m-%d %H:%M UTC")
    header = f"""---
title: SDLC Intelligence Agent — Demo Report
date: {now}
tags: [sdlc, security, compliance, ai-agents, gitlab]
---

# SDLC Intelligence Agent Demo Report

**Generated:** {now}
**MR:** [!{mr_iid}]({mr_url})
**Project:** {os.environ.get('GITLAB_PROJECT_ID', 'unknown')}

> This report was generated automatically by running four AI agents against a real
> GitLab merge request. Each agent reacted to a GitLab event, ran LLM analysis,
> and posted structured output back to the MR thread and Slack.

"""
    from tools.token_tracker import get_summary
    summary = get_summary()
    token_section = f"""| Model | Input tokens | Output tokens | Est. cost |
|---|---|---|---|
"""
    for row in summary["models"]:
        token_section += f"| `{row['model']}` | {row['input_tokens']:,} | {row['output_tokens']:,} | ${row['estimated_cost_usd']:.4f} |\n"
    token_section += f"\n**Total:** {summary['total_tokens']:,} tokens · **${summary['estimated_cost_usd']:.4f}**"
    _section("Token Usage (Green Agent)", token_section)

    body = header + "\n".join(_report_sections)
    REPORT_PATH.write_text(body, encoding="utf-8")
    print(f"\n  \033[33m📄 Obsidian report →\033[0m  {REPORT_PATH}")


def _create_mr(project) -> tuple[int, str]:
    """Push vulnerable_app.py to a new branch and open an MR."""
    timestamp = int(time.time())
    branch = f"demo/security-scan-{timestamp}"
    default_branch = project.default_branch or "main"

    _info(f"Creating branch {branch}")
    project.branches.create({"branch": branch, "ref": default_branch})

    content = (Path(__file__).parent / "vulnerable_app.py").read_text(encoding="utf-8")
    _info("Committing vulnerable_app.py (hardcoded secrets, SQL injection, command injection, eval, SSRF…)")
    project.files.create({
        "file_path": "demo/vulnerable_app.py",
        "branch": branch,
        "content": content,
        "commit_message": "add user auth and reporting module",
    })

    _info("Opening MR with minimal description (triggers compliance failures)")
    mr = project.mergerequests.create({
        "source_branch": branch,
        "target_branch": default_branch,
        "title": "Add user auth and reporting module",
        "description": "adds some new features",
        "remove_source_branch": True,
    })
    _ok(f"MR !{mr.iid} created → {mr.web_url}")
    return mr.iid, mr.web_url


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mr-iid", type=int, help="Reuse an existing MR instead of creating one")
    parser.add_argument("--pipeline-id", type=int, help="Failed pipeline ID for Insight Agent")
    args = parser.parse_args()

    for var in ("ANTHROPIC_API_KEY", "GITLAB_TOKEN", "GITLAB_PROJECT_ID"):
        if not os.environ.get(var):
            sys.exit(f"ERROR: {var} not set in .env")

    from tools import gitlab_client
    project = gitlab_client.get_project()

    # ── Step 1: MR ────────────────────────────────────────────────────────────
    if args.mr_iid:
        mr_iid = args.mr_iid
        mr_url = f"{os.environ.get('GITLAB_URL', 'https://gitlab.com')}/{os.environ.get('GITLAB_PROJECT_ID', '')}/merge_requests/{mr_iid}"
        _banner(1, "Reusing existing MR")
        _ok(f"MR !{mr_iid} → {mr_url}")
    else:
        _banner(1, "Creating demo MR with vulnerable code")
        mr_iid, mr_url = _create_mr(project)
        _info("Waiting 3s for GitLab to index the diff…")
        time.sleep(3)

    _section("Demo MR", f"**URL:** {mr_url}  \n**MR IID:** !{mr_iid}")

    # ── Step 2: Security Agent ─────────────────────────────────────────────────
    _banner(2, "Security Agent — scanning MR diff for vulnerabilities")
    _info("Loading RAG policy store + running Claude scan…")
    from agents.security_agent.agent import SecurityAgent
    sec = SecurityAgent().run({"mr_iid": mr_iid, "post_comment": True, "post_slack": True})
    _ok(f"Verdict: \033[1;31m{sec['verdict']}\033[0m  |  posted to MR + Slack")
    _section("Security Agent", f"**Verdict:** `{sec['verdict']}`\n\n```\n{sec['output'][:3000]}\n```")

    # ── Step 3: Compliance Agent ───────────────────────────────────────────────
    _banner(3, "Compliance Agent — checking MR metadata")
    from agents.compliance_agent.agent import ComplianceAgent
    comp = ComplianceAgent().run({"mr_iid": mr_iid, "post_comment": True, "post_slack": True})
    _ok(f"Verdict: \033[1;31m{comp['verdict']}\033[0m  |  posted to MR + Slack")
    _section("Compliance Agent", f"**Verdict:** `{comp['verdict']}`\n\n{comp['output'][:3000]}")

    # ── Step 4: Insight Agent (optional) ──────────────────────────────────────
    if args.pipeline_id:
        _banner(4, "Insight Agent — analysing failed pipeline")
        from agents.insight_agent.agent import InsightAgent
        ins = InsightAgent().run({
            "pipeline_id": args.pipeline_id,
            "mr_iid": mr_iid,
            "post_slack": True,
            "report_path": str(Path(__file__).parent / "pipeline_report.html"),
        })
        _ok(f"Recurrence risk: {ins['recurrence_risk']}  |  HTML report → demo/pipeline_report.html")
        _section("Insight Agent", f"**Recurrence Risk:** `{ins['recurrence_risk']}`\n\n{ins['output'][:3000]}")
    else:
        _info("Insight Agent skipped (pass --pipeline-id <id> to include it)")

    # ── Step 5: Digest Agent ───────────────────────────────────────────────────
    _banner(5, "Digest Agent — generating weekly sprint summary")
    from agents.digest_agent.agent import DigestAgent
    dig = DigestAgent().run({"weeks_back": 1, "post_slack": True})
    _ok("Weekly digest posted to Slack")
    _section("Digest Agent — Weekly Sprint Summary", dig["output"][:4000])

    # ── Report ─────────────────────────────────────────────────────────────────
    _banner(6, "Writing Obsidian report + token summary")
    _write_report(mr_iid, mr_url)

    from tools.token_tracker import log_summary
    log_summary()

    print(f"""
\033[1;32m{'━'*60}
  Demo complete
{'━'*60}\033[0m

  GitLab MR  →  {mr_url}
  Slack      →  check #security-alerts and #general
  Report     →  {REPORT_PATH}

  Open DEMO_REPORT.md in Obsidian to see the full structured output.
""")


if __name__ == "__main__":
    main()
