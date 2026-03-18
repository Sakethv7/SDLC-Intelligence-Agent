"""Abstract base class all sub-agents inherit from."""
from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    name: str = "base"

    @abstractmethod
    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the agent.

        Args:
            context: Trigger-specific payload (MR iid, pipeline id, sprint dates, …)

        Returns:
            Result dict with at minimum {"status": "ok"|"error", "output": str}
        """
        ...
