from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from .d1p import D1PSpec, D1PState, METRICS


FAMILY_METRICS = {
    "P": ("record_count",),
    "E": ("category_a_target_count", "category_a_target_share"),
    "J": ("attribute_present_count",),
    "M": ("category_b_target_share",),
}


def parse_fraction(value: str | int | float) -> Fraction:
    if isinstance(value, float):
        return Fraction(str(value))
    return Fraction(value)


class D1PValueSuite:
    def __init__(
        self,
        spec: D1PSpec,
        full_state: D1PState,
        value_spec_path: str | Path,
    ) -> None:
        self.spec = spec
        self.full = full_state
        raw = yaml.safe_load(Path(value_spec_path).read_text(encoding="utf-8"))
        self.revenue = Fraction(raw["revenue"])
        self.count_weights = {
            node: parse_fraction(weight)
            for node, weight in raw["values"]["V_count"]["node_weights"].items()
        }
        self.coordinate_weights = {
            (node, metric): parse_fraction(weight)
            for node, metrics in raw["values"]["V1_default_v3_2"]["coordinate_weights"].items()
            for metric, weight in metrics.items()
        }
        self.family_weights = {
            family: parse_fraction(weight)
            for family, weight in raw["values"]["V1_default_v3_2"]["family_weights"].items()
        }
        if sum(self.coordinate_weights.values(), Fraction()) != 1:
            raise ValueError("V1 coordinate weights must sum to one")

    def v0(self, mask: int) -> Fraction:
        return self.revenue * Fraction(mask.bit_count(), self.spec.player_count)

    def v_count(self, state: D1PState) -> Fraction:
        score = Fraction()
        for node, weight in self.count_weights.items():
            full_count = self.full.counts[node][0]
            score += weight * Fraction(state.counts[node][0], full_count)
        return self.revenue * score

    def coordinate_score(self, state: D1PState, node: str, metric: str) -> Fraction:
        total, category_a, present, category_b = state.counts[node]
        full_total, full_category_a, full_present, full_category_b = self.full.counts[node]
        if metric == "record_count":
            return Fraction(total, full_total)
        if metric == "category_a_target_count":
            return Fraction(category_a, full_category_a)
        if metric == "attribute_present_count":
            return Fraction(present, full_present)
        if metric == "category_a_target_share":
            if total == 0:
                return Fraction()
            current_ratio = Fraction(category_a, total)
            full_ratio = Fraction(full_category_a, full_total)
            return Fraction(total, full_total) * (1 - abs(current_ratio - full_ratio))
        if metric == "category_b_target_share":
            if present == 0:
                return Fraction()
            current_ratio = Fraction(category_b, present)
            full_ratio = Fraction(full_category_b, full_present)
            return Fraction(present, full_present) * (1 - abs(current_ratio - full_ratio))
        raise KeyError(metric)

    def family_scores(self, state: D1PState) -> dict[str, Fraction]:
        result: dict[str, Fraction] = {}
        for family, metrics in FAMILY_METRICS.items():
            family_weight = self.family_weights[family]
            weighted = sum(
                (
                    self.coordinate_weights[(node, metric)]
                    * self.coordinate_score(state, node, metric)
                    for node in self.spec.nodes
                    for metric in metrics
                ),
                Fraction(),
            )
            result[family] = weighted / family_weight
        return result

    def v1(self, state: D1PState) -> Fraction:
        return self.revenue * sum(
            (
                weight * self.coordinate_score(state, node, metric)
                for (node, metric), weight in self.coordinate_weights.items()
            ),
            Fraction(),
        )

    def v2_decimal(self, state: D1PState, interaction_lambda: Fraction, precision: int = 80) -> Decimal:
        families = self.family_scores(state)
        with localcontext() as context:
            context.prec = precision
            arithmetic = sum(
                (
                    Decimal(weight.numerator) / Decimal(weight.denominator)
                    * Decimal(families[family].numerator) / Decimal(families[family].denominator)
                    for family, weight in self.family_weights.items()
                ),
                Decimal(0),
            )
            if any(score == 0 for score in families.values()):
                geometric = Decimal(0)
            else:
                product = Decimal(1)
                for family, weight in self.family_weights.items():
                    score = families[family]
                    base = Decimal(score.numerator) / Decimal(score.denominator)
                    if weight == Fraction(1, 4):
                        product *= base
                    else:
                        product *= context.power(
                            base, Decimal(weight.numerator) / Decimal(weight.denominator)
                        )
                geometric = product.sqrt().sqrt() if all(
                    weight == Fraction(1, 4) for weight in self.family_weights.values()
                ) else product
            lam = Decimal(interaction_lambda.numerator) / Decimal(interaction_lambda.denominator)
            revenue = Decimal(self.revenue.numerator) / Decimal(self.revenue.denominator)
            return +(revenue * ((Decimal(1) - lam) * arithmetic + lam * geometric))

    def all_values(self, states: Sequence[D1PState]) -> dict[str, list[Fraction | Decimal]]:
        return {
            "V0": [self.v0(mask) for mask in range(len(states))],
            "V_count": [self.v_count(state) for state in states],
            "V1": [self.v1(state) for state in states],
            "V2_lambda_0": [self.v1(state) for state in states],
            "V2_lambda_0_5": [
                self.v2_decimal(state, Fraction(1, 2), precision=80) for state in states
            ],
        }


def count_closed_form(spec: D1PSpec, suite: D1PValueSuite) -> list[Fraction]:
    result = []
    for record in spec.records:
        contribution = sum(
            (
                suite.count_weights[node] / suite.full.counts[node][0]
                for node in spec.ancestors[record.leaf_node_id]
            ),
            Fraction(),
        )
        result.append(suite.revenue * contribution)
    return result

