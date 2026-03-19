# SDLC Intelligence Agent

SDLC Intelligence Agent is a GitLab-native orchestration layer for AI agents that remove friction from the software delivery lifecycle. Instead of acting like a chat assistant, it reacts to real GitLab events and takes action automatically across merge requests, pipelines, and team reporting.

## What Problem It Solves

AI can already write code. The larger bottlenecks are everything around code:

- security review arrives too late
- merge requests lack process hygiene
- pipeline failures take too long to triage
- teams lose visibility across weekly delivery progress

This project packages those bottlenecks into event-driven agents that operate directly in GitLab workflows.

## How It Works

The system listens for GitLab activity and dispatches work to specialized agents:

- `Security Agent`
  Scans merge request diffs against internal policy documents and OWASP guidance, then posts findings to the merge request and optionally Slack.
- `Compliance Agent`
  Reviews merge request metadata and change context against a release/process checklist when reviewers are assigned.
- `Insight Agent`
  Investigates failed pipelines, summarizes probable root causes, estimates recurrence risk, posts alerts, and generates an HTML incident report artifact.
- `Digest Agent`
  Builds a weekly engineering digest from merged MRs, closed issues, commits, and pipeline pass/fail trends.

## Trigger Map

- MR opened -> `Security Agent` + `Compliance Agent`
- Reviewer assigned -> `Compliance Agent`
- Pipeline failed -> `Insight Agent`
- Weekly schedule / manual trigger -> `Digest Agent`

Core orchestration lives in [orchestrator.py](orchestrator.py) and the webhook entrypoint lives in [server.py](server.py).

## GitLab Agent Integration

The repository includes a GitLab agent configuration at [.gitlab/agents/sdlc-intelligence/config.yaml](.gitlab/agents/sdlc-intelligence/config.yaml) for project access. The rest of the automation is implemented as Python event handlers and webhook-triggered workflows so it can run both locally and inside GitLab CI.

## GitLab AI Catalog

All four agents and the end-to-end review flow are published as GitLab Duo catalog artifacts:

| File | Type | Description |
|---|---|---|
| [agents/sdlc-security-agent.yml](agents/sdlc-security-agent.yml) | Agent | MR diff security scanner |
| [agents/sdlc-compliance-agent.yml](agents/sdlc-compliance-agent.yml) | Agent | Delivery checklist reviewer |
| [agents/sdlc-insight-agent.yml](agents/sdlc-insight-agent.yml) | Agent | Pipeline failure analyst |
| [agents/sdlc-digest-agent.yml](agents/sdlc-digest-agent.yml) | Agent | Weekly sprint digest generator |
| [flows/sdlc-review-flow.yml](flows/sdlc-review-flow.yml) | Flow | Security + compliance + summary, sequential |

These definitions run on the GitLab Duo Agent Platform, which uses Anthropic Claude models through GitLab's AI infrastructure.

## Anthropic through GitLab

The Python webhook server can route all Claude inference through the GitLab AI Gateway instead of calling the Anthropic API directly. Set `GITLAB_AI_GATEWAY_URL` in your environment:

```bash
# GitLab.com
GITLAB_AI_GATEWAY_URL=https://cloud.gitlab.com/ai/v1
GITLAB_AI_GATEWAY_TOKEN=your_gitlab_pat

# Self-hosted GitLab
GITLAB_AI_GATEWAY_URL=https://your-gitlab.example.com/ai/v1
```

When `GITLAB_AI_GATEWAY_URL` is set, the `anthropic_client` module configures the SDK to use the gateway as its base URL. Leaving it blank falls back to the direct Anthropic API.

## Google Cloud Deployment

The webhook server ships as a container that deploys to Cloud Run in one command.

### Deploy to Cloud Run

```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions="_REGION=us-central1,_SERVICE=sdlc-intelligence-agent,_GCP_PROJECT=your-project"
```

The CI/CD pipeline includes a `deploy-cloud-run` job (manual trigger on main) that runs this automatically via a service account.

### Cloud Storage for Reports

When `GCS_BUCKET` is set, the Insight Agent uploads each HTML pipeline failure report to Google Cloud Storage after writing it locally as a CI artifact:

```
gs://<GCS_BUCKET>/pipeline-reports/<pipeline_id>.html
```

Configure in `.env`:
```bash
GCP_PROJECT_ID=your_gcp_project_id
GCS_BUCKET=your_gcs_bucket_name
```

## Sustainability

This project is designed to minimise unnecessary compute. See [SUSTAINABILITY.md](SUSTAINABILITY.md) for the full breakdown. Key choices:

- **Model tiering**: `claude-haiku` for structured/classification tasks, `claude-sonnet` for complex reasoning
- **Input truncation**: diffs capped at 20 files / 5 hunks, logs at 60 lines — no unbounded prompt growth
- **RAG over full injection**: Security Agent retrieves only relevant policy chunks (60–80% token reduction vs. injecting the full policy corpus)
- **Event-driven only**: zero LLM calls when no GitLab events occur
- **Token usage logged**: every run writes `token_usage.jsonl` as a CI artifact for cost accountability

## Architecture

1. GitLab emits an event or scheduled job.
2. The webhook server or CI trigger builds a normalized context payload.
3. The orchestrator dispatches the payload to the correct specialist agent.
4. The agent fetches GitLab data, runs LLM analysis, and takes action.
5. Results are posted back to GitLab, Slack, and optional artifacts.

## Repository Layout

- [agents/](agents/) specialist agents and prompts
- [triggers/](triggers/) CLI/CI entrypoints
- [tools/](tools/) GitLab, Slack, and Anthropic integrations
- [policy_docs/](policy_docs/) local security/compliance knowledge base
- [tests/](tests/) unit tests

## Setup

### Requirements

- Python `3.11+`
- GitLab personal access token with access to the target project
- Anthropic API key
- Slack incoming webhook(s)

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Configure

Set the values in [.env.example](.env.example):

- `ANTHROPIC_API_KEY`
- `GITLAB_URL`
- `GITLAB_TOKEN`
- `GITLAB_PROJECT_ID`
- `SLACK_WEBHOOK_URL`
- `SLACK_WEBHOOK_URL_ALERTS`
- `GITLAB_WEBHOOK_SECRET`

## Running Locally

Start the webhook server:

```bash
uvicorn server:app --reload --port 8080
```

Run tests:

```bash
python -m pytest -q
```

Run individual triggers:

```bash
python -m triggers.weekly_cron
python -m triggers.reviewer_assignment
python -m triggers.reviewer_assignment --compliance
python -m triggers.pipeline_failure
```

## Example Webhook Usage

Manual digest trigger:

```bash
curl -X POST http://localhost:8080/webhook/digest \
  -H "Content-Type: application/json" \
  -d '{"project_id":"123","weeks_back":1,"post_slack":false}'
```

GitLab webhook endpoint:

```text
POST /webhook/gitlab
Header: X-Gitlab-Token: <your secret>
```

## Why This Is Different

- Event-driven, not chat-only
- Multi-agent orchestration instead of a single generic assistant
- Designed around software delivery bottlenecks, not generic Q&A
- Produces actions and artifacts inside developer workflows

## Reliability Notes

The Security Agent uses local vector retrieval over policy documents. When a transformer embedding model is unavailable, the repo falls back to a deterministic local embedder so tests and restricted environments still work.

## Testing

Unit tests cover:

- digest formatting and delivery path
- compliance verdict handling
- insight failure analysis and trend behavior
- security policy ingestion and retrieval

## Submission Summary

This project is a digital teammate for GitLab teams:

- it reviews risk when code changes arrive
- it checks process quality when review ownership changes
- it diagnoses broken pipelines when delivery fails
- it summarizes team output on a recurring cadence

See [SUBMISSION.md](SUBMISSION.md) for ready-to-paste hackathon submission text.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
