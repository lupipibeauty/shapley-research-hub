from __future__ import annotations

import csv
import sys
from fractions import Fraction
from pathlib import Path

from aggregate_report_shapley.block_permutation import block_contiguous_value
from aggregate_report_shapley.d1 import (
    D1_CELLS,
    D1_CITY_BLOCKS,
    D1_LEVELS,
    D1_MEMBERSHIP,
    D1_RECORDS,
    D1_REGION_BLOCKS,
)
from aggregate_report_shapley.exact_shapley import exact_shapley_subset
from aggregate_report_shapley.report_state import all_coalition_states
from aggregate_report_shapley.shapley_levels import shapley_levels_from_dividends
from aggregate_report_shapley.value_functions import D1ValueSuite


ROOT = Path(__file__).resolve().parents[1]


def l1(left: list[Fraction], right: list[Fraction]) -> Fraction:
    return sum((abs(a - b) for a, b in zip(left, right)), Fraction(0))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    states = all_coalition_states(D1_RECORDS, D1_MEMBERSHIP, D1_CELLS)
    suite = D1ValueSuite(states[-1])
    values = suite.all_values(states)
    output = ROOT / "outputs" / "tables" / "e1_method_distances.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["价值函数", "分配方法", "相对标准Shapley的L1距离", "相对标准Shapley的最大绝对差"])
        for value_name in ("V1", "V2"):
            table = values[value_name]
            standard = exact_shapley_subset(table, len(D1_RECORDS))
            methods = {
                "A4_城市连续排列": block_contiguous_value(table, D1_CITY_BLOCKS, len(D1_RECORDS)),
                "A4_地区连续排列": block_contiguous_value(table, D1_REGION_BLOCKS, len(D1_RECORDS)),
                "A5_Shapley层次值": shapley_levels_from_dividends(
                    table, D1_LEVELS, len(D1_RECORDS)
                ),
            }
            for method, allocation in methods.items():
                differences = [abs(a - b) for a, b in zip(allocation, standard)]
                writer.writerow(
                    [value_name, method, str(l1(allocation, standard)), str(max(differences))]
                )
    print(f"已写入结果：{output}")


if __name__ == "__main__":
    main()

