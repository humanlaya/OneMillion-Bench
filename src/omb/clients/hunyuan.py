#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hunyuan API client."""

import asyncio
from typing import Any, Dict, List, Optional

import aiohttp

from .base import BaseLLMClient


class HunyuanClient(BaseLLMClient):
    """Client for Hunyuan API."""

    async def call(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        retry_count: int = 0,
        enable_enhancement: bool = True,
        enable_search: bool = False,
        **kwargs,
    ) -> str:
        """Call Hunyuan API.

        Args:
            messages: List of message dictionaries
            model: Model name (uses config default if None)
            retry_count: Current retry attempt
            enable_enhancement: Whether to enable enhancement (default: True)
            enable_search: Whether to force search enhancement
            **kwargs: Additional parameters

        Returns:
            Response text from the model

        Raises:
            aiohttp.ClientResponseError: If API returns error after retries
            ValueError: If response format is invalid
        """
        # Set default model if not provided
        if model is None:
            model = "hunyuan-2.0-thinking-20251109"  # Default fallback if needed

        headers = {
            "Authorization": f"Bearer {self.config.hunyuan_api_key}",
            "Content-Type": "application/json",
        }

        payload = {"model": model, "messages": messages, "extra_body": {}}

        if enable_search:
            payload["extra_body"]["enable_enhancement"] = True
            payload["extra_body"]["force_search_enhancement"] = True
            # payload["extra_body"]["citation"] = True
            # payload["extra_body"]["search_info"] = True

        # Add optional parameters if they exist in config
        if self.config.temperature:
            payload["temperature"] = self.config.temperature

        # Only add max_tokens if explicitly set, some models might have different defaults
        if self.config.max_tokens:
            payload["max_tokens"] = self.config.get_max_tokens_for_model(model)

        # Add sampling parameters if configured
        if self.config.top_p is not None:
            payload["top_p"] = self.config.top_p
        if self.config.top_k is not None:
            payload["top_k"] = self.config.top_k
        if self.config.frequency_penalty is not None:
            payload["frequency_penalty"] = self.config.frequency_penalty
        if self.config.presence_penalty is not None:
            payload["presence_penalty"] = self.config.presence_penalty

        session = kwargs.get("session")
        if not session:
            raise ValueError("Session is required for Hunyuan client")

        try:
            proxy = self.config.proxy
            # Use specific API base if configured, otherwise default to the one in the curl
            api_base = getattr(
                self.config,
                "hunyuan_api_base",
                "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
            )

            async with session.post(
                api_base,
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
                            f"Hunyuan API error {response.status}: {error_text[:300]}"
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

                content = result["choices"][0]["message"]["content"]
                if not content:
                    raise ValueError("API returned empty content")

                # Update statistics
                if "usage" in result:
                    usage = result["usage"]
                    self.update_token_usage(usage, model_name=model)

                self.increment_api_calls()
                return content.strip()

        except aiohttp.ClientResponseError as e:
            if retry_count >= self.config.retry_times:
                from ..utils import print_warning

                print_warning(
                    f"Hunyuan API error details: status={e.status}, message={e.message}"
                )
                raise
            await asyncio.sleep(self.config.retry_delay)
            return await self.call(
                messages,
                model,
                retry_count + 1,
                enable_enhancement,
                enable_search=enable_search,
                **kwargs,
            )
        except Exception as e:
            if retry_count < self.config.retry_times:
                await asyncio.sleep(self.config.retry_delay)
                return await self.call(
                    messages,
                    model,
                    retry_count + 1,
                    enable_enhancement,
                    enable_search=enable_search,
                    **kwargs,
                )
            else:
                raise
