from __future__ import annotations

import csv
import json
import sys
import time
from fractions import Fraction
from pathlib import Path

import duckdb

from aggregate_report_shapley.block_permutation import (
    allowed_block_permutation_count,
    block_contiguous_value,
    enumerate_block_permutations,
    permutation_average,
)
from aggregate_report_shapley.d1 import (
    D1_CELLS,
    D1_CITY_BLOCKS,
    D1_LEVELS,
    D1_MEMBERSHIP,
    D1_RECORDS,
    D1_REGION_BLOCKS,
)
from aggregate_report_shapley.database_loader import create_d1_database
from aggregate_report_shapley.exact_shapley import efficiency_error, exact_shapley_subset
from aggregate_report_shapley.report_query import query_all_d1_reports
from aggregate_report_shapley.report_state import all_coalition_states, assert_same_state
from aggregate_report_shapley.shapley_levels import (
    harsanyi_dividends,
    shapley_from_dividends,
    shapley_levels_by_permutations,
    shapley_levels_from_dividends,
)
from aggregate_report_shapley.value_functions import D1ValueSuite


ROOT = Path(__file__).resolve().parents[1]
A0_NAME = "A0_标准Shapley"
A4_CITY_NAME = "A4_城市连续排列"
A4_REGION_NAME = "A4_地区连续排列"
A5_NAME = "A5_Shapley层次值"


def as_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    started = time.perf_counter()
    timings: dict[str, float] = {}

    checkpoint = time.perf_counter()
    incremental_states = all_coalition_states(D1_RECORDS, D1_MEMBERSHIP, D1_CELLS)
    timings["构造全部增量联盟状态_秒"] = time.perf_counter() - checkpoint

    checkpoint = time.perf_counter()
    connection = duckdb.connect(":memory:")
    create_d1_database(connection)
    sql_states = query_all_d1_reports(connection)
    for mask, (incremental, sql) in enumerate(zip(incremental_states, sql_states)):
        assert_same_state(incremental, sql, D1_CELLS, context=f"mask={mask}")
    timings["SQL计算全部4096个联盟_秒"] = time.perf_counter() - checkpoint

    suite = D1ValueSuite(incremental_states[-1])
    value_tables = suite.all_values(incremental_states)
    allocations: dict[tuple[str, str], list[Fraction]] = {}

    for value_name, values in value_tables.items():
        checkpoint = time.perf_counter()
        a0 = exact_shapley_subset(values, len(D1_RECORDS))
        timings[f"{value_name}_A0计算_秒"] = time.perf_counter() - checkpoint
        dividend_standard = shapley_from_dividends(
            harsanyi_dividends(values), len(D1_RECORDS)
        )
        if a0 != dividend_standard:
            raise AssertionError(f"{value_name}：A0 子集公式与红利公式不一致")
        if efficiency_error(a0, values) != 0:
            raise AssertionError(f"{value_name}：A0 效率性质失败")
        allocations[(value_name, A0_NAME)] = a0

        city_block = block_contiguous_value(values, D1_CITY_BLOCKS, len(D1_RECORDS))
        region_block = block_contiguous_value(values, D1_REGION_BLOCKS, len(D1_RECORDS))
        allocations[(value_name, A4_CITY_NAME)] = city_block
        allocations[(value_name, A4_REGION_NAME)] = region_block
        if efficiency_error(city_block, values) != 0 or efficiency_error(region_block, values) != 0:
            raise AssertionError(f"{value_name}：A4 效率性质失败")

        checkpoint = time.perf_counter()
        level_permutation, hierarchy_count = shapley_levels_by_permutations(
            values, len(D1_RECORDS)
        )
        level_dividend = shapley_levels_from_dividends(
            values, D1_LEVELS, len(D1_RECORDS)
        )
        timings[f"{value_name}_A5双重核验_秒"] = time.perf_counter() - checkpoint
        if hierarchy_count != 18_432:
            raise AssertionError(f"允许层次排列数异常：{hierarchy_count}")
        if level_permutation != level_dividend:
            raise AssertionError(f"{value_name}：A5 排列公式与红利公式不一致")
        if efficiency_error(level_permutation, values) != 0:
            raise AssertionError(f"{value_name}：A5 效率性质失败")
        allocations[(value_name, A5_NAME)] = level_permutation

    # Independent enumeration check for the 55,296 city-contiguous permutations.
    enumerated_city_v1, city_count = permutation_average(
        value_tables["V1"], enumerate_block_permutations(D1_CITY_BLOCKS), len(D1_RECORDS)
    )
    if city_count != 55_296:
        raise AssertionError(f"允许城市连续排列数异常：{city_count}")
    if enumerated_city_v1 != allocations[("V1", A4_CITY_NAME)]:
        raise AssertionError("城市连续子集公式与直接排列枚举不一致")

    expected_v0 = [Fraction(100, 12) for _ in D1_RECORDS]
    for method in (A0_NAME, A4_CITY_NAME, A4_REGION_NAME, A5_NAME):
        if allocations[("V0", method)] != expected_v0:
            raise AssertionError(f"{method}：V0 等额支付不变量失败")

    tables_dir = ROOT / "outputs" / "tables"
    raw_dir = ROOT / "outputs" / "raw"
    logs_dir = ROOT / "outputs" / "logs"
    for directory in (tables_dir, raw_dir, logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    with (raw_dir / "d1_coalition_values.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["联盟位掩码", "联盟记录数", "V0", "V1", "V2"])
        for mask in range(1 << len(D1_RECORDS)):
            writer.writerow(
                [mask, mask.bit_count(), *(as_text(value_tables[name][mask]) for name in ("V0", "V1", "V2"))]
            )

    with (tables_dir / "d1_exact_allocations.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["价值函数", "分配方法", "记录编号", "精确支付", "浮点支付"])
        for (value_name, method), allocation in sorted(allocations.items()):
            for record, payment in zip(D1_RECORDS, allocation):
                writer.writerow([value_name, method, record.record_id, as_text(payment), float(payment)])

    summary = {
        "状态": "通过",
        "联盟数量": 4096,
        "固定报表单元数": 13,
        "SQL与增量状态不一致数": 0,
        "允许排列数量": {
            "城市连续": allowed_block_permutation_count(D1_CITY_BLOCKS),
            "地区连续": allowed_block_permutation_count(D1_REGION_BLOCKS),
            "地理层次": 18_432,
        },
        "精确核验项目": [
            "A0 子集公式等于 A0 Harsanyi 红利公式",
            "V1 下 A4 城市连续子集公式等于55,296个允许排列的直接枚举",
            "A5 层次排列等于 Besner 红利公式",
            "V0/V1/V2 与 A0/A4/A5 均满足效率性质",
            "V0 等额支付不变量",
        ],
        "计时": timings,
        "总运行时间_秒": time.perf_counter() - started,
    }
    (logs_dir / "e0_correctness.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

