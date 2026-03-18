"""Unit tests for the Security Agent RAG store and agent."""
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents.security_agent import rag_store


@pytest.fixture(autouse=True)
def tmp_store(monkeypatch):
    """Redirect the RAG store to a temp directory for each test."""
    tmp = tempfile.mkdtemp()
    monkeypatch.setattr(rag_store, "STORE_DIR", Path(tmp) / "store")
    yield
    shutil.rmtree(tmp)


def test_chunk_basic():
    chunks = rag_store._chunk("a" * 1000)
    assert len(chunks) > 1
    assert all(len(c) <= rag_store.CHUNK_SIZE for c in chunks)


def test_ingest_and_retrieve(tmp_path):
    doc = tmp_path / "policy.md"
    doc.write_text("Never hardcode API keys or secrets in source code. Use environment variables.")
    rag_store.ingest_file(doc)

    results = rag_store.retrieve("hardcoded secrets in code")
    assert len(results) > 0
    assert "secrets" in results[0]["text"].lower() or "hardcode" in results[0]["text"].lower()


def test_ingest_directory(tmp_path):
    (tmp_path / "a.md").write_text("Use parameterized queries to prevent SQL injection.")
    (tmp_path / "b.md").write_text("Always validate user input at API boundaries.")
    counts = rag_store.ingest_directory(tmp_path)
    assert sum(counts.values()) >= 2


def test_store_size_starts_empty():
    assert rag_store.store_size() == 0


@patch("agents.security_agent.agent.slack_notifier")
@patch("agents.security_agent.agent.anthropic_client")
@patch("agents.security_agent.agent.gitlab_client")
def test_security_agent_approve(mock_gl, mock_anthropic, mock_slack, tmp_path, monkeypatch):
    monkeypatch.setattr(rag_store, "STORE_DIR", tmp_path / "store")
    monkeypatch.setenv("POLICY_DOCS_DIR", str(tmp_path))

    mock_project = MagicMock()
    mock_gl.get_project.return_value = mock_project
    mock_gl.get_mr_diff.return_value = "- old_line\n+ new_line"
    mock_anthropic.complete.return_value = (
        "## 🔐 Security Scan Results\n### Verdict\nAPPROVE"
    )

    from agents.security_agent.agent import SecurityAgent
    result = SecurityAgent().run({"mr_iid": 1, "post_comment": False, "post_slack": False})

    assert result["status"] == "ok"
    assert result["verdict"] == "APPROVE"
    mock_slack.post_alert.assert_not_called()
