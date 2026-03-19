"""Thin wrapper around the Anthropic SDK, configured once for the whole project.

Supports two routing modes:
- Direct Anthropic API (default): uses ANTHROPIC_API_KEY
- GitLab AI Gateway: set GITLAB_AI_GATEWAY_URL to route Anthropic calls through
  GitLab's AI infrastructure (e.g. https://cloud.gitlab.com/ai/v1).
  Uses GITLAB_AI_GATEWAY_TOKEN if set, otherwise falls back to ANTHROPIC_API_KEY.
"""
import os
import anthropic

from tools.token_tracker import record

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        gateway_url = os.environ.get("GITLAB_AI_GATEWAY_URL", "").strip()
        if gateway_url:
            token = os.environ.get("GITLAB_AI_GATEWAY_TOKEN") or os.environ["ANTHROPIC_API_KEY"]
            _client = anthropic.Anthropic(api_key=token, base_url=gateway_url)
        else:
            _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def complete(
    prompt: str,
    system: str = "",
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    temperature: float = 0.6,
) -> str:
    """Single-turn completion. Returns the text content of the first block."""
    client = get_client()
    kwargs: dict = dict(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    if system:
        kwargs["system"] = system
    response = client.messages.create(**kwargs)
    record(model=model, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)
    return response.content[0].text.strip()
