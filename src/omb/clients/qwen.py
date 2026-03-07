#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Qwen Deep Research API client."""

import asyncio
import os
from typing import Any, Dict, List, Optional

import aiohttp
import dashscope

from .base import BaseLLMClient


class QwenDeepResearchClient(BaseLLMClient):
    """Client for Qwen Deep Research API using dashscope."""

    def __init__(self, config: Any, token_tracker=None):
        """Initialize Qwen client.

        Args:
            config: Configuration object
            token_tracker: Optional TokenTracker for tracking usage
        """
        super().__init__(config, token_tracker)
        # Set dashscope API key from environment
        if not os.getenv("DASHSCOPE_API_KEY"):
            # Fallback to config if env var is missing, though config might read env var too
            if not self.config.dashscope_api_key:
                raise ValueError("DASHSCOPE_API_KEY environment variable not set")

    async def call(
        self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs
    ) -> str:
        """Call Qwen Deep Research API with two-round conversation.

        Args:
            messages: List of message dictionaries
            model: Model name (not used, always uses qwen-deep-research)
            **kwargs: Additional parameters

        Returns:
            Response text from the model
        """
        # Extract prompt from messages
        prompt = ""
        for msg in messages:
            if msg.get("role") == "user":
                prompt = msg.get("content", "")
                break

        # Run synchronous call in executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self._call_sync, prompt)

        self.increment_api_calls()
        return response

    def _call_sync(self, prompt: str) -> str:
        """Synchronous call to Qwen Deep Research with two-round conversation.

        Args:
            prompt: User prompt

        Returns:
            Response text from the model
        """
        # Enhanced prompt to prevent asking questions
        enhanced_prompt = f"""请直接回答以下问题，不要向我提问，不要要求我提供更多信息。请基于问题中已有的信息直接给出完整、详细的答案。

{prompt}"""

        messages = [
            {
                "role": "system",
                "content": "你是一个专业的问题解答助手。你必须直接回答问题，禁止向用户提问或要求更多信息。",
            },
            {"role": "user", "content": enhanced_prompt},
        ]

        api_key = self.config.dashscope_api_key or os.getenv("DASHSCOPE_API_KEY")

        # First round
        responses = dashscope.Generation.call(
            api_key=api_key,
            model="qwen-deep-research",
            messages=messages,
            stream=True,
        )

        first_content = ""
        for response in responses:
            if hasattr(response, "output") and response.output:
                message = response.output.get("message", {})
                chunk = message.get("content", "")
                if chunk:
                    first_content += chunk

        # Second round: force no questions
        messages.append({"role": "assistant", "content": first_content})
        messages.append(
            {
                "role": "user",
                "content": "请不要向我提问，直接基于你现有的知识和理解给出完整的答案。如果有不确定的地方，请直接说明你的判断和理由，而不是反问我。",
            }
        )

        # Second round call
        responses = dashscope.Generation.call(
            api_key=api_key,
            model="qwen-deep-research",
            messages=messages,
            stream=True,
        )

        second_content = ""
        for response in responses:
            if hasattr(response, "output") and response.output:
                message = response.output.get("message", {})
                chunk = message.get("content", "")
                if chunk:
                    second_content += chunk

        return second_content


class QwenClient(BaseLLMClient):
    """Client for Qwen model like: qwen3-max-2026-01-23."""

    async def call(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        retry_count: int = 0,
        response_format: Optional[Dict[str, str]] = None,
        enable_search: bool = False,
        **kwargs,
    ) -> str:
        """Call Qwen API.

        Args:
            messages: List of message dictionaries
            model: Model name
            reasoning_effort: Reasoning effort level (not used here)
            retry_count: Current retry attempt
            response_format: Optional response format
            enable_search: Whether to enable search
            **kwargs: Additional parameters

        Returns:
            Response text from the model
        """
        if model is None:
            model = "qwen3-max-2026-01-23"

        headers = {
            "Authorization": f"Bearer {self.config.dashscope_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "enable_thinking": True,
            "enable_search": enable_search,
        }

        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature

        # Add sampling parameters if configured
        if self.config.top_p is not None:
            payload["top_p"] = self.config.top_p
        if self.config.top_k is not None:
            payload["top_k"] = self.config.top_k
        if self.config.repetition_penalty is not None:
            payload["repetition_penalty"] = self.config.repetition_penalty

        # OpenRouter uses max_tokens, Qwen typically supports it too.
        # But if not set or default, maybe leave it out or set it.
        # self.config.max_tokens defaults to 128000 or 65536 in config.
        # I'll add it if it seems safe.
        # payload["max_tokens"] = self.config.max_tokens

        session = kwargs.get("session")
        if not session:
            raise ValueError("Session is required for Qwen client")

        try:
            proxy = self.config.proxy
            async with session.post(
                self.config.dashscope_api_base,
                headers=headers,
                json=payload,
                proxy=proxy,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    if retry_count >= self.config.retry_times:
                        from ..utils import print_warning

                        print_warning(f"Qwen API error {response.status}: {error_text[:300]}")
                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=response.status,
                        message=error_text[:100],
                    )
                result = await response.json()

                if "choices" not in result or len(result["choices"]) == 0:
                    raise ValueError(f"Response format error: {result.keys()}")

                message = result["choices"][0]["message"]
                content = message.get("content", "")

                # Handle reasoning content if separated?
                # For qwen3-max-2026-01-23 with enable_thinking=True, it returns thinking content.
                # Usually we want the final response.
                # If content is empty but reasoning is there?
                # Let's assume standard OpenAI format where content is the answer.
                # If reasoning is separate, we might log it or ignore it depending on needs.
                # For now, just getting content.

                if content is None:
                    content = ""
                content = str(content).strip()

                if not content:
                    # Check if there is reasoning content that we should return instead?
                    reasoning = message.get("reasoning_content", "")
                    if reasoning:
                        # If only reasoning is returned (unlikely), strictly we want the answer.
                        pass
                    raise ValueError("API returned empty content")

                # Update usage
                if "usage" in result:
                    self.update_token_usage(result["usage"], model_name=model)

                self.increment_api_calls()
                return content

        except Exception as e:
            if retry_count < self.config.retry_times:
                await asyncio.sleep(self.config.retry_delay)
                return await self.call(messages, model, reasoning_effort, retry_count + 1, **kwargs)
            else:
                raise
