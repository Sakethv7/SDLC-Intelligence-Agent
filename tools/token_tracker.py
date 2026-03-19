"""Token usage tracker for Green Agent sustainability reporting.

Accumulates input/output token counts per model across the process lifetime and
writes a summary to TOKEN_USAGE_LOG (default: token_usage.jsonl) for CI artifact
collection and energy-efficiency reporting.
"""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Cost-per-million-tokens reference (USD) — used only for sustainability reporting
_COST_PER_MTok: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6":        {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 0.25,  "output": 1.25},
    "default":                   {"input": 3.00,  "output": 15.00},
}

_totals: dict[str, dict[str, int]] = defaultdict(lambda: {"input": 0, "output": 0})
_log_path = Path(os.environ.get("TOKEN_USAGE_LOG", "token_usage.jsonl"))


def record(*, model: str, input_tokens: int, output_tokens: int) -> None:
    """Record token usage for a single completion call."""
    _totals[model]["input"] += input_tokens
    _totals[model]["output"] += output_tokens

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    try:
        with _log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        logger.warning("Could not write token usage log to %s", _log_path)


def get_summary() -> dict:
    """Return accumulated usage with estimated cost and carbon context."""
    rows = []
    total_input = total_output = 0
    total_cost = 0.0

    for model, counts in _totals.items():
        rates = _COST_PER_MTok.get(model, _COST_PER_MTok["default"])
        cost = (counts["input"] / 1_000_000 * rates["input"]
                + counts["output"] / 1_000_000 * rates["output"])
        rows.append({
            "model": model,
            "input_tokens": counts["input"],
            "output_tokens": counts["output"],
            "estimated_cost_usd": round(cost, 6),
        })
        total_input += counts["input"]
        total_output += counts["output"]
        total_cost += cost

    return {
        "models": rows,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "estimated_cost_usd": round(total_cost, 6),
    }


def log_summary() -> None:
    """Log accumulated token usage at process end (call from CI cleanup or server shutdown)."""
    summary = get_summary()
    if summary["total_tokens"] == 0:
        return
    logger.info(
        "Token usage summary — total: %d (in: %d, out: %d) | est. cost: $%.4f",
        summary["total_tokens"],
        summary["total_input_tokens"],
        summary["total_output_tokens"],
        summary["estimated_cost_usd"],
    )
    for row in summary["models"]:
        logger.info(
            "  %s: in=%d out=%d cost=$%.4f",
            row["model"], row["input_tokens"], row["output_tokens"], row["estimated_cost_usd"],
        )
