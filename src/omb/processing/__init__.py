#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Async processing for model response generation and grading."""

import asyncio
from typing import Any, Dict, List, Optional

import aiohttp
from rich.progress import Progress, TaskID

from ..clients import (
    HunyuanClient,
    Ling1TClient,
    OpenRouterClient,
    QwenClient,
    QwenDeepResearchClient,
    VolcEngineClient,
)
from ..grading import build_grading_prompt, convert_scores, parse_grading_response
from ..utils import RichColors, err_console, print_debug_question, print_debug_response


async def generate_model_response(
    session: Any,
    prompt: str,
    model_name: str,
    file_name: str,
    config: Any,
    semaphore: asyncio.Semaphore,
    progress: Progress,
    task_id: TaskID,
    token_tracker: Any = None,
) -> Optional[Dict[str, Any]]:
    """Generate a single model response.

    Args:
        session: aiohttp ClientSession
        prompt: User prompt
        model_name: Name of the model
        file_name: Name of the file being processed
        config: Configuration object
        semaphore: Semaphore for concurrency control
        progress: Rich Progress instance
        task_id: Rich Progress task ID
        token_tracker: Optional TokenTracker for usage tracking

    Returns:
        Dictionary with model_name and response_text, or None if failed
    """
    async with semaphore:
        attempts = 0
        max_retries = config.retry_times

        while attempts <= max_retries:
            try:
                # Calculate timeout with 600s stepup
                current_timeout = (attempts + 1) * 600

                # Debug logging: Print question
                if config.debug and attempts == 0:
                    print_debug_question(file_name, prompt, model_name)

                # Handle different model types
                token_usage = None
                response = None

                if model_name == "qwen-deep-research":
                    client = QwenDeepResearchClient(config, token_tracker)
                    messages = [{"role": "user", "content": prompt}]
                    response = await asyncio.wait_for(
                        client.call(messages), timeout=current_timeout
                    )
                    token_usage = client.last_usage

                elif "hunyuan" in model_name:
                    real_model_name = model_name
                    enable_search = False

                    if model_name.endswith("-with-search"):
                        real_model_name = model_name.replace("-with-search", "")
                        enable_search = True

                    client = HunyuanClient(config, token_tracker)
                    messages = [{"role": "user", "content": prompt}]
                    response = await asyncio.wait_for(
                        client.call(
                            messages,
                            real_model_name,
                            session=session,
                            enable_search=enable_search,
                        ),
                        timeout=current_timeout,
                    )
                    token_usage = client.last_usage

                elif "qwen3-max" in model_name and not model_name.startswith("qwen/"):
                    real_model_name = model_name
                    enable_search = False

                    if model_name.endswith("-with-search"):
                        real_model_name = model_name.replace("-with-search", "")
                        enable_search = True

                    client = QwenClient(config, token_tracker)
                    messages = [{"role": "user", "content": prompt}]
                    response = await asyncio.wait_for(
                        client.call(
                            messages,
                            real_model_name,
                            session=session,
                            enable_search=enable_search,
                        ),
                        timeout=current_timeout,
                    )
                    token_usage = client.last_usage

                elif model_name == "Ling-1T":
                    client = Ling1TClient(config, token_tracker)
                    messages = [{"role": "user", "content": prompt}]
                    response = await asyncio.wait_for(
                        client.call(messages, session=session), timeout=current_timeout
                    )
                    token_usage = client.last_usage

                elif (
                    "doubao" in model_name or model_name.startswith("ep-")
                ) and "deep-research" not in model_name:
                    real_model_name = model_name
                    tools = None

                    # Check for search enabled
                    if model_name.endswith("-with-search"):
                        real_model_name = model_name.replace("-with-search", "")
                        # Configuration for Doubao web search
                        tools = [{"type": "web_search", "max_keyword": 2}]

                    client = VolcEngineClient(config, token_tracker)
                    messages = [{"role": "user", "content": prompt}]
                    # You might want to pass specific params for doubao if needed
                    response = await asyncio.wait_for(
                        client.call(
                            messages,
                            model=real_model_name,
                            session=session,
                            reasoning_effort=(
                                "high"
                                if "thinking" in real_model_name
                                or "reasoning" in real_model_name
                                or "seed" in real_model_name
                                else None
                            ),
                            tools=tools,
                        ),
                        timeout=current_timeout,
                    )
                    token_usage = client.last_usage

                elif model_name.endswith("-with-search"):
                    base_model = model_name.replace("-with-search", "")

                    # Unified handling for all models with search using OpenRouter web plugin
                    # According to docs/web_search.md, we use plugins=[{"id": "web"}]
                    client = OpenRouterClient(config, token_tracker)
                    messages = [{"role": "user", "content": prompt}]

                    response = await asyncio.wait_for(
                        client.call(
                            messages,
                            base_model,
                            reasoning_effort=config.reasoning_effort,
                            session=session,
                            plugins=[{"id": "web"}],
                        ),
                        timeout=current_timeout,
                    )
                    token_usage = client.last_usage

                else:
                    # Use OpenRouter for other models
                    client = OpenRouterClient(config, token_tracker)

                    enhanced_prompt = f"""请直接回答以下问题，不要向我提问，不要要求我提供更多信息。请基于问题中已有的信息直接给出完整、详细的答案。

{prompt}"""
                    messages = [
                        {
                            "role": "system",
                            "content": "你是一个专业的问题解答助手。你必须直接回答问题，禁止向用户提问或要求更多信息。",
                        },
                        {"role": "user", "content": enhanced_prompt},
                    ]

                    # Single round generation is sufficient with the enhanced prompt
                    response = await asyncio.wait_for(
                        client.call(
                            messages,
                            model_name,
                            reasoning_effort=config.reasoning_effort,
                            session=session,
                        ),
                        timeout=current_timeout,
                    )
                    token_usage = client.last_usage

                if not response or len(response.strip()) < 10:
                    raise ValueError("Response too short")

                # Debug logging: Print response with token usage
                if config.debug:
                    print_debug_response(
                        file_name, response, model_name, "Generation", token_usage
                    )

                # Update progress
                if token_usage:
                    output_tokens = token_usage.get("completion_tokens", 0)
                    desc = f"[{RichColors.GREEN}]✓[/{RichColors.GREEN}] [{RichColors.DIM}]{file_name}[/{RichColors.DIM}] [{RichColors.YELLOW}]{model_name}[/{RichColors.YELLOW}]: [{RichColors.SUCCESS}]{output_tokens:,} tokens[/{RichColors.SUCCESS}]"
                else:
                    desc = f"[{RichColors.GREEN}]✓[/{RichColors.GREEN}] [{RichColors.DIM}]{file_name}[/{RichColors.DIM}] [{RichColors.YELLOW}]{model_name}[/{RichColors.YELLOW}]: [{RichColors.SUCCESS}]{len(response.split())} words[/{RichColors.SUCCESS}]"
                progress.advance(task_id)
                progress.console.print(f"  {desc}")

                # Include reasoning_tokens in response if available
                reasoning_tokens = (
                    token_usage.get("reasoning_tokens", 0) if token_usage else 0
                )
                result_dict = {
                    "model_name": model_name,
                    "response_text": response,
                }
                if reasoning_tokens:
                    result_dict["reasoning_tokens"] = reasoning_tokens
                return result_dict

            except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
                attempts += 1
                if attempts <= max_retries:
                    err_console.print(
                        f"  ⚠️  Generation timed out for {model_name} (attempt {attempts}/{max_retries}), retrying with {(attempts + 1) * config.retry_delay}s timeout...",
                        style=RichColors.WARNING,
                    )
                    await asyncio.sleep(config.retry_delay)
                    continue
                else:
                    progress.advance(task_id)
                    progress.console.print(
                        f"  [{RichColors.RED}]✗[/{RichColors.RED}] Generation failed (timeout) [{RichColors.DIM}]{file_name}[/{RichColors.DIM}] [{RichColors.YELLOW}]{model_name}[/{RichColors.YELLOW}]"
                    )
                    return None
            except Exception as e:
                attempts += 1
                if attempts <= max_retries:
                    err_console.print(
                        f"  ⚠️  Generation failed for {model_name} (attempt {attempts}/{max_retries}): {str(e)}, retrying...",
                        style=RichColors.WARNING,
                    )
                    await asyncio.sleep(config.retry_delay)
                    continue
                else:
                    progress.advance(task_id)
                    progress.console.print(
                        f"  [{RichColors.RED}]✗[/{RichColors.RED}] Generation failed [{RichColors.DIM}]{file_name}[/{RichColors.DIM}] [{RichColors.YELLOW}]{model_name}[/{RichColors.YELLOW}]: [{RichColors.RED}]{str(e)[:200]}[/{RichColors.RED}]"
                    )
                    return None


async def grade_single_model(
    session: Any,
    prompt: str,
    model_name: str,
    model_response: str,
    rubrics: List[Dict[str, Any]],
    human_scores_dict: Dict[str, int],
    model_idx: int,
    file_name: str,
    config: Any,
    semaphore: asyncio.Semaphore,
    progress: Progress,
    task_id: TaskID,
    token_tracker: Any = None,
    judge_model: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Grade a single model response.

    Args:
        session: aiohttp ClientSession
        prompt: Original user prompt
        model_name: Name of the model being graded
        model_response: Model's response to grade
        rubrics: List of rubric dictionaries
        human_scores_dict: Dictionary of human scores
        model_idx: Model index
        file_name: Name of the file being processed
        config: Configuration object
        semaphore: Semaphore for concurrency control
        progress: Rich Progress instance
        task_id: Rich Progress task ID
        token_tracker: Optional TokenTracker for usage tracking
        judge_model: Judge model to use (defaults to config.judge_model)

    Returns:
        Dictionary with grading results, or None if failed
    """
    effective_judge_model = judge_model or config.judge_model
    # Strip ::run_N suffix for API calls (used by repeated-judge feature)
    api_judge_model = effective_judge_model.split("::run_")[0] if "::run_" in effective_judge_model else effective_judge_model
    async with semaphore:
        attempts = 0
        max_retries = config.retry_times

        while attempts <= max_retries:
            try:
                # Calculate timeout with 60s stepup
                current_timeout = (attempts + 1) * 6000

                # Debug logging: Print question and response being graded
                if config.debug and attempts == 0:
                    print_debug_question(file_name, prompt, model_name)
                    print_debug_response(
                        file_name, model_response, model_name, "Reference"
                    )

                grading_prompt = build_grading_prompt(
                    prompt, model_response, rubrics, human_scores_dict
                )
                messages = [{"role": "user", "content": grading_prompt}]

                client = OpenRouterClient(config, token_tracker)

                response_text = await asyncio.wait_for(
                    client.call(
                        messages,
                        api_judge_model,
                        config.reasoning_effort,
                        session=session,
                        response_format={"type": "json_object"},
                    ),
                    timeout=current_timeout,
                )

                # Debug logging: Print grading result with token usage
                if config.debug:
                    print_debug_response(
                        file_name,
                        response_text,
                        api_judge_model,
                        "Grading",
                        client.last_usage,
                    )

                raw_results = parse_grading_response(response_text, rubrics)

                # Check for parsing failure (all rubrics marked as NA)
                is_parsing_failed = all(
                    r.get("binary_score") == "NA" for r in raw_results.values()
                )

                if is_parsing_failed:
                    attempts += 1
                    if attempts <= max_retries:
                        err_console.print(
                            f"  ⚠️  JSON parsing failed (attempt {attempts}/{max_retries}), retrying...",
                            style=RichColors.WARNING,
                        )
                        await asyncio.sleep(config.retry_delay)
                        continue
                    else:
                        err_console.print(
                            f"  ⚠️  JSON parsing failed after {attempts} attempts. Using last result.",
                            style=RichColors.WARNING,
                        )

                final_scores = convert_scores(raw_results, rubrics)

                # Calculate total score, skip NA values
                total_score = sum(
                    score for score in final_scores.values() if score != "NA"
                )

                progress.advance(task_id)
                progress.console.print(
                    f"  [{RichColors.GREEN}]✓[/{RichColors.GREEN}] [{RichColors.DIM}]{file_name}[/{RichColors.DIM}] [{RichColors.YELLOW}]{model_name}[/{RichColors.YELLOW}]: [{RichColors.SUCCESS}]{total_score} points[/{RichColors.SUCCESS}]"
                )

                return {
                    "model_idx": model_idx,
                    "model_name": model_name,
                    "judge_model": effective_judge_model,
                    "raw_results": raw_results,
                    "final_scores": final_scores,
                    "total_score": total_score,
                }

            except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
                attempts += 1
                if attempts <= max_retries:
                    err_console.print(
                        f"  ⚠️  Grading timed out for {model_name} (attempt {attempts}/{max_retries}), retrying with {(attempts + 1) * config.retry_delay}s timeout...",
                        style=RichColors.WARNING,
                    )
                    await asyncio.sleep(config.retry_delay)
                    continue
                else:
                    progress.advance(task_id)
                    progress.console.print(
                        f"  [{RichColors.RED}]✗[/{RichColors.RED}] Grading failed (timeout) [{RichColors.DIM}]{file_name}[/{RichColors.DIM}] [{RichColors.YELLOW}]{model_name}[/{RichColors.YELLOW}]"
                    )
                    return None
            except Exception as e:
                attempts += 1
                if attempts <= max_retries:
                    err_console.print(
                        f"  ⚠️  Grading failed for {model_name} (attempt {attempts}/{max_retries}): {str(e)[:100]}, retrying...",
                        style=RichColors.WARNING,
                    )
                    await asyncio.sleep(config.retry_delay)
                    continue
                else:
                    progress.advance(task_id)
                    progress.console.print(
                        f"  [{RichColors.RED}]✗[/{RichColors.RED}] Grading failed [{RichColors.DIM}]{file_name}[/{RichColors.DIM}] [{RichColors.YELLOW}]{model_name}[/{RichColors.YELLOW}]: [{RichColors.RED}]{str(e)[:50]}[/{RichColors.RED}]"
                    )
                    return None
