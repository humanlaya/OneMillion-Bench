"""
Cost calculation and token tracking utilities.
"""

from collections import defaultdict
from typing import Any, Dict, Tuple

from ..config import ConfigManager


class TokenTracker:
    """Tracks token usage and calculates costs."""

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self._reset_counters()

    def _reset_counters(self) -> None:
        """Reset all tracking counters."""
        self._total_tokens = {"prompt": 0, "completion": 0, "total": 0}
        self.model_usage = defaultdict(lambda: {"prompt": 0, "completion": 0, "total": 0})
        self.api_calls = 0

    def track_usage(self, model_name: str, prompt_tokens: int, completion_tokens: int) -> None:
        """Track token usage for a model."""
        total = prompt_tokens + completion_tokens

        # Update model-specific usage
        usage = self.model_usage[model_name]
        usage["prompt"] += prompt_tokens
        usage["completion"] += completion_tokens
        usage["total"] += total

        # Update global totals
        self._total_tokens["prompt"] += prompt_tokens
        self._total_tokens["completion"] += completion_tokens
        self._total_tokens["total"] += total

    def increment_api_calls(self) -> None:
        """Increment API call counter."""
        self.api_calls += 1

    def calculate_cost(self) -> Tuple[float, Dict[str, Dict[str, Any]]]:
        """Calculate total API cost and breakdown."""
        pricing_config = self.config.get_model_pricing()
        default_pricing = self.config.get_default_pricing()

        total_cost = 0.0
        breakdown = {}

        for model_name, usage in self.model_usage.items():
            pricing = pricing_config.get(model_name, default_pricing)

            prompt_cost = (usage["prompt"] / 1_000_000) * pricing.get("input", 0.0)
            completion_cost = (usage["completion"] / 1_000_000) * pricing.get("output", 0.0)
            model_cost = prompt_cost + completion_cost

            breakdown[model_name] = {
                "prompt_tokens": usage["prompt"],
                "completion_tokens": usage["completion"],
                "prompt_cost": prompt_cost,
                "completion_cost": completion_cost,
                "total_cost": model_cost,
            }

            total_cost += model_cost

        return total_cost, breakdown

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive tracking summary."""
        total_cost, cost_breakdown = self.calculate_cost()

        return {
            "total_tokens": self._total_tokens,
            "model_usage": dict(self.model_usage),
            "api_calls": self.api_calls,
            "total_cost": total_cost,
            "cost_breakdown": cost_breakdown,
        }

    def reset(self) -> None:
        """Reset all tracking statistics."""
        self._reset_counters()
