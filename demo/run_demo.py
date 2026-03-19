"""
SDLC Intelligence Agent — Demo Runner
======================================
Creates a demo MR on your GitLab project containing intentionally vulnerable code,
then runs all four agents against real GitLab data so you can record the output.

Usage:
    python -m demo.run_demo [--skip-mr] [--mr-iid N] [--pipeline-id N]

Steps:
    1. Creates branch  demo/security-scan-<timestamp>
    2. Commits demo/vulnerable_app.py to that branch
    3. Opens an MR with a deliberately minimal description (triggers compliance issues)
    4. Runs Security Agent  → posts findings to the MR
    5. Runs Compliance Agent → posts checklist table to the MR
    6. Runs Digest Agent    → prints weekly digest (does NOT post to Slack by default)
    7. (Optional) Runs Insight Agent if --pipeline-id is supplied

Requirements:
    .env must contain: ANTHROPIC_API_KEY, GITLAB_TOKEN, GITLAB_PROJECT_ID
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("demo")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def _create_demo_mr(project) -> int:
    """Push vulnerable_app.py to a new branch and open an MR. Returns mr.iid."""
    import gitlab

    timestamp = int(time.time())
    branch = f"demo/security-scan-{timestamp}"
    default_branch = project.default_branch or "main"

    logger.info("Creating branch %s from %s", branch, default_branch)
    project.branches.create({"branch": branch, "ref": default_branch})

    demo_file = Path(__file__).parent / "vulnerable_app.py"
    content = demo_file.read_text(encoding="utf-8")

    logger.info("Committing vulnerable_app.py to %s", branch)
    project.files.create({
        "file_path": "demo/vulnerable_app.py",
        "branch": branch,
        "content": content,
        "commit_message": "add user auth and reporting module",
    })

    logger.info("Opening MR")
    mr = project.mergerequests.create({
        "source_branch": branch,
        "target_branch": default_branch,
        "title": "Add user auth and reporting module",
        # Deliberately thin description and no labels → triggers compliance findings
        "description": "adds some new features",
        "remove_source_branch": True,
    })
    logger.info("MR created: !%s  %s", mr.iid, mr.web_url)
    print(f"\n  MR URL: {mr.web_url}\n")
    return mr.iid


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="SDLC Intelligence Agent demo runner")
    parser.add_argument("--skip-mr", action="store_true", help="Skip MR creation, use --mr-iid")
    parser.add_argument("--mr-iid", type=int, help="Existing MR IID to run agents against")
    parser.add_argument("--pipeline-id", type=int, help="Failed pipeline ID for Insight Agent demo")
    parser.add_argument("--post-slack", action="store_true", help="Actually post to Slack (default: dry-run)")
    args = parser.parse_args()

    for var in ("ANTHROPIC_API_KEY", "GITLAB_TOKEN", "GITLAB_PROJECT_ID"):
        if not os.environ.get(var):
            sys.exit(f"ERROR: {var} is not set. Copy .env.example to .env and fill in your values.")

    from tools import gitlab_client
    project = gitlab_client.get_project()

    # ── Step 1: Create demo MR ────────────────────────────────────────────────
    if args.skip_mr:
        if not args.mr_iid:
            sys.exit("--skip-mr requires --mr-iid")
        mr_iid = args.mr_iid
        logger.info("Skipping MR creation, using MR !%s", mr_iid)
    else:
        _separator("STEP 1 — Creating demo MR with vulnerable code")
        mr_iid = _create_demo_mr(project)
        logger.info("Waiting 3s for GitLab to index the diff...")
        time.sleep(3)

    # ── Step 2: Security Agent ────────────────────────────────────────────────
    _separator("STEP 2 — Security Agent (scanning MR diff)")
    from agents.security_agent.agent import SecurityAgent
    sec_result = SecurityAgent().run({
        "mr_iid": mr_iid,
        "post_comment": True,
        "post_slack": args.post_slack,
    })
    print("Verdict:", sec_result.get("verdict", "see output below"))
    print(sec_result.get("output", "")[:1000])

    # ── Step 3: Compliance Agent ──────────────────────────────────────────────
    _separator("STEP 3 — Compliance Agent (checking MR metadata)")
    from agents.compliance_agent.agent import ComplianceAgent
    comp_result = ComplianceAgent().run({
        "mr_iid": mr_iid,
        "post_comment": True,
        "post_slack": args.post_slack,
    })
    print("Verdict:", comp_result.get("verdict", "see output below"))
    print(comp_result.get("output", "")[:1000])

    # ── Step 4: Insight Agent (optional) ─────────────────────────────────────
    if args.pipeline_id:
        _separator("STEP 4 — Insight Agent (analysing failed pipeline)")
        from agents.insight_agent.agent import InsightAgent
        ins_result = InsightAgent().run({
            "pipeline_id": args.pipeline_id,
            "mr_iid": mr_iid,
            "post_slack": args.post_slack,
            "report_path": "demo_pipeline_report.html",
        })
        print("Risk:", ins_result.get("recurrence_risk"))
        print(ins_result.get("output", "")[:1000])
        print(f"\n  HTML report: demo_pipeline_report.html")
    else:
        logger.info("Skipping Insight Agent (pass --pipeline-id <id> to include it)")

    # ── Step 5: Digest Agent ──────────────────────────────────────────────────
    _separator("STEP 5 — Digest Agent (weekly sprint summary)")
    from agents.digest_agent.agent import DigestAgent
    dig_result = DigestAgent().run({
        "weeks_back": 1,
        "post_slack": args.post_slack,
    })
    print(dig_result.get("output", "")[:2000])

    # ── Token usage summary ───────────────────────────────────────────────────
    _separator("Token Usage Summary (Green Agent)")
    from tools.token_tracker import log_summary
    log_summary()

    _separator("Demo complete")
    print(f"  MR !{mr_iid} now has Security + Compliance comments from the agents.")
    print(f"  Open it in GitLab to see the output for your video recording.\n")


if __name__ == "__main__":
    main()
