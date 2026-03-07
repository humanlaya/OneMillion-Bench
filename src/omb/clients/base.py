#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Base client for LLM API interactions."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from ..tracking import TokenTracker


class BaseLLMClient(ABC):
    """Abstract base class for LLM API clients."""

    def __init__(self, config: Any, token_tracker: Optional["TokenTracker"] = None):
        """Initialize the client.

        Args:
            config: Configuration object
            token_tracker: Optional TokenTracker for tracking usage
        """
        self.config = config
        self.token_tracker = token_tracker
        self.api_calls = 0
        self.total_tokens = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self.last_usage: Optional[Dict[str, int]] = None

    @abstractmethod
    async def call(
        self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs
    ) -> str:
        """Call the LLM API.

        Args:
            messages: List of message dictionaries
            model: Model name (optional)
            **kwargs: Additional parameters

        Returns:
            Response text from the model
        """
        pass

    def update_token_usage(self, usage: Dict[str, int], model_name: Optional[str] = None) -> None:
        """Update token usage statistics.

        Args:
            usage: Usage dictionary with token counts
            model_name: Name of the model (for TokenTracker)
        """
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        # Extract reasoning_tokens from output_tokens_details if available
        reasoning_tokens = 0
        output_tokens_details = usage.get("output_tokens_details")
        if isinstance(output_tokens_details, dict):
            reasoning_tokens = output_tokens_details.get("reasoning_tokens", 0)

        # Store last usage for retrieval
        self.last_usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": usage.get("total_tokens", prompt_tokens + completion_tokens),
            "reasoning_tokens": reasoning_tokens,
        }

        # Update local statistics
        self.total_tokens["prompt_tokens"] += prompt_tokens
        self.total_tokens["completion_tokens"] += completion_tokens
        self.total_tokens["total_tokens"] += usage.get(
            "total_tokens", prompt_tokens + completion_tokens
        )

        # Update global TokenTracker if available
        if self.token_tracker and model_name:
            self.token_tracker.track_usage(model_name, prompt_tokens, completion_tokens)

    def increment_api_calls(self) -> None:
        """Increment API call counter."""
        self.api_calls += 1
        if self.token_tracker:
            self.token_tracker.increment_api_calls()

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics.

        Returns:
            Dictionary with API calls and token usage
        """
        return {"api_calls": self.api_calls, "tokens": self.total_tokens.copy()}
