#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenRouter API client."""

import asyncio
from typing import Any, Dict, List, Optional

import aiohttp

from .base import BaseLLMClient


class OpenRouterClient(BaseLLMClient):
    """Client for OpenRouter API."""

    def _modify_messages_for_retry(
        self, messages: List[Dict[str, str]], retry_count: int
    ) -> List[Dict[str, str]]:
        """Modify messages slightly on retry to encourage a response.

        Args:
            messages: Original messages
            retry_count: Current retry count

        Returns:
            Modified messages with additional prompting
        """
        modified = messages.copy()

        # Add encouragement prefix to the last user message
        for i in range(len(modified) - 1, -1, -1):
            if modified[i]["role"] == "user":
                original_content = modified[i]["content"]

                # Vary the encouragement based on retry count to avoid repetition
                if retry_count % 3 == 1:
                    prefix = "重要提示：请务必提供回答。即使信息不完整，也请基于现有信息给出你的最佳答案。\n\n"
                elif retry_count % 3 == 2:
                    prefix = "注意：你必须回答这个问题。请不要返回空响应，给出你的分析和答案。\n\n"
                else:
                    prefix = "请确保提供完整的回答。不要留空，请基于问题内容给出详细的答复。\n\n"

                modified[i] = {"role": "user", "content": prefix + original_content}
                break

        return modified

    async def call(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        retry_count: int = 0,
        response_format: Optional[Dict[str, str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        plugins: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> str:
        """Call OpenRouter API.

        Args:
            messages: List of message dictionaries
            model: Model name (uses config default if None)
            reasoning_effort: Reasoning effort level
            retry_count: Current retry attempt
            response_format: Optional response format (e.g. {"type": "json_object"})
            tools: Optional list of tools
            plugins: Optional list of plugins (e.g. web search)
            **kwargs: Additional parameters

        Returns:
            Response text from the model

        Raises:
            aiohttp.ClientResponseError: If API returns error after retries
            ValueError: If response format is invalid
        """
        if model is None:
            model = self.config.judge_model

        headers = {
            "Authorization": f"Bearer {self.config.router_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.get_max_tokens_for_model(model),
        }

        # Add sampling parameters if configured
        if self.config.top_p is not None:
            payload["top_p"] = self.config.top_p
        if self.config.top_k is not None:
            payload["top_k"] = self.config.top_k
        if self.config.min_p is not None:
            payload["min_p"] = self.config.min_p
        if self.config.frequency_penalty is not None:
            payload["frequency_penalty"] = self.config.frequency_penalty
        if self.config.presence_penalty is not None:
            payload["presence_penalty"] = self.config.presence_penalty
        if self.config.repetition_penalty is not None:
            payload["repetition_penalty"] = self.config.repetition_penalty

        if reasoning_effort:
            payload["extra_body"] = {"reasoning": {"effort": reasoning_effort}}

        if response_format:
            payload["response_format"] = response_format

        if tools:
            payload["tools"] = tools

        if plugins:
            payload["plugins"] = plugins

        session = kwargs.get("session")
        if not session:
            raise ValueError("Session is required for OpenRouter client")

        try:
            proxy = self.config.proxy
            async with session.post(
                self.config.router_api_base,
                headers=headers,
                json=payload,
                proxy=proxy,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    if retry_count >= self.config.retry_times:
                        from ..utils import print_warning

                        print_warning(
                            f"API error {response.status}: {error_text[:300]}"
                        )
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

                # Normalize content to string
                if content is None:
                    content = ""
                content = str(content).strip()

                # Some models put content in reasoning field
                if not content:
                    reasoning = message.get("reasoning", "")
                    if reasoning is not None:
                        reasoning = str(reasoning).strip()
                        if reasoning:
                            content = reasoning

                if not content:
                    raise ValueError("API returned empty content")

                # Update statistics
                if "usage" in result:
                    usage = result["usage"]
                    # Map OpenRouter specific fields to standard fields if missing
                    if "input_tokens" in usage and "prompt_tokens" not in usage:
                        usage["prompt_tokens"] = usage["input_tokens"]
                    if "output_tokens" in usage and "completion_tokens" not in usage:
                        usage["completion_tokens"] = usage["output_tokens"]
                    self.update_token_usage(usage, model_name=model)

                self.increment_api_calls()
                return content

        except aiohttp.ClientResponseError as e:
            if retry_count >= self.config.retry_times:
                if retry_count >= self.config.retry_times:
                    from ..utils import print_warning

                    print_warning(
                        f"API error details: status={e.status}, message={e.message}"
                    )
                raise
            await asyncio.sleep(self.config.retry_delay)
            return await self.call(
                messages, model, reasoning_effort, retry_count + 1, **kwargs
            )
        except Exception as e:
            if retry_count < self.config.retry_times:
                # If we got an empty content error, modify the prompt slightly to encourage a response
                if "empty content" in str(e).lower():
                    modified_messages = self._modify_messages_for_retry(
                        messages, retry_count
                    )
                    await asyncio.sleep(self.config.retry_delay)
                    return await self.call(
                        modified_messages,
                        model,
                        reasoning_effort,
                        retry_count + 1,
                        **kwargs,
                    )
                else:
                    await asyncio.sleep(self.config.retry_delay)
                    return await self.call(
                        messages, model, reasoning_effort, retry_count + 1, **kwargs
                    )
            else:
                raise
