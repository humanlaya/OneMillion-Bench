#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parser for ``economic_value.md``.

The Markdown file is one row per question with columns:
``UUID | Domain | CNY | USD | Subset``. Each row carries either CNY or USD
(never both); ``Subset`` is ``cn`` (CN ¥ wage anchoring) or ``global``
(US BLS USD wage anchoring).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple


@dataclass(frozen=True)
class EconomicValueEntry:
    """One row of ``economic_value.md``."""

    uuid: str
    domain: str
    subset: str  # "cn" or "global"
    currency: str  # "CNY" or "USD"
    value: float

    def as_tuple(self) -> Tuple[str, str, str, str, float]:
        return (self.uuid, self.domain, self.subset, self.currency, self.value)


class EconomicValueTable:
    """In-memory index of per-question economic values, keyed by UUID."""

    def __init__(self, entries: Iterable[EconomicValueEntry]):
        self._by_uuid: Dict[str, EconomicValueEntry] = {}
        for entry in entries:
            if entry.uuid in self._by_uuid:
                raise ValueError(f"Duplicate UUID in economic value table: {entry.uuid}")
            self._by_uuid[entry.uuid] = entry

    def __len__(self) -> int:
        return len(self._by_uuid)

    def __iter__(self) -> Iterator[EconomicValueEntry]:
        return iter(self._by_uuid.values())

    def __contains__(self, uuid: str) -> bool:  # type: ignore[override]
        return uuid in self._by_uuid

    def get(self, uuid: str) -> Optional[EconomicValueEntry]:
        return self._by_uuid.get(uuid)

    def lookup_any(self, candidates: Iterable[str]) -> Optional[EconomicValueEntry]:
        """Return the first matching entry for any of the candidate keys."""
        for key in candidates:
            if not key:
                continue
            entry = self._by_uuid.get(str(key))
            if entry is not None:
                return entry
        return None

    def domains(self) -> List[str]:
        return sorted({entry.domain for entry in self._by_uuid.values()})

    def subsets(self) -> List[str]:
        return sorted({entry.subset for entry in self._by_uuid.values()})

    def totals_by_subset(self) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        for entry in self._by_uuid.values():
            totals[entry.subset] = totals.get(entry.subset, 0.0) + entry.value
        return totals


def _split_pipe_row(line: str) -> List[str]:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    inner = stripped.strip("|")
    return [cell.strip() for cell in inner.split("|")]


def _parse_amount(raw: str) -> Optional[float]:
    cleaned = raw.replace(",", "").replace("¥", "").replace("$", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def load_economic_value_table(path: Path) -> EconomicValueTable:
    """Parse ``economic_value.md`` into an :class:`EconomicValueTable`.

    Validation:
      * Each row must be one and only one of CNY / USD.
      * ``Subset`` must be ``cn`` or ``global``.
      * UUIDs must be unique.
    """
    path = Path(path)
    entries: List[EconomicValueEntry] = []
    saw_header = False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        cells = _split_pipe_row(raw_line)
        if len(cells) < 5:
            continue
        if not saw_header:
            if cells[0].lower() == "uuid":
                saw_header = True
            continue
        # Skip the separator row "| ---- | ... |" right after the header.
        if all(set(cell) <= {"-", ":"} for cell in cells if cell):
            continue

        uuid_, domain, cny_raw, usd_raw, subset = cells[:5]
        if not uuid_:
            continue
        cny = _parse_amount(cny_raw)
        usd = _parse_amount(usd_raw)

        if cny is None and usd is None:
            raise ValueError(f"Row {uuid_} has neither CNY nor USD value")
        if cny is not None and usd is not None:
            raise ValueError(f"Row {uuid_} has both CNY and USD values")

        currency = "CNY" if cny is not None else "USD"
        value = cny if cny is not None else usd
        subset_norm = subset.lower()
        if subset_norm not in {"cn", "global"}:
            raise ValueError(
                f"Row {uuid_} has invalid subset {subset!r} (expected 'cn' or 'global')"
            )

        entries.append(
            EconomicValueEntry(
                uuid=uuid_,
                domain=domain,
                subset=subset_norm,
                currency=currency,
                value=float(value),
            )
        )

    return EconomicValueTable(entries)
