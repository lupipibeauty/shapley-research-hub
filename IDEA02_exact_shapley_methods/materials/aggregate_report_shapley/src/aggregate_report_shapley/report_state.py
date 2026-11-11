from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable, Mapping, Sequence

from .model import CellKey, Record


@dataclass(slots=True)
class ReportState:
    counts: dict[CellKey, int]
    sums: dict[CellKey, int]

    @classmethod
    def empty(cls, cells: Iterable[CellKey]) -> "ReportState":
        ordered = tuple(cells)
        return cls(
            counts={cell: 0 for cell in ordered},
            sums={cell: 0 for cell in ordered},
        )

    def copy(self) -> "ReportState":
        return ReportState(self.counts.copy(), self.sums.copy())

    def add_record(self, record: Record, membership: Iterable[CellKey]) -> None:
        for cell in membership:
            self.counts[cell] += 1
            self.sums[cell] += record.amount

    def average(self, cell: CellKey) -> Fraction | None:
        count = self.counts[cell]
        return None if count == 0 else Fraction(self.sums[cell], count)

    def canonical(self, cells: Sequence[CellKey]) -> tuple[tuple[int, int], ...]:
        return tuple((self.counts[cell], self.sums[cell]) for cell in cells)


def state_for_mask(
    mask: int,
    records: Sequence[Record],
    membership: Sequence[Sequence[CellKey]],
    cells: Sequence[CellKey],
) -> ReportState:
    state = ReportState.empty(cells)
    for index, record in enumerate(records):
        if mask & (1 << index):
            state.add_record(record, membership[index])
    return state


def all_coalition_states(
    records: Sequence[Record],
    membership: Sequence[Sequence[CellKey]],
    cells: Sequence[CellKey],
) -> list[ReportState]:
    states = [ReportState.empty(cells)]
    for mask in range(1, 1 << len(records)):
        lsb = mask & -mask
        index = lsb.bit_length() - 1
        state = states[mask ^ lsb].copy()
        state.add_record(records[index], membership[index])
        states.append(state)
    return states


def assert_same_state(
    left: ReportState,
    right: ReportState,
    cells: Sequence[CellKey],
    *,
    context: str = "",
) -> None:
    if left.canonical(cells) != right.canonical(cells):
        mismatches = [
            (cell, left.counts[cell], left.sums[cell], right.counts[cell], right.sums[cell])
            for cell in cells
            if (left.counts[cell], left.sums[cell])
            != (right.counts[cell], right.sums[cell])
        ]
        raise AssertionError(f"report states differ {context}: {mismatches}")

