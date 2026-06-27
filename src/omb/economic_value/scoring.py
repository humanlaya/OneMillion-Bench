#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Per-question scoring helpers: ExpertScore and pass mask.

These mirror the formulas in README §"Evaluation metrics":

    ExpertScore(q) = clip(  Σ_{r∈R_q} s_r / Σ_{r∈R_q⁺} w_r , 0, 1 )
    PassRate(Q)    = (1/|Q|) Σ_q 𝟙[ExpertScore(q) ≥ 0.7]

``s_r`` is the rubric-level score already written by ``omb eval`` into
``rubric_auto_score[<judge>][rubric_<n>_response_<i>_auto_score]`` — the
``convert_scores`` step assigns ``+w`` (or ``-w``) on hit and ``0`` on miss
or NA.
"""

from __future__ import annotations

from typing import Iterable, List, Mapping, Optional

DEFAULT_PASS_THRESHOLD = 0.7


def total_positive_weight(rubrics: Iterable[Mapping[str, object]]) -> float:
    """Σ over R_q^+ — denominator of ExpertScore."""
    total = 0.0
    for rubric in rubrics:
        weight = float(rubric.get("rubric_weight", 0) or 0)
        if weight > 0:
            total += weight
    return total


def total_score(
    rubrics: Iterable[Mapping[str, object]],
    rubric_auto_score: Mapping[str, object],
    response_idx: int,
) -> float:
    """Σ_{r∈R_q} s_r — numerator of ExpertScore.

    ``rubric_auto_score`` is the per-judge dict already nested under a single
    judge model (i.e. caller has dereferenced ``data["rubric_auto_score"][judge]``).
    NA entries are treated as 0, matching ``_add_macro_average_row``.
    """
    rubric_list: List[Mapping[str, object]] = list(rubrics)
    total = 0.0
    for rubric in rubric_list:
        rubric_num = rubric.get("rubric_number")
        key = f"rubric_{rubric_num}_response_{response_idx}_auto_score"
        score = rubric_auto_score.get(key, 0)
        if score == "NA" or score is None:
            continue
        try:
            total += float(score)
        except (TypeError, ValueError):
            continue
    return total


def expert_score(
    rubrics: Iterable[Mapping[str, object]],
    rubric_auto_score: Mapping[str, object],
    response_idx: int,
) -> Optional[float]:
    """Compute ExpertScore for one (question, response) pair.

    Returns ``None`` when the question has no positive-weight rubrics
    (denominator would be zero); such questions cannot meaningfully pass
    or fail and should be excluded from Economic Value aggregation.
    """
    rubric_list = list(rubrics)
    denom = total_positive_weight(rubric_list)
    if denom <= 0:
        return None
    numer = total_score(rubric_list, rubric_auto_score, response_idx)
    raw = numer / denom
    if raw < 0:
        return 0.0
    if raw > 1:
        return 1.0
    return raw


def passes_threshold(score: Optional[float], threshold: float = DEFAULT_PASS_THRESHOLD) -> bool:
    return score is not None and score >= threshold
