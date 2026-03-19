# Devpost Submission Copy

## Project Name

SDLC Intelligence Agent

## Tagline

An event-driven team of AI agents for GitLab that accelerates security review, compliance checks, pipeline triage, and weekly delivery reporting.

## Problem

Software teams are no longer blocked only by writing code. The slowest parts of the delivery lifecycle are the surrounding workflows: security review, compliance process checks, failed pipeline investigation, and status reporting. Those tasks are repetitive, operationally expensive, and often happen too late.

## Solution

SDLC Intelligence Agent turns those bottlenecks into autonomous GitLab workflows. It reacts to merge request events, reviewer assignment changes, pipeline failures, and weekly schedules, then routes the event to a specialized AI agent that can analyze context and take action.

## Features

- `Security Agent` scans merge request diffs using retrieval over internal security policies and OWASP guidance.
- `Compliance Agent` reviews MR metadata, labels, branches, reviewers, and changed files against a delivery checklist.
- `Insight Agent` analyzes failed pipelines, estimates recurrence risk, posts alerts, and generates an HTML incident report.
- `Digest Agent` creates a weekly sprint digest from GitLab merge requests, issues, commits, and pipeline outcomes.
- `Orchestrator` routes GitLab events to the right agent or agent combination.

## How It Works

GitLab webhooks and CI triggers provide event payloads. A FastAPI webhook service and trigger scripts normalize those payloads. The orchestrator dispatches them to purpose-built agents. Each agent pulls the relevant GitLab context, runs LLM-backed analysis, and posts results back into GitLab or Slack.

## Why It Matters

This project is not a chat wrapper around an LLM. It is a workflow automation system that takes action where teams actually lose time:

- before risky code merges
- when process hygiene degrades
- when delivery pipelines fail
- when managers need a coherent update across the week

## What Makes It Technically Interesting

- multi-agent orchestration tied to GitLab events
- RAG-backed security review using local policy documents
- webhook + CI trigger support
- HTML artifact generation for pipeline failure reports
- Slack and GitLab feedback loops built into the workflow

## Built With

- Python
- FastAPI
- Anthropic Claude
- GitLab API
- GitLab CI/CD
- Slack Webhooks
- NumPy
- sentence-transformers

## Impact

The project reduces time spent on repetitive review and operational triage work while making those workflows more consistent. Instead of depending on a human to notice every risk or summarize every failure, the system reacts immediately and leaves structured output inside the tools teams already use.
