#!/usr/bin/env python3
"""
Categorize JSON files in subdirectories by their time_sensitivity
recorded in diachronical_stats.json.

Creates three target directories:
  - agnostic          (time-agnostic + uncategorized fallback)
  - weak_sensitive    (weakly time-sensitive)
  - sensitive         (strongly time-sensitive, mapped from '强时效性')

Files are COPIED (not moved) to preserve the original layout.
"""

import json
import os
import shutil
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent

# ── Load the lookup table ────────────────────────────────────────────
with open(BASE_DIR / "diachronical_stats.json", encoding="utf-8") as f:
    stats = json.load(f)

# Build mapping: (lang, item_id) -> time_sensitivity
LABEL_MAP = {
    "Time-agnostic": "agnostic",
    "Weakly time-sensitive": "weak_sensitive",
    "强时效性": "sensitive",
}

sensitivity_lookup: dict[tuple[str, str], str] = {}
for entry in stats:
    raw_label = entry["time_sensitivity"].strip()
    mapped = LABEL_MAP.get(raw_label, "agnostic")
    sensitivity_lookup[(entry["lang"], entry["item_id"])] = mapped

# ── Discover and categorize JSON files ───────────────────────────────
TARGET_DIRS = [
    "agnostic",
    "weak_sensitive",
    "sensitive",
]
for d in TARGET_DIRS:
    (BASE_DIR / d).mkdir(exist_ok=True)

counters: dict[str, int] = defaultdict(int)

# Walk every domain/lang subdir  (e.g. Finance/CN, Law/EN, …)
for domain_dir in sorted(BASE_DIR.iterdir()):
    if not domain_dir.is_dir() or domain_dir.name in TARGET_DIRS:
        continue
    for lang_dir in sorted(domain_dir.iterdir()):
        if not lang_dir.is_dir():
            continue
        lang = lang_dir.name  # "CN" or "EN"
        for json_file in sorted(lang_dir.glob("*.json")):
            item_id = json_file.stem  # e.g. "SQL_Item_1221"
            key = (lang, item_id)
            category = sensitivity_lookup.get(key, "agnostic")

            dest_dir = BASE_DIR / category / domain_dir.name / lang
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(json_file, dest_dir / json_file.name)
            counters[category] += 1

# ── Report ───────────────────────────────────────────────────────────
print("=== Categorization complete ===")
for cat in TARGET_DIRS:
    print(f"  {cat}: {counters[cat]} files")
