"""Slack Block Kit helper — posts rich messages via incoming webhook."""
import os
import requests

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
SLACK_WEBHOOK_URL_ALERTS = os.environ.get("SLACK_WEBHOOK_URL_ALERTS", SLACK_WEBHOOK_URL)
SLACK_USER_ID = os.environ.get("SLACK_USER_ID", "")

_MAX_BLOCK_CHARS = 2800
_MAX_BLOCKS = 50


def _chunk_text(text: str) -> list[str]:
    """Split long text into Slack-safe blocks."""
    chunks, current = [], []
    length = 0
    for line in text.splitlines(keepends=True):
        if length + len(line) > _MAX_BLOCK_CHARS and current:
            chunks.append("".join(current))
            current, length = [], 0
        current.append(line)
        length += len(line)
    if current:
        chunks.append("".join(current))
    return chunks


def _build_blocks(title: str, body: str, footer: str = "") -> list[dict]:
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": title, "emoji": True}},
        {"type": "divider"},
    ]
    for chunk in _chunk_text(body):
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})
        if len(blocks) >= _MAX_BLOCKS - 2:
            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": "_…message truncated_"}}
            )
            break
    blocks.append({"type": "divider"})
    if footer:
        blocks.append(
            {"type": "context", "elements": [{"type": "mrkdwn", "text": footer}]}
        )
    return blocks


def post(
    title: str,
    body: str,
    footer: str = "",
    webhook_url: str = "",
    mention_user: bool = True,
) -> None:
    url = webhook_url or SLACK_WEBHOOK_URL
    if not url:
        raise ValueError("SLACK_WEBHOOK_URL is not configured")

    mention = f"<@{SLACK_USER_ID}> " if mention_user and SLACK_USER_ID else ""
    payload = {
        "text": f"{mention}{title}",
        "blocks": _build_blocks(title, body, footer),
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()


def post_alert(title: str, body: str, footer: str = "") -> None:
    """Posts to the alerts webhook (pipeline failures, security findings)."""
    post(title, body, footer, webhook_url=SLACK_WEBHOOK_URL_ALERTS)
