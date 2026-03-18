"""Thin wrapper around the Anthropic SDK, configured once for the whole project."""
import os
import anthropic

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
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
    return response.content[0].text.strip()
