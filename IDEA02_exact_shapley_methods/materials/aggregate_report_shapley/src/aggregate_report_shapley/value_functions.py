from __future__ import annotations

from fractions import Fraction
from math import ceil
from typing import Sequence

from .d1 import D1_MODULE_CELLS
from .report_state import ReportState


class D1ValueSuite:
    def __init__(self, full_state: ReportState, revenue: int = 100) -> None:
        self.revenue = Fraction(revenue)
        self.full_state = full_state
        self.thresholds = {
            cell: ceil(Fraction(3, 4) * full_state.counts[cell])
            for cells in D1_MODULE_CELLS.values()
            for cell in cells
        }
        module_budget = self.revenue / len(D1_MODULE_CELLS)
        self.v1_weights = {
            cell: module_budget / len(cells)
            for cells in D1_MODULE_CELLS.values()
            for cell in cells
        }

    def v0(self, mask: int, player_count: int = 12) -> Fraction:
        return self.revenue * mask.bit_count() / player_count

    def v1(self, state: ReportState) -> Fraction:
        return sum(
            (
                weight
                for cell, weight in self.v1_weights.items()
                if state.counts[cell] >= self.thresholds[cell]
            ),
            Fraction(0),
        )

    def v2(self, state: ReportState) -> Fraction:
        local = Fraction(4, 5) * self.v1(state)
        geography_ready = all(
            state.counts[cell] >= self.thresholds[cell]
            for cell in D1_MODULE_CELLS["region"]
        )
        category_ready = all(
            state.counts[cell] >= self.thresholds[cell]
            for cell in D1_MODULE_CELLS["category"]
        )
        return local + (Fraction(20) if geography_ready and category_ready else 0)

    def all_values(self, states: Sequence[ReportState]) -> dict[str, list[Fraction]]:
        return {
            "V0": [self.v0(mask) for mask in range(len(states))],
            "V1": [self.v1(state) for state in states],
            "V2": [self.v2(state) for state in states],
        }

