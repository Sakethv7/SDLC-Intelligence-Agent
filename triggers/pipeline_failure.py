"""
Pipeline failure trigger — runs the Insight Agent.
Called by: GitLab CI on failed pipeline, or `python -m triggers.pipeline_failure`
"""
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

import orchestrator


def main():
    pipeline_id = os.environ.get("FAILED_PIPELINE_ID") or os.environ.get("CI_PIPELINE_ID")
    if not pipeline_id:
        print("ERROR: FAILED_PIPELINE_ID not set", file=sys.stderr)
        sys.exit(1)

    result = orchestrator.dispatch(
        "pipeline_failed",
        {
            "project_id": os.environ.get("GITLAB_PROJECT_ID"),
            "pipeline_id": pipeline_id,
        },
    )
    insight = result.get("insight", {})
    if insight.get("status") == "error":
        print(f"ERROR: {insight['output']}", file=sys.stderr)
        sys.exit(1)
    print("Insight posted.")


if __name__ == "__main__":
    main()
