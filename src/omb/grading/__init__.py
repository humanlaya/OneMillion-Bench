#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Grading logic for omb."""

from .parser import convert_scores, parse_grading_response
from .prompts import build_grading_prompt

__all__ = [
    "build_grading_prompt",
    "convert_scores",
    "parse_grading_response",
]
