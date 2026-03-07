#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Grading response parser and score converter."""

import json
import re
from typing import Any, Dict, List


def clean_and_parse_json(json_str: str) -> Any:
    """Attempt to clean and parse a JSON string.

    Handles:
    - Smart quotes
    - Trailing commas
    - Control characters
    """
    if not json_str:
        raise ValueError("Empty JSON string")

    # Basic cleanup
    json_str = json_str.strip()

    # 1. Try parsing original first
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 2. Try fixing trailing commas on original
    # Pattern: , \s* ]  -> ]
    json_str_fixed = re.sub(r",\s*\]", "]", json_str)
    json_str_fixed = re.sub(r",\s*\}", "}", json_str_fixed)

    try:
        return json.loads(json_str_fixed)
    except json.JSONDecodeError:
        pass

    # 3. Try replacing smart quotes
    # Only do this if previous attempts failed, as it might break valid strings containing smart quotes
    json_str_quotes = json_str.replace("“", '"').replace("”", '"')

    try:
        return json.loads(json_str_quotes)
    except json.JSONDecodeError:
        pass

    # 4. Try fixing trailing commas on quote-replaced version
    json_str_quotes_fixed = re.sub(r",\s*\]", "]", json_str_quotes)
    json_str_quotes_fixed = re.sub(r",\s*\}", "}", json_str_quotes_fixed)

    try:
        return json.loads(json_str_quotes_fixed)
    except json.JSONDecodeError:
        pass

    # 5. If it's a list that got truncated, try to append ']'
    if json_str.startswith("[") and not json_str.endswith("]"):
        try:
            return json.loads(json_str + "]")
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not parse JSON")


def parse_grading_response(
    response_text: str, rubrics: List[Dict[str, Any]]
) -> Dict[int, Dict[str, Any]]:
    """Parse grading response from judge model.

    Args:
        response_text: Raw response text from judge model
        rubrics: List of rubric dictionaries

    Returns:
        Dictionary mapping rubric_id to parsed results
    """
    results = {}

    # Try multiple patterns to match JSON array
    patterns = [
        r"```json\s*(\[[\s\S]*\])\s*```",  # JSON in code block (greedy to last ])
        r"```\s*(\[[\s\S]*\])\s*```",  # JSON in code block without json tag
    ]

    json_str = None
    matched_pattern = None

    # 1. First try code block patterns
    for i, pattern in enumerate(patterns):
        match = re.search(pattern, response_text, re.DOTALL)
        if match:
            try:
                data_list = clean_and_parse_json(match.group(1))
                json_str = match.group(1)  # Keep raw str for logging if needed
                matched_pattern = i + 1
                break
            except (ValueError, json.JSONDecodeError):
                continue

    # 2. If code block fails, try to find all [ ... ] and select longest parseable JSON
    if not json_str:
        start_positions = [m.start() for m in re.finditer(r"\[", response_text)]

        for start in start_positions:
            bracket_count = 0
            in_string = False
            escape_next = False

            for i in range(start, len(response_text)):
                char = response_text[i]

                if escape_next:
                    escape_next = False
                    continue

                if char == "\\":
                    escape_next = True
                    continue

                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue

                if not in_string:
                    if char == "[":
                        bracket_count += 1
                    elif char == "]":
                        bracket_count -= 1
                        if bracket_count == 0:
                            candidate = response_text[start : i + 1]
                            try:
                                data_list = clean_and_parse_json(candidate)
                                json_str = candidate
                                matched_pattern = 3
                                break
                            except (ValueError, json.JSONDecodeError):
                                continue
            if json_str:
                break

    # 3. Last resort: Try to find content between first [ and last ]
    if not json_str:
        first_bracket = response_text.find("[")
        last_bracket = response_text.rfind("]")

        if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
            candidate = response_text[first_bracket : last_bracket + 1]
            try:
                data_list = clean_and_parse_json(candidate)
                json_str = candidate
                matched_pattern = 4
            except (ValueError, json.JSONDecodeError):
                pass

    if json_str:
        try:
            # data_list should be already set by one of the methods above
            # But let's double check if we just set json_str and not data_list in some path (unlikely with current logic)
            if "data_list" not in locals():
                data_list = clean_and_parse_json(json_str)

            for item in data_list:
                rubric_id = item.get("rubric_id")
                status = item.get("status", "").strip()
                justification = item.get("justification", "").strip()
                consistency = item.get("consistency", "").strip()

                # More robust yes/no detection
                yes_values = ["是", "Yes", "yes", "Y", "YES", "true", "True", "命中"]
                binary_score = 1 if status in yes_values else 0

                if rubric_id:
                    # Normalize rubric_id to int if possible
                    try:
                        rubric_id = int(rubric_id)
                    except (ValueError, TypeError):
                        pass

                    results[rubric_id] = {
                        "status": status,
                        "binary_score": binary_score,
                        "justification": justification,
                        "consistency": consistency,
                    }
        except Exception as e:
            from ..utils import print_warning

            print_warning(f"JSON解析错误: {str(e)[:100]}")
            print_warning(
                f"匹配的pattern: {matched_pattern}, JSON长度: {len(json_str) if json_str else 0}"
            )
    else:
        from ..utils import print_warning

        print_warning(f"未找到JSON数组，response前500字符: {response_text[:500]}")

    # Fill missing rubrics
    for rubric in rubrics:
        rubric_num = rubric["rubric_number"]

        # Normalize lookup key
        lookup_key = rubric_num
        try:
            lookup_key = int(rubric_num)
        except (ValueError, TypeError):
            pass

        if lookup_key not in results:
            results[lookup_key] = {
                "status": "否",
                "binary_score": "NA",
                "justification": "解析失败",
                "consistency": "",
            }

    return results


def convert_scores(
    raw_results: Dict[int, Dict[str, Any]], rubrics: List[Dict[str, Any]]
) -> Dict[int, Any]:
    """Convert binary scores to final scores based on rubric weights.

    Args:
        raw_results: Raw parsing results from parse_grading_response
        rubrics: List of rubric dictionaries

    Returns:
        Dictionary mapping rubric_id to final score
    """
    final_scores = {}

    for rubric in rubrics:
        rubric_num = rubric["rubric_number"]
        weight = rubric["rubric_weight"]

        # Normalize lookup key
        lookup_key = rubric_num
        try:
            lookup_key = int(rubric_num)
        except (ValueError, TypeError):
            pass

        raw_result = raw_results.get(lookup_key, {"binary_score": 0})
        binary_score = raw_result["binary_score"]

        # Check if parsing failed
        if binary_score == "NA":
            final_scores[rubric_num] = "NA"
            continue

        # Positive scoring (weight > 0): hit(yes)=score, miss(no)=0
        # Negative scoring (weight < 0): hit(yes)=deduct, miss(no)=0
        if weight > 0:
            final_score = weight if binary_score == 1 else 0
        elif weight < 0:
            final_score = weight if binary_score == 1 else 0
        else:
            final_score = 0

        final_scores[rubric_num] = final_score

    return final_scores
