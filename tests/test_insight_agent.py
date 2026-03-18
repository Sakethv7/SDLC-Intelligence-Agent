"""Unit tests for the Insight Agent."""
from unittest.mock import MagicMock, patch


def _make_pipeline_detail(branch="main", job_count=1):
    return {
        "id": 999,
        "status": "failed",
        "branch": branch,
        "duration": 120,
        "web_url": "https://gitlab.com/test/-/pipelines/999",
        "triggered_by": "alice",
        "failed_jobs": [
            {
                "name": "unit-tests",
                "stage": "test",
                "failure_reason": "script_failure",
                "duration": 45,
                "web_url": "https://gitlab.com/test/-/jobs/1",
                "log_tail": "FAILED: AssertionError: expected 200 got 500\nError: test suite failed",
            }
        ] * job_count,
    }


@patch("agents.insight_agent.agent.slack_notifier")
@patch("agents.insight_agent.agent.anthropic_client")
@patch("agents.insight_agent.agent.gitlab_client")
def test_insight_agent_runs(mock_gl, mock_anthropic, mock_slack):
    mock_gl.get_project.return_value = MagicMock()
    mock_gl.get_pipeline_detail.return_value = _make_pipeline_detail()
    mock_gl.get_recent_pipeline_failures.return_value = []
    mock_anthropic.complete.return_value = (
        "## 🔴 Pipeline Failure Analysis\n"
        "### Root Cause\nUnit test assertion failure.\n"
        "### Recurrence Risk\n**LOW** — isolated failure."
    )

    from agents.insight_agent.agent import InsightAgent
    result = InsightAgent().run({"pipeline_id": 999, "post_slack": True})

    assert result["status"] == "ok"
    assert result["pipeline_id"] == 999
    assert result["failed_jobs"] == 1
    mock_slack.post_alert.assert_called_once()


@patch("agents.insight_agent.agent.slack_notifier")
@patch("agents.insight_agent.agent.anthropic_client")
@patch("agents.insight_agent.agent.gitlab_client")
def test_insight_agent_no_failed_jobs(mock_gl, mock_anthropic, mock_slack):
    mock_gl.get_project.return_value = MagicMock()
    detail = _make_pipeline_detail()
    detail["failed_jobs"] = []
    mock_gl.get_pipeline_detail.return_value = detail

    from agents.insight_agent.agent import InsightAgent
    result = InsightAgent().run({"pipeline_id": 999, "post_slack": False})

    assert result["status"] == "ok"
    assert "No failed jobs" in result["output"]
    mock_slack.post_alert.assert_not_called()


@patch("agents.insight_agent.agent.slack_notifier")
@patch("agents.insight_agent.agent.anthropic_client")
@patch("agents.insight_agent.agent.gitlab_client")
def test_insight_agent_trend_report_fires(mock_gl, mock_anthropic, mock_slack):
    mock_gl.get_project.return_value = MagicMock()
    mock_gl.get_pipeline_detail.return_value = _make_pipeline_detail()
    mock_gl.get_recent_pipeline_failures.return_value = [
        {"id": i, "branch": "main", "created_at": "2026-03-18", "duration": 90, "web_url": f"https://gitlab.com/-/pipelines/{i}"}
        for i in range(5)
    ]
    mock_anthropic.complete.side_effect = [
        "## 🔴 Pipeline Failure Analysis\n### Recurrence Risk\n**HIGH**",
        "Trend: tests failing on main. Fix: pin dependencies.",
    ]

    from agents.insight_agent.agent import InsightAgent
    result = InsightAgent().run({"pipeline_id": 999, "post_slack": True})

    assert result["trend_report"] is not None
    assert mock_slack.post_alert.call_count == 2   # analysis + trend
