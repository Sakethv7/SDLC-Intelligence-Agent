"""
FastAPI webhook server
======================
Receives GitLab system hooks and routes them to the orchestrator.

Endpoints:
  POST /webhook/gitlab   — GitLab system hook payload
  POST /webhook/digest   — manual digest trigger
  GET  /health           — liveness probe
"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import orchestrator  # noqa: E402 (after dotenv load)

app = FastAPI(title="SDLC Intelligence Agent", version="0.1.0")

GITLAB_SECRET = os.environ.get("GITLAB_WEBHOOK_SECRET", "")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook/digest")
async def trigger_digest(request: Request):
    """Manual or cron-triggered digest."""
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    result = orchestrator.dispatch("weekly_digest", body)
    return JSONResponse(result)


@app.post("/webhook/gitlab")
async def gitlab_webhook(
    request: Request,
    x_gitlab_token: str = Header(default=""),
):
    if GITLAB_SECRET and x_gitlab_token != GITLAB_SECRET:
        raise HTTPException(status_code=401, detail="Invalid token")

    payload = await request.json()
    event = payload.get("object_kind") or payload.get("event_type", "unknown")
    attrs = payload.get("object_attributes", {})

    context = {
        "project_id": payload.get("project", {}).get("id"),
        "mr_iid": attrs.get("iid"),
        "pipeline_id": attrs.get("id") if event == "pipeline" else None,
    }

    if event == "merge_request":
        action = attrs.get("action", "")
        if action == "open":
            result = orchestrator.dispatch("mr_opened", context)
        elif action == "update" and payload.get("assignees"):
            result = orchestrator.dispatch("reviewer_assigned", context)
        else:
            return JSONResponse({"status": "ignored", "event": event, "action": action})

    elif event == "pipeline" and attrs.get("status") == "failed":
        result = orchestrator.dispatch("pipeline_failed", context)

    else:
        return JSONResponse({"status": "ignored", "event": event})

    return JSONResponse(result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
