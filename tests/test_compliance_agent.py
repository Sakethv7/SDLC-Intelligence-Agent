"""Unit tests for the Compliance Agent."""
from unittest.mock import MagicMock, patch, PropertyMock


def _make_mock_mr(**kwargs):
    mr = MagicMock()
    mr.iid = kwargs.get("iid", 1)
    mr.title = kwargs.get("title", "feat: add login")
    mr.source_branch = kwargs.get("source_branch", "feat/add-login")
    mr.target_branch = kwargs.get("target_branch", "main")
    mr.author = {"name": "alice"}
    mr.labels = kwargs.get("labels", ["backend"])
    mr.assignees = [{"name": "alice"}]
    mr.reviewers = [{"name": "bob"}]
    mr.web_url = "https://gitlab.com/test/project/-/merge_requests/1"
    mr.created_at = "2026-03-18T09:00:00Z"
    mr.description = kwargs.get("description", "Closes #42\n\nAdds login feature with tests.")
    mr.changes.return_value = {
        "changes": [{"new_path": "app/auth.py"}, {"new_path": "tests/test_auth.py"}]
    }
    return mr


@patch("agents.compliance_agent.agent.slack_notifier")
@patch("agents.compliance_agent.agent.anthropic_client")
@patch("agents.compliance_agent.agent.gitlab_client")
def test_compliance_pass(mock_gl, mock_anthropic, mock_slack):
    mock_project = MagicMock()
    mock_gl.get_project.return_value = mock_project
    mock_project.mergerequests.get.return_value = _make_mock_mr()
    mock_anthropic.complete.return_value = (
        "## 📋 Compliance Checklist\n\n"
        "| # | Check | Status | Notes |\n"
        "|---|-------|--------|-------|\n"
        "| 1 | Branch naming | ✅ | feat/add-login |\n\n"
        "## Summary\n**Overall: PASS**\nAll checks passed."
    )

    from agents.compliance_agent.agent import ComplianceAgent
    result = ComplianceAgent().run({"mr_iid": 1, "post_comment": False, "post_slack": False})

    assert result["status"] == "ok"
    assert result["verdict"] == "PASS"
    mock_slack.post_alert.assert_not_called()


@patch("agents.compliance_agent.agent.slack_notifier")
@patch("agents.compliance_agent.agent.anthropic_client")
@patch("agents.compliance_agent.agent.gitlab_client")
def test_compliance_fail_notifies_slack(mock_gl, mock_anthropic, mock_slack):
    mock_project = MagicMock()
    mock_gl.get_project.return_value = mock_project
    mock_project.mergerequests.get.return_value = _make_mock_mr(
        source_branch="my-random-branch", labels=[], description=""
    )
    mock_anthropic.complete.return_value = (
        "## 📋 Compliance Checklist\n\n"
        "## Summary\n**Overall: FAIL**\nBranch naming and labels missing.\n\n"
        "## Required Actions\n- Rename branch\n- Add labels"
    )

    from agents.compliance_agent.agent import ComplianceAgent
    result = ComplianceAgent().run({"mr_iid": 2, "post_comment": False, "post_slack": True})

    assert result["verdict"] == "FAIL"
    mock_slack.post_alert.assert_called_once()


@patch("agents.compliance_agent.agent.slack_notifier")
@patch("agents.compliance_agent.agent.anthropic_client")
@patch("agents.compliance_agent.agent.gitlab_client")
def test_compliance_warn_no_slack(mock_gl, mock_anthropic, mock_slack):
    mock_project = MagicMock()
    mock_gl.get_project.return_value = mock_project
    mock_project.mergerequests.get.return_value = _make_mock_mr()
    mock_anthropic.complete.return_value = (
        "## Summary\n**Overall: WARN**\nMinor issues found."
    )

    from agents.compliance_agent.agent import ComplianceAgent
    result = ComplianceAgent().run({"mr_iid": 3, "post_comment": False, "post_slack": True})

    assert result["verdict"] == "WARN"
    mock_slack.post_alert.assert_not_called()
