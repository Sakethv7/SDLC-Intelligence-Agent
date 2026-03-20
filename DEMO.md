# SDLC Intelligence Agent — Demo Script

> This guide is for a human reviewer (HITL) evaluating the project. It walks through what the system does, how to verify each agent, and what to look for as evidence that it's working.

---

## What You're Looking At

SDLC Intelligence Agent is an event-driven AI system that listens to GitLab activity and automatically:

| When this happens in GitLab... | This agent runs... | And does this... |
|---|---|---|
| A merge request is opened | Security Agent | Scans the diff for vulnerabilities, posts findings as an MR comment |
| A reviewer is assigned to an MR | Compliance Agent | Checks a 10-point delivery checklist, posts pass/warn/fail table |
| A CI/CD pipeline fails | Insight Agent | Analyzes job logs, identifies root cause, posts to Slack + uploads HTML report |
| Every Monday at 09:00 (or manually) | Digest Agent | Synthesizes the week's MRs, issues, commits, and pipeline health into a Slack summary |

No chat interface. No manual prompting. The agents act on their own when events occur.

---

## Prerequisites

Before running anything, make sure you have:

- [ ] Python 3.11+
- [ ] A GitLab account with a project you can test against
- [ ] A GitLab personal access token (scopes: `api`, `read_repository`)
- [ ] An Anthropic API key
- [ ] A Slack incoming webhook URL (optional but recommended to see Slack outputs)

---

## Step 1 — Setup

```bash
# Clone the repo
git clone <repo-url>
cd "SDLC Intelligence Agent"

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment config
cp .env.example .env
```

Open `.env` and set these minimum required values:

```env
ANTHROPIC_API_KEY=your_key_here
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=your_pat_here
GITLAB_PROJECT_ID=your_project_id_here
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

---

## Step 2 — Run Tests (Verify Everything Works)

```bash
python -m pytest -q
```

**Expected output:** All 4 test suites pass — security, compliance, insight, digest.

This confirms the agents, RAG pipeline, and tools layer are all wired correctly without needing live GitLab/Slack calls.

---

## Step 3 — Start the Webhook Server

```bash
uvicorn server:app --reload --port 8080
```

Verify it's running:

```bash
curl http://localhost:8080/health
```

**Expected:** `{"status":"ok"}`

---

## Step 4 — Demo Each Agent

### Agent 1: Security Agent
**Trigger:** MR opened

```bash
curl -X POST http://localhost:8080/webhook/gitlab \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "mr_opened",
    "project_id": YOUR_PROJECT_ID,
    "mr_iid": YOUR_MR_IID
  }'
```

**What to look for:**
- A new comment appears on the GitLab MR with security findings
- Verdict is one of: `✅ APPROVE`, `⚠️ REQUEST_CHANGES`, or `🚫 BLOCK`
- Findings are color-coded by severity (CRITICAL 🔴, HIGH, MEDIUM 🟡, LOW 🟢)
- If verdict is BLOCK or REQUEST_CHANGES, a Slack alert fires

> **How it works under the hood:** The agent fetches the MR diff, retrieves relevant policy chunks from the RAG store (sentence-transformers embeddings over `policy_docs/`), and sends diff + policy context to Claude Sonnet for analysis.

---

### Agent 2: Compliance Agent
**Trigger:** Reviewer assigned to an MR

```bash
curl -X POST http://localhost:8080/webhook/gitlab \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "reviewer_assigned",
    "project_id": YOUR_PROJECT_ID,
    "mr_iid": YOUR_MR_IID
  }'
```

**What to look for:**
- A new comment appears on the GitLab MR with a checklist table
- Each of the 10 checklist items shows PASS ✅, WARN ⚠️, or FAIL ❌
- Overall verdict: `PASS`, `WARN`, or `FAIL`
- On FAIL, a Slack alert fires

**The 10-point checklist covers:**
1. Branch naming convention (`feat/`, `fix/`, `chore/`, etc.)
2. Linked issue (`#123`, `Closes`, `Fixes` keywords)
3. Labels applied
4. Description quality
5. Test coverage evidence
6. WIP/Draft status
7. Target branch correctness
8. Documentation updates
9. File count under 20
10. Assignee assigned

> **How it works under the hood:** Claude Haiku evaluates the MR metadata against the checklist — cost-optimized for this structured task.

---

### Agent 3: Insight Agent
**Trigger:** Pipeline failure

```bash
curl -X POST http://localhost:8080/webhook/gitlab \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "pipeline_failed",
    "project_id": YOUR_PROJECT_ID,
    "pipeline_id": YOUR_PIPELINE_ID
  }'
```

**What to look for:**
- A Slack message appears with:
  - Root cause summary
  - Failure type classification (Flaky Test / Dependency / Config / Code Bug / Timeout / Permission)
  - Recurrence risk: 🔴 HIGH / 🟡 MEDIUM / 🟢 LOW
  - Link to the HTML report (if GCS is configured)
- A `pipeline_report.html` file is generated locally (and uploaded to GCS if `GCS_BUCKET` is set)
- If 3+ recent failures are detected, a trend summary is also generated

> **How it works under the hood:** The agent fetches failed job logs (last 60 lines per job), pulls 7-day failure history, and sends everything to Claude Sonnet for root cause analysis. Trend detection uses Claude Haiku.

---

### Agent 4: Digest Agent
**Trigger:** Weekly schedule or manual

```bash
curl -X POST http://localhost:8080/webhook/digest \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": YOUR_PROJECT_ID,
    "weeks_back": 1,
    "post_slack": true
  }'
```

**What to look for:**
- A Slack message with a structured weekly digest containing:
  - Sprint Highlights (3-5 most impactful items)
  - Issues Closed (grouped by theme)
  - MRs Merged (key contributions with authors)
  - Pipeline Health (pass rate %, notable failures)
  - Risks & Watch Items
  - Next Steps / Recommendations
- Digest is bounded to ~600 words for readability

> **How it works under the hood:** The agent pulls up to 30 merged MRs, 30 closed issues, 20 commits, and pipeline stats from the past week, then passes the summary to Claude Sonnet for narrative synthesis.

---

## Step 5 — Run Triggers Directly (Alternative to Webhook)

You can also invoke agents directly without the webhook server:

```bash
# Weekly digest
python -m triggers.weekly_cron

# Security + Compliance on an MR
python -m triggers.reviewer_assignment

# Compliance only
python -m triggers.reviewer_assignment --compliance

# Pipeline failure analysis
python -m triggers.pipeline_failure
```

---

## Step 6 — Check Token Usage Log

After any agent run, check `token_usage.jsonl` in the project root:

```bash
cat token_usage.jsonl
```

Each line is a JSON record showing:
- Which model was called (`claude-sonnet-4-6` or `claude-haiku-4-5-20251001`)
- Input and output token counts
- Estimated USD cost

This is the system's built-in cost accountability — every inference call is logged.

---

## What Good Output Looks Like

| Agent | GitLab | Slack | Artifact |
|---|---|---|---|
| Security | MR comment with verdict + findings table | Alert on BLOCK/REQUEST_CHANGES | — |
| Compliance | MR comment with 10-point checklist table | Alert on FAIL | — |
| Insight | Optional MR comment | Rich message with root cause + risk | `pipeline_report.html` (local + GCS) |
| Digest | — | Full sprint narrative message | — |

---

## Architecture at a Glance

```
GitLab Event
     │
     ▼
FastAPI Webhook Server (server.py)
     │
     ▼
Orchestrator (orchestrator.py)
     │
     ├── mr_opened        → Security Agent + Compliance Agent
     ├── reviewer_assigned → Compliance Agent
     ├── pipeline_failed  → Insight Agent
     └── weekly_digest    → Digest Agent
          │
          ▼
     Tools Layer
     ├── anthropic_client  → Claude API (or GitLab AI Gateway)
     ├── gitlab_client     → GitLab REST API
     ├── slack_notifier    → Slack Block Kit
     ├── gcs_client        → Google Cloud Storage
     └── token_tracker     → Cost logging
```

---

## Common Issues

| Issue | Fix |
|---|---|
| `401 Unauthorized` from GitLab | Check `GITLAB_TOKEN` has `api` scope |
| Slack message not appearing | Verify `SLACK_WEBHOOK_URL` is correct and active |
| RAG store empty / no policy chunks | Run any Security Agent call once — it auto-ingests `policy_docs/` on first run |
| `GCS_BUCKET` not set | HTML report saves locally only (`pipeline_report.html`), no GCS upload — this is fine |
| Embedding model download slow | First run downloads `all-MiniLM-L6-v2` from HuggingFace — subsequent runs use cache |

---

## GitLab AI Catalog Artifacts

All four agents are **live in the GitLab AI Hackathon catalog at `v1.0.0`** and enabled in the participant project (`gitlab-ai-hackathon/participants/35468228`).

| File | Type | Catalog Status |
|---|---|---|
| `agents/sdlc-security-agent.yml` | GitLab Duo Agent | ✅ Published & enabled |
| `agents/sdlc-compliance-agent.yml` | GitLab Duo Agent | ✅ Published & enabled |
| `agents/sdlc-insight-agent.yml` | GitLab Duo Agent | ✅ Published & enabled |
| `agents/sdlc-digest-agent.yml` | GitLab Duo Agent | ✅ Published & enabled |
| `flows/sdlc-review-flow.yml` | GitLab Duo Flow | ✅ Published |

### How Publishing Works

Pushing a Git tag triggers the `catalog-sync` CI component which:
1. Validates YAML schemas (`validate-items` job)
2. Checks for placeholder content (`placeholder-test` job)
3. Publishes to the catalog and enables in the project (`catalog-sync` job)

### Testing Agents via Duo Chat

You can interact with any of the four agents directly through GitLab Duo Chat — no webhook server needed:

1. Navigate to the project: `gitlab.com/gitlab-ai-hackathon/participants/35468228`
2. Click the **Duo Chat icon** (bottom-left of the page)
3. Click the agent name at the top to open the agent picker
4. Search **SDLC** and select an agent
5. Send a message — e.g. paste a code snippet and ask the Security Agent to review it

### Verify in Project UI

To confirm agents are enabled:
- Go to **Automate → Agents → Enabled tab** in the project sidebar
- All four SDLC agents should appear listed as enabled

---

*Built for the GitLab AI Hackathon — GitLab & Anthropic category.*
