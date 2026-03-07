#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ling-1T API client."""

from typing import Any, Dict, List, Optional

import aiohttp

from .base import BaseLLMClient


class Ling1TClient(BaseLLMClient):
    """Client for Ling-1T API."""

    async def call(
        self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs
    ) -> str:
        """Call Ling-1T API with two-round conversation.

        Args:
            messages: List of message dictionaries
            model: Model name (not used, always uses Ling-1T)
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

        session = kwargs.get("session")
        if not session:
            raise ValueError("Session is required for Ling-1T client")

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

        headers = {
            "Authorization": f"Bearer {self.config.ling_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "Ling-1T",
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.get_max_tokens_for_model("Ling-1T"),
        }

        # Add sampling parameters if configured
        if self.config.top_p is not None:
            payload["top_p"] = self.config.top_p
        if self.config.top_k is not None:
            payload["top_k"] = self.config.top_k
        if self.config.frequency_penalty is not None:
            payload["frequency_penalty"] = self.config.frequency_penalty
        if self.config.presence_penalty is not None:
            payload["presence_penalty"] = self.config.presence_penalty

        # First round
        async with session.post(
            self.config.ling_api_base,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
        ) as response:
            response.raise_for_status()
            result = await response.json()

            if "choices" not in result or len(result["choices"]) == 0:
                raise ValueError(f"响应格式错误: {result.keys()}")

            message = result["choices"][0]["message"]
            first_response = message.get("content", "")

            if first_response is None:
                first_response = ""
            first_response = str(first_response).strip()

            if not first_response:
                raise ValueError("API 返回空内容")

        # Second round: force no questions
        messages.append({"role": "assistant", "content": first_response})
        messages.append(
            {
                "role": "user",
                "content": "请不要向我提问，直接基于你现有的知识和理解给出完整的答案。如果有不确定的地方，请直接说明你的判断和理由，而不是反问我。",
            }
        )

        payload["messages"] = messages

        # Second round call
        async with session.post(
            self.config.ling_api_base,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
        ) as response:
            response.raise_for_status()
            result = await response.json()

            if "choices" not in result or len(result["choices"]) == 0:
                raise ValueError(f"响应格式错误: {result.keys()}")

            message = result["choices"][0]["message"]
            content = message.get("content", "")

            if content is None:
                content = ""
            content = str(content).strip()

            if not content:
                raise ValueError("API 返回空内容")

            # Update statistics (both rounds counted as one call)
            if "usage" in result:
                usage = result["usage"]
                # Map API-specific fields to standard fields if needed
                if "input_tokens" in usage and "prompt_tokens" not in usage:
                    usage["prompt_tokens"] = usage["input_tokens"]
                if "output_tokens" in usage and "completion_tokens" not in usage:
                    usage["completion_tokens"] = usage["output_tokens"]
                self.update_token_usage(usage, model_name="Ling-1T")

            self.increment_api_calls()
            return content
