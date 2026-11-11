from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Iterable, Sequence

import yaml


COUNTERS = ("total", "category_a_target", "attribute_present", "category_b_target")
METRICS = (
    "record_count",
    "category_a_target_count",
    "category_a_target_share",
    "attribute_present_count",
    "category_b_target_share",
)


@dataclass(frozen=True, slots=True)
class D1PRecord:
    player_index: int
    record_id: str
    source: str
    owner_id: str
    leaf_node_id: str
    category_a_id: str
    attribute_present: bool
    category_b_id: str | None


@dataclass(frozen=True, slots=True)
class D1PSpec:
    records: tuple[D1PRecord, ...]
    nodes: tuple[str, ...]
    ancestors: dict[str, tuple[str, str, str]]
    category_a_target: str
    category_b_target: str
    revenue: int

    @property
    def player_count(self) -> int:
        return len(self.records)

    @property
    def full_mask(self) -> int:
        return (1 << self.player_count) - 1


@dataclass(slots=True)
class D1PState:
    counts: dict[str, list[int]]

    @classmethod
    def empty(cls, nodes: Iterable[str]) -> "D1PState":
        return cls({node: [0, 0, 0, 0] for node in nodes})

    def copy(self) -> "D1PState":
        return D1PState({node: values.copy() for node, values in self.counts.items()})

    def add_record(self, record: D1PRecord, spec: D1PSpec) -> None:
        increments = (
            1,
            int(record.category_a_id == spec.category_a_target),
            int(record.attribute_present),
            int(record.attribute_present and record.category_b_id == spec.category_b_target),
        )
        for node in spec.ancestors[record.leaf_node_id]:
            target = self.counts[node]
            for index, value in enumerate(increments):
                target[index] += value

    def canonical(self, nodes: Sequence[str]) -> tuple[tuple[int, int, int, int], ...]:
        return tuple(tuple(self.counts[node]) for node in nodes)

    def metric(self, node: str, metric: str) -> int | Fraction | None:
        total, category_a, present, category_b = self.counts[node]
        if metric == "record_count":
            return total
        if metric == "category_a_target_count":
            return category_a
        if metric == "category_a_target_share":
            return None if total == 0 else Fraction(category_a, total)
        if metric == "attribute_present_count":
            return present
        if metric == "category_b_target_share":
            return None if present == 0 else Fraction(category_b, present)
        raise KeyError(metric)


def load_d1p_spec(path: str | Path, *, revenue: int = 1000) -> D1PSpec:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    hierarchy = {
        row["leaf_node_id"]: (
            row["leaf_node_id"],
            row["parent_node_id"],
            row["root_node_id"],
        )
        for row in raw["hierarchy"]
    }
    records = tuple(
        D1PRecord(
            player_index=index,
            record_id=row["record_id"],
            source=row["source"],
            owner_id=row["owner_id"],
            leaf_node_id=row["leaf_node_id"],
            category_a_id=row["category_a_id"],
            attribute_present=bool(row["attribute_present"]),
            category_b_id=row.get("category_b_id"),
        )
        for index, row in enumerate(raw["records"])
    )
    return D1PSpec(
        records=records,
        nodes=tuple(raw["report"]["nodes"]),
        ancestors=hierarchy,
        category_a_target=raw["report"]["category_a_target"],
        category_b_target=raw["report"]["category_b_target"],
        revenue=revenue,
    )


def all_incremental_states(spec: D1PSpec) -> list[D1PState]:
    states = [D1PState.empty(spec.nodes)]
    for mask in range(1, 1 << spec.player_count):
        least_bit = mask & -mask
        index = least_bit.bit_length() - 1
        state = states[mask ^ least_bit].copy()
        state.add_record(spec.records[index], spec)
        states.append(state)
    return states


def state_for_mask(mask: int, spec: D1PSpec) -> D1PState:
    state = D1PState.empty(spec.nodes)
    for record in spec.records:
        if mask & (1 << record.player_index):
            state.add_record(record, spec)
    return state

