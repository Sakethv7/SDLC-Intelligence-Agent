"""
Reviewer assignment trigger — runs Security + Compliance agents.
Called by: GitLab CI on MR events, or `python -m triggers.reviewer_assignment`

Flags:
  --compliance   run compliance only (reviewer assigned, not MR open)
"""
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

import orchestrator


def main():
    compliance_only = "--compliance" in sys.argv
    mr_iid = os.environ.get("MR_IID") or os.environ.get("CI_MERGE_REQUEST_IID")
    if not mr_iid:
        print("ERROR: MR_IID not set", file=sys.stderr)
        sys.exit(1)

    event = "reviewer_assigned" if compliance_only else "mr_opened"
    result = orchestrator.dispatch(
        event,
        {
            "project_id": os.environ.get("GITLAB_PROJECT_ID"),
            "mr_iid": int(mr_iid),
        },
    )
    errors = [k for k, v in result.items() if v.get("status") == "error"]
    if errors:
        print(f"ERROR in agents: {errors}", file=sys.stderr)
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
