#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Economic Value aggregation for in-memory OMB evaluation results."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .loader import EconomicValueEntry, EconomicValueTable, load_economic_value_table
from .scoring import DEFAULT_PASS_THRESHOLD, expert_score, passes_threshold

ID_KEY_CANDIDATES: Tuple[str, ...] = ("uuid", "UUID", "case_id", "caseId", "id")


@dataclass
class ModelEconomicValue:
    """Economic Value totals for one model under one judge."""

    model: str
    judge: str
    threshold: float
    cn: Dict[str, Any] = field(
        default_factory=lambda: {"total": 0.0, "passed": 0, "questions": 0, "currency": "CNY"}
    )
    global_: Dict[str, Any] = field(
        default_factory=lambda: {"total": 0.0, "passed": 0, "questions": 0, "currency": "USD"}
    )

    @property
    def questions_total(self) -> int:
        return int(self.cn["questions"]) + int(self.global_["questions"])

    @property
    def questions_passed(self) -> int:
        return int(self.cn["passed"]) + int(self.global_["passed"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "judge": self.judge,
            "threshold": self.threshold,
            "questions_total": self.questions_total,
            "questions_passed": self.questions_passed,
            "cn": dict(self.cn),
            "global": dict(self.global_),
            "display": format_model_economic_value(self),
        }


@dataclass
class EconomicValueReport:
    """Economic Value result for a judge sheet/report section."""

    judge: str
    threshold: float
    table_size: int
    files_scanned: int
    files_matched: int
    models: Dict[str, ModelEconomicValue]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "judge": self.judge,
            "threshold": self.threshold,
            "table_size": self.table_size,
            "files_scanned": self.files_scanned,
            "files_matched": self.files_matched,
            "models": {model: stats.to_dict() for model, stats in self.models.items()},
        }


def default_economic_value_path() -> Path:
    """Return the repo-level economic value table path."""
    return Path(__file__).resolve().parents[3] / "economic_value.md"


def format_model_economic_value(value: Optional[ModelEconomicValue]) -> str:
    """Format one model's CN/USD totals for report cells."""
    if value is None:
        return "N/A"
    parts: List[str] = []
    if value.cn["questions"]:
        parts.append(f"¥{value.cn['total']:,.0f}")
    if value.global_["questions"]:
        parts.append(f"${value.global_['total']:,.0f}")
    return " / ".join(parts) if parts else "N/A"


def _candidate_ids(data: Mapping[str, Any], path: Path) -> List[str]:
    keys: List[str] = []
    for key in ID_KEY_CANDIDATES:
        if key in data and data[key] not in (None, ""):
            keys.append(str(data[key]))
    stem = path.stem
    if stem and stem not in keys:
        keys.append(stem)
    prefix = re.split(r"[\W_]+", stem, maxsplit=1)[0] if stem else ""
    if prefix and prefix not in keys:
        keys.append(prefix)
    return keys


def _update_model_value(
    model_value: ModelEconomicValue,
    entry: EconomicValueEntry,
    score: Optional[float],
) -> None:
    bucket = model_value.cn if entry.subset == "cn" else model_value.global_
    bucket["questions"] += 1
    if passes_threshold(score, model_value.threshold):
        bucket["passed"] += 1
        bucket["total"] += entry.value


def compute_economic_value_from_data(
    file_data_map: Dict[Path, Dict[str, Any]],
    json_files: Sequence[Path],
    judge_model_name: str,
    models_list: Sequence[str],
    economic_value_md: Optional[Path] = None,
    threshold: float = DEFAULT_PASS_THRESHOLD,
    table: Optional[EconomicValueTable] = None,
) -> EconomicValueReport:
    """Compute Economic Value for one judge from loaded evaluation data."""
    table_path = Path(economic_value_md) if economic_value_md else default_economic_value_path()
    value_table = table if table is not None else load_economic_value_table(table_path)
    models = {
        model: ModelEconomicValue(model=model, judge=judge_model_name, threshold=threshold)
        for model in models_list
    }
    files_scanned = 0
    files_matched = 0

    for json_path in sorted(json_files):
        data = file_data_map.get(json_path, {})
        rubrics = data.get("rubrics", [])
        rubric_auto_score = data.get("rubric_auto_score", {})
        judge_scores = rubric_auto_score.get(judge_model_name, {})
        if not isinstance(rubrics, list) or not isinstance(judge_scores, Mapping):
            continue

        files_scanned += 1
        entry = value_table.lookup_any(_candidate_ids(data, json_path))
        if entry is None:
            continue
        files_matched += 1

        for response_key, response_data in data.get("model_response", {}).items():
            if not isinstance(response_data, Mapping):
                continue
            match = re.match(r"model_response_(\d+)$", str(response_key))
            if not match:
                continue
            model_name = str(response_data.get("model_name") or "").strip()
            if model_name not in models:
                continue
            score = expert_score(rubrics, judge_scores, int(match.group(1)))
            _update_model_value(models[model_name], entry, score)

    return EconomicValueReport(
        judge=judge_model_name,
        threshold=threshold,
        table_size=len(value_table),
        files_scanned=files_scanned,
        files_matched=files_matched,
        models=models,
    )
