"""GitLab API helpers used across agents."""
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import gitlab

_gl: gitlab.Gitlab | None = None


def get_gl() -> gitlab.Gitlab:
    global _gl
    if _gl is None:
        _gl = gitlab.Gitlab(
            url=os.environ.get("GITLAB_URL", "https://gitlab.com"),
            private_token=os.environ["GITLAB_TOKEN"],
        )
        _gl.auth()
    return _gl


def get_project(project_id: str | int | None = None):
    gl = get_gl()
    pid = project_id or os.environ["GITLAB_PROJECT_ID"]
    return gl.projects.get(pid)


# ── Digest helpers ────────────────────────────────────────────────────────────

def get_merged_mrs(project, since: datetime) -> list[dict]:
    mrs = project.mergerequests.list(
        state="merged",
        updated_after=since.isoformat(),
        order_by="updated_at",
        sort="desc",
        per_page=100,
        get_all=True,
    )
    return [
        {
            "iid": mr.iid,
            "title": mr.title,
            "author": mr.author["name"],
            "merged_at": mr.merged_at,
            "web_url": mr.web_url,
            "labels": mr.labels,
        }
        for mr in mrs
    ]


def get_closed_issues(project, since: datetime) -> list[dict]:
    issues = project.issues.list(
        state="closed",
        updated_after=since.isoformat(),
        order_by="updated_at",
        sort="desc",
        per_page=100,
        get_all=True,
    )
    return [
        {
            "iid": issue.iid,
            "title": issue.title,
            "author": issue.author["name"],
            "closed_at": issue.closed_at,
            "web_url": issue.web_url,
            "labels": issue.labels,
            "assignees": [a["name"] for a in issue.assignees],
        }
        for issue in issues
    ]


def get_pipeline_summary(project, since: datetime) -> dict:
    pipelines = project.pipelines.list(
        updated_after=since.isoformat(),
        per_page=100,
        get_all=True,
    )
    total = len(pipelines)
    passed = sum(1 for p in pipelines if p.status == "success")
    failed = sum(1 for p in pipelines if p.status == "failed")
    return {"total": total, "passed": passed, "failed": failed}


def get_commits(project, since: datetime) -> list[dict]:
    commits = project.commits.list(
        since=since.isoformat(),
        per_page=100,
        get_all=True,
    )
    return [
        {
            "short_id": c.short_id,
            "title": c.title,
            "author_name": c.author_name,
            "created_at": c.created_at,
        }
        for c in commits
    ]


# ── MR diff helper (Security Agent) ──────────────────────────────────────────

def get_mr_diff(project, mr_iid: int) -> str:
    mr = project.mergerequests.get(mr_iid)
    diffs = mr.diffs.list()
    chunks = []
    for diff in diffs[:20]:          # cap at 20 files
        for d in diff.diffs[:5]:     # cap at 5 hunks per file
            chunks.append(f"### {d['new_path']}\n{d['diff']}")
    return "\n\n".join(chunks)


def post_mr_comment(project, mr_iid: int, body: str) -> None:
    mr = project.mergerequests.get(mr_iid)
    mr.notes.create({"body": body})


# ── Pipeline failure helper (Insight Agent) ───────────────────────────────────

def get_failed_jobs(project, pipeline_id: int) -> list[dict]:
    pipeline = project.pipelines.get(pipeline_id)
    jobs = pipeline.jobs.list(scope=["failed"], get_all=True)
    return [
        {
            "name": j.name,
            "stage": j.stage,
            "failure_reason": j.failure_reason,
            "web_url": j.web_url,
        }
        for j in jobs
    ]
