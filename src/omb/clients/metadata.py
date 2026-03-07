#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenRouter model metadata detection.

Fetches context_length and top_provider.max_completion_tokens
from the OpenRouter /api/v1/models endpoint for runtime parameter setup.
"""

from typing import Any, Dict, List, Optional

import requests


def fetch_openrouter_models(api_key: str) -> List[Dict[str, Any]]:
    """Fetch all model metadata from OpenRouter.

    Args:
        api_key: OpenRouter API key

    Returns:
        List of model data dictionaries
    """
    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data.get("data", [])


def detect_model_metadata(
    api_key: str, model_ids: List[str]
) -> Dict[str, Dict[str, Optional[int]]]:
    """Detect context_length and max_completion_tokens for given models.

    Args:
        api_key: OpenRouter API key
        model_ids: List of model IDs to look up

    Returns:
        Dict mapping model_id to {context_length, max_completion_tokens}
    """
    all_models = fetch_openrouter_models(api_key)

    # Build lookup by model id
    model_lookup: Dict[str, Dict[str, Any]] = {}
    for m in all_models:
        mid = m.get("id", "")
        if mid:
            model_lookup[mid] = m

    result: Dict[str, Dict[str, Optional[int]]] = {}
    for model_id in model_ids:
        info = model_lookup.get(model_id)
        if info:
            context_length = info.get("context_length")
            top_provider = info.get("top_provider", {}) or {}
            max_completion_tokens = top_provider.get("max_completion_tokens")
            result[model_id] = {
                "context_length": context_length,
                "max_completion_tokens": max_completion_tokens,
            }
    return result
