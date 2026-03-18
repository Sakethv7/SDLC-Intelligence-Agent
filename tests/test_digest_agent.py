"""Unit tests for the Digest Agent (mocked dependencies)."""
from unittest.mock import MagicMock, patch

from agents.digest_agent.agent import DigestAgent, _fmt_mrs, _fmt_issues, _fmt_commits


def test_fmt_mrs_empty():
    assert _fmt_mrs([]) == "  (none)"


def test_fmt_mrs():
    mrs = [{"iid": 1, "title": "Add feature", "author": "alice", "labels": ["backend"]}]
    out = _fmt_mrs(mrs)
    assert "!1" in out
    assert "alice" in out
    assert "backend" in out


def test_fmt_issues_empty():
    assert _fmt_issues([]) == "  (none)"


def test_fmt_commits_empty():
    assert _fmt_commits([]) == "  (none)"


@patch("agents.digest_agent.agent.slack_notifier")
@patch("agents.digest_agent.agent.anthropic_client")
@patch("agents.digest_agent.agent.gitlab_client")
def test_digest_agent_run(mock_gl, mock_anthropic, mock_slack):
    mock_project = MagicMock()
    mock_gl.get_project.return_value = mock_project
    mock_gl.get_merged_mrs.return_value = [
        {"iid": 1, "title": "Fix bug", "author": "bob", "labels": []}
    ]
    mock_gl.get_closed_issues.return_value = []
    mock_gl.get_commits.return_value = []
    mock_gl.get_pipeline_summary.return_value = {"total": 10, "passed": 9, "failed": 1}
    mock_anthropic.complete.return_value = "🚀 *Sprint Highlights*\n- Fixed critical bug"

    agent = DigestAgent()
    result = agent.run({"project_id": "123", "post_slack": True})

    assert result["status"] == "ok"
    assert "Sprint Highlights" in result["output"]
    assert result["stats"]["mrs"] == 1
    mock_slack.post.assert_called_once()
