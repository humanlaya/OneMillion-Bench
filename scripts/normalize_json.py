#!/usr/bin/env python3
"""
Normalize JSON filenames to the form SQL_Item_{digit}.json
and dump processed data into a "New" directory, preserving directory structure.

Handles patterns like:
  SQL_Item_1238_CN.json      -> SQL_Item_1238.json
  SQL_Item_7574_EN.json      -> SQL_Item_7574.json
  SQL_Item_7574_EN_更新.json  -> SQL_Item_7574.json  (updated version takes priority)
"""

import os
import re
import shutil
import json
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR
NEW_DIR = SCRIPT_DIR / "New"

# Match: SQL_Item_{digits} followed by optional suffixes like _CN, _EN, _EN_更新
PATTERN = re.compile(r"^(SQL_Item_\d+)(?:_[A-Za-z\u4e00-\u9fff]+)*\.json$")


def extract_normalized_name(filename: str) -> str | None:
    """Extract the normalized name SQL_Item_{digit}.json from a filename."""
    m = PATTERN.match(filename)
    if m:
        return m.group(1) + ".json"
    return None


def is_updated_version(filename: str) -> bool:
    """Check if this file is an updated (更新) version."""
    return "更新" in filename


def main():
    log = []
    stats = defaultdict(int)
    conflicts = []

    # Collect all candidate files grouped by (relative_dir, normalized_name)
    # so we can resolve conflicts (e.g. _EN vs _EN_更新)
    candidates: dict[tuple[str, str], list[Path]] = defaultdict(list)

    for root, _, files in os.walk(SRC_DIR):
        root_path = Path(root)
        # Skip the New directory and hidden dirs
        rel = root_path.relative_to(SRC_DIR)
        if str(rel).startswith("New") or str(rel).startswith("."):
            continue

        for f in files:
            if not f.endswith(".json"):
                continue
            norm = extract_normalized_name(f)
            if norm is None:
                stats["skipped"] += 1
                log.append(f"SKIP (no match): {rel / f}")
                continue
            candidates[(str(rel), norm)].append(root_path / f)

    # Process candidates, resolving duplicates
    for (rel_dir, norm_name), sources in sorted(candidates.items()):
        dst_dir = NEW_DIR / rel_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst_path = dst_dir / norm_name

        if len(sources) == 1:
            src = sources[0]
        else:
            # Prefer 更新 (updated) version; otherwise pick the first
            updated = [s for s in sources if is_updated_version(s.name)]
            if updated:
                src = updated[0]
                others = [s for s in sources if s != src]
                conflicts.append(
                    f"CONFLICT resolved: {norm_name} in {rel_dir} "
                    f"-> picked '{src.name}' over {[o.name for o in others]}"
                )
            else:
                src = sorted(sources, key=lambda p: p.name)[0]
                others = [s for s in sources if s != src]
                conflicts.append(
                    f"CONFLICT resolved: {norm_name} in {rel_dir} "
                    f"-> picked '{src.name}' over {[o.name for o in others]}"
                )

        shutil.copy2(src, dst_path)
        stats["copied"] += 1
        log.append(f"COPY: {src.relative_to(SRC_DIR)} -> New/{rel_dir}/{norm_name}")

    # Write process log
    report_path = NEW_DIR / "_normalize_report.json"
    NEW_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "total_copied": stats["copied"],
        "total_skipped": stats["skipped"],
        "conflicts_resolved": len(conflicts),
        "conflicts": conflicts,
        "details": log,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Done! Copied {stats['copied']} files, skipped {stats['skipped']}, "
          f"resolved {len(conflicts)} conflicts.")
    print(f"Output directory: {NEW_DIR}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
