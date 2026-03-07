# -*- coding: utf-8 -*-
"""VolcEngine API client."""

import asyncio
from typing import Any, Dict, List, Optional

import aiohttp

from .base import BaseLLMClient


class VolcEngineClient(BaseLLMClient):
    """Client for VolcEngine API."""

    async def call(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        retry_count: int = 0,
        response_format: Optional[Dict[str, str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> str:
        """Call VolcEngine API.

        Args:
            messages: List of message dictionaries
            model: Model name
            reasoning_effort: Reasoning effort level
            retry_count: Current retry attempt
            response_format: Optional response format
            tools: Optional list of tools
            **kwargs: Additional parameters

        Returns:
            Response text from the model
        """
        if model is None:
            # Default to a generic model or raise error if required,
            # but usually model is passed from processing.py
            model = "doubao-seed-1-8-251228"

        headers = {
            "Authorization": f"Bearer {self.config.volc_api_key}",
            "Content-Type": "application/json",
        }

        # Construct payload
        payload = {
            "model": model,
            "messages": messages,
            # VolcEngine/Doubao models might use specific parameters
            "max_tokens": self.config.get_max_tokens_for_model(model),
            # "stream": False, # Default is False usually
        }

        # Add temperature only if explicitly set or if model supports it (some reasoning models might not)
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature

        # Add sampling parameters if configured
        if self.config.top_p is not None:
            payload["top_p"] = self.config.top_p
        if self.config.top_k is not None:
            payload["top_k"] = self.config.top_k
        if self.config.frequency_penalty is not None:
            payload["frequency_penalty"] = self.config.frequency_penalty
        if self.config.presence_penalty is not None:
            payload["presence_penalty"] = self.config.presence_penalty

        if reasoning_effort:
            # Check if we should put it in top level or extra_body based on SDK usage
            # The snippet showed it as a top level param in the method call,
            # which usually maps to top level in JSON for some providers or extra_body for others.
            # But the snippet also had extra_body={"thinking": ...}
            # We'll add it to payload if it's a standard param, or handle it via extra_body if needed.
            # For now, let's assume standard OpenAI-like behavior where it might be in the body.
            # However, looking at the snippet: reasoning={"effort": "high"} passed to client.create
            # This suggests it maps to "reasoning_effort" in the payload (like O1).
            pass  # We will handle it below

        # Handle specific VolcEngine/Doubao params from snippet
        # Snippet: extra_body={"thinking": {"type": "enabled"}}
        # Snippet: reasoning={"effort": "high"}

        # We will allow passing these via kwargs or defaults
        extra_body = kwargs.get("extra_body", {})
        if "thinking" not in extra_body:
            extra_body["thinking"] = {"type": "enabled"}

        payload["extra_body"] = extra_body

        # Handle reasoning parameter if provided in snippet style
        if reasoning_effort:
            # The snippet passed reasoning={"effort": "high"}
            payload["extra_body"]["thinking"] = {"type": "enabled"}

        # If response format is provided
        if response_format:
            payload["response_format"] = response_format

        if tools:
            # Check if there are non-function tools (like web_search)
            # VolcEngine's OpenAI-compatible endpoint expects web_search in extra_body
            has_web_search = any(t.get("type") == "web_search" for t in tools)
            if has_web_search:
                extra_body["tools"] = tools
            else:
                payload["tools"] = tools

        session = kwargs.get("session")
        if not session:
            # If no session provided, create one (though usually passed from orchestrator)
            # Ideally we should use the session passed in.
            # If not, we might need to create a temporary one, but async context managers are tricky here.
            # We will raise error as in OpenRouterClient
            raise ValueError("Session is required for VolcEngine client")

        # Endpoint construction
        base_url = self.config.volc_api_base
        if not base_url.endswith("/"):
            base_url += "/"
        # Standard OpenAI compatible endpoint
        api_url = f"{base_url}chat/completions"

        try:
            proxy = self.config.proxy
            async with session.post(
                api_url,
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
                            f"VolcEngine API error {response.status}: {error_text[:300]}"
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

                # Normalize content
                if content is None:
                    content = ""
                content = str(content).strip()

                # Check for reasoning content if main content is empty (DeepSeek/R1 style)
                if not content:
                    reasoning_content = message.get("reasoning_content", "")
                    if reasoning_content:
                        content = str(reasoning_content).strip()

                if not content:
                    # Some models might return empty content if only tool calls, but we expect text here
                    # Unless it's a thinking model that returns reasoning in a different field?
                    # The snippet has 'thinking': {'type': 'enabled'}, so maybe reasoning is returned?
                    pass

                if not content:
                    raise ValueError("API returned empty content")

                # Update statistics
                if "usage" in result:
                    self.update_token_usage(result["usage"], model_name=model)

                self.increment_api_calls()
                return content

        except aiohttp.ClientResponseError as e:
            if retry_count >= self.config.retry_times:
                from ..utils import print_warning

                print_warning(
                    f"VolcEngine API error details: status={e.status}, message={e.message}"
                )
                raise
            await asyncio.sleep(self.config.retry_delay)
            return await self.call(
                messages,
                model,
                reasoning_effort,
                retry_count + 1,
                response_format=response_format,
                tools=tools,
                **kwargs,
            )
        except Exception as e:
            if retry_count < self.config.retry_times:
                await asyncio.sleep(self.config.retry_delay)
                return await self.call(
                    messages,
                    model,
                    reasoning_effort,
                    retry_count + 1,
                    response_format=response_format,
                    tools=tools,
                    **kwargs,
                )
            else:
                raise
