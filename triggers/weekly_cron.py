"""
Weekly cron trigger — runs the Digest Agent.
Called by: GitLab CI schedule, or locally with `python -m triggers.weekly_cron`
"""
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

import orchestrator


def main():
    result = orchestrator.dispatch(
        "weekly_digest",
        {
            "project_id": os.environ.get("GITLAB_PROJECT_ID"),
            "weeks_back": int(os.environ.get("SPRINT_WEEKS", 1)),
            "post_slack": True,
        },
    )
    digest = result.get("digest", {})
    if digest.get("status") == "error":
        print(f"ERROR: {digest['output']}", file=sys.stderr)
        sys.exit(1)
    print("Digest posted successfully.")
    print(digest.get("output", "")[:500])


if __name__ == "__main__":
    main()
