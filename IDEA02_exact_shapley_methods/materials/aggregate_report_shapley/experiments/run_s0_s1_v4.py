from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aggregate_report_shapley.d1p import (  # noqa: E402
    METRICS,
    all_incremental_states,
    load_d1p_spec,
)
from aggregate_report_shapley.d1p_sql import (  # noqa: E402
    create_d1p_database,
    query_all_sql_p,
    query_all_sql_u,
)
from aggregate_report_shapley.d1p_values import (  # noqa: E402
    D1PValueSuite,
    count_closed_form,
)
from aggregate_report_shapley.exact_shapley import (  # noqa: E402
    exact_shapley_decimal,
    exact_shapley_subset,
    shapley_via_mobius_decimal,
    shapley_via_mobius_fraction,
)


OUT = ROOT / "outputs" / "v4_0"
S0 = OUT / "S0"
S1 = OUT / "S1"
REPORTS = ROOT / "reports"
for directory in (S0, S1, REPORTS):
    directory.mkdir(parents=True, exist_ok=True)

LOG_PATH = S1 / "run_s0_s1.log"


def log(message: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def state_digest(states, nodes) -> str:
    digest = hashlib.sha256()
    for mask, state in enumerate(states):
        digest.update(str(mask).encode())
        digest.update(repr(state.canonical(nodes)).encode())
    return digest.hexdigest()


def serialize_number(value: Fraction | Decimal) -> str:
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    return format(value, "f")


def benchmark(function, *, warmup: int = 1, runs: int = 3):
    for _ in range(warmup):
        function()
    durations = []
    last = None
    for _ in range(runs):
        start = time.perf_counter()
        last = function()
        durations.append(time.perf_counter() - start)
    return last, {
        "runs": runs,
        "minimum_seconds": min(durations),
        "median_seconds": statistics.median(durations),
        "maximum_seconds": max(durations),
        "raw_seconds": durations,
    }


def audit_edges(name, table, player_count: int):
    negative = zero = positive = 0
    minimum = None
    maximum = None
    minimum_edge = maximum_edge = None
    for mask, base in enumerate(table):
        for player in range(player_count):
            bit = 1 << player
            if mask & bit:
                continue
            delta = table[mask | bit] - base
            if delta < 0:
                negative += 1
            elif delta == 0:
                zero += 1
            else:
                positive += 1
            if minimum is None or delta < minimum:
                minimum, minimum_edge = delta, (mask, player)
            if maximum is None or delta > maximum:
                maximum, maximum_edge = delta, (mask, player)
    return {
        "value": name,
        "edges": negative + zero + positive,
        "negative_edges": negative,
        "zero_edges": zero,
        "positive_edges": positive,
        "minimum_marginal": serialize_number(minimum),
        "minimum_edge": {"mask": minimum_edge[0], "player_index": minimum_edge[1]},
        "maximum_marginal": serialize_number(maximum),
        "maximum_edge": {"mask": maximum_edge[0], "player_index": maximum_edge[1]},
        "value_minimum": serialize_number(min(table)),
        "value_maximum": serialize_number(max(table)),
    }


def write_truth_table(states, spec) -> None:
    path = S1 / "coalition_report_truth.csv.gz"
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "mask", "coalition_size", "node_id", "total_count",
                "category_a_target_count", "attribute_present_count",
                "category_b_target_count", "category_a_target_share",
                "category_b_target_share",
            ]
        )
        for mask, state in enumerate(states):
            for node in spec.nodes:
                total, category_a, present, category_b = state.counts[node]
                writer.writerow(
                    [
                        mask, mask.bit_count(), node, total, category_a, present, category_b,
                        "NULL" if total == 0 else serialize_number(Fraction(category_a, total)),
                        "NULL" if present == 0 else serialize_number(Fraction(category_b, present)),
                    ]
                )


def main() -> None:
    if LOG_PATH.exists():
        attempt = 1
        while (S1 / f"run_s0_s1_attempt_{attempt}_previous.log").exists():
            attempt += 1
        LOG_PATH.replace(S1 / f"run_s0_s1_attempt_{attempt}_previous.log")
    started = time.perf_counter()
    log("S0/S1 开始：冻结 D1-P 输入并构造三条真值路径。")

    config_paths = [
        ROOT / "config" / "d1p_design.yaml",
        ROOT / "config" / "report_spec_v3_2.yaml",
        ROOT / "config" / "value_spec_v3_2.yaml",
        ROOT / "config" / "value_audit_v4_0.yaml",
        ROOT / "config" / "protocol_v4_0.yaml",
    ]
    environment = {
        "timestamp": datetime.now().isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "duckdb": duckdb.__version__,
        "cwd": str(ROOT),
        "git_repository": False,
        "rust_cargo_available": False,
        "input_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in config_paths},
    }
    (S0 / "environment_and_input_hashes.json").write_text(
        json.dumps(environment, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    load_start = time.perf_counter()
    spec = load_d1p_spec(ROOT / "config" / "d1p_design.yaml")
    load_seconds = time.perf_counter() - load_start
    if spec.player_count != 12 or len(spec.nodes) != 7 or len(METRICS) != 5:
        raise AssertionError("冻结结构不是 12 玩家、7 节点、5 指标")
    log("S0 冻结完成：12 个逻辑记录玩家、7 个汇总节点、35 个输出坐标。")

    connection = duckdb.connect(":memory:")
    create_d1p_database(connection, spec)
    sql_p, timing_sql_p = benchmark(lambda: query_all_sql_p(connection, spec))
    sql_u, timing_sql_u = benchmark(lambda: query_all_sql_u(connection, spec))
    incremental, timing_st = benchmark(lambda: all_incremental_states(spec))
    digests = {
        "SQL-P": state_digest(sql_p, spec.nodes),
        "SQL-U": state_digest(sql_u, spec.nodes),
        "ST": state_digest(incremental, spec.nodes),
    }
    mismatches = []
    for mask in range(1 << spec.player_count):
        truth = incremental[mask].canonical(spec.nodes)
        if sql_p[mask].canonical(spec.nodes) != truth:
            mismatches.append({"mask": mask, "implementation": "SQL-P"})
        if sql_u[mask].canonical(spec.nodes) != truth:
            mismatches.append({"mask": mask, "implementation": "SQL-U"})
    if mismatches:
        raise AssertionError(f"三路径不一致：{mismatches[:10]}")
    log("S1 报表真值通过：4096 个联盟的 SQL-P、SQL-U、ST 逐计数完全一致。")

    expected_full = {
        "COUNTRY": [12, 6, 10, 6], "A": [4, 2, 3, 2], "B": [8, 4, 7, 4],
        "A1": [2, 1, 2, 1], "A2": [2, 1, 1, 1],
        "B1": [4, 2, 3, 2], "B2": [4, 2, 4, 2],
    }
    if incremental[-1].counts != expected_full:
        raise AssertionError("满联盟硬编码断言失败")
    if incremental[7].counts["COUNTRY"] != [3, 1, 3, 2]:
        raise AssertionError("mask=7 硬编码断言失败")

    suite = D1PValueSuite(
        spec, incremental[-1], ROOT / "config" / "value_spec_v3_2.yaml"
    )
    values, timing_value = benchmark(lambda: suite.all_values(incremental))
    if values["V2_lambda_0"] != values["V1"]:
        raise AssertionError("V2(lambda=0) 未与 V1 精确一致")
    audits = [audit_edges(name, table, spec.player_count) for name, table in values.items()]

    boundary_epsilon = Decimal("1e-27")
    boundary_edges = []
    v2_table = values["V2_lambda_0_5"]
    for mask, base in enumerate(v2_table):
        for player in range(spec.player_count):
            bit = 1 << player
            if mask & bit:
                continue
            if abs(v2_table[mask | bit] - base) < boundary_epsilon:
                high_left = suite.v2_decimal(incremental[mask], Fraction(1, 2), 120)
                high_right = suite.v2_decimal(incremental[mask | bit], Fraction(1, 2), 120)
                boundary_edges.append(
                    {
                        "mask": mask, "player_index": player,
                        "delta_120": serialize_number(high_right - high_left),
                    }
                )
    if any(Decimal(edge["delta_120"]) < 0 for edge in boundary_edges):
        raise AssertionError("V2 高精度边界复核发现负边际")
    if any(audit["negative_edges"] for audit in audits):
        raise AssertionError("单调性审计发现负边际")
    log("S1 价值性质通过：5 个价值版本各检查 24576 条加边边，未发现负边际。")

    def solve_all():
        result = {}
        for name in ("V0", "V_count", "V1", "V2_lambda_0"):
            result[name] = exact_shapley_subset(values[name], spec.player_count)
        result["V2_lambda_0_5"] = exact_shapley_decimal(
            values["V2_lambda_0_5"], spec.player_count, precision=100
        )
        return result

    allocations, timing_shapley = benchmark(solve_all)
    oracle_diffs = {}
    for name in ("V0", "V_count", "V1", "V2_lambda_0"):
        independent = shapley_via_mobius_fraction(values[name], spec.player_count)
        oracle_diffs[name] = serialize_number(
            max(abs(a - b) for a, b in zip(allocations[name], independent))
        )
    independent_decimal = shapley_via_mobius_decimal(
        values["V2_lambda_0_5"], spec.player_count, precision=100
    )
    oracle_diffs["V2_lambda_0_5"] = serialize_number(
        max(abs(a - b) for a, b in zip(allocations["V2_lambda_0_5"], independent_decimal))
    )
    if any(oracle_diffs[name] != "0/1" for name in ("V0", "V_count", "V1", "V2_lambda_0")):
        raise AssertionError("精确值的子集公式与 Möbius 真值不一致")
    if Decimal(oracle_diffs["V2_lambda_0_5"]) >= Decimal("1e-70"):
        raise AssertionError("V2 的两套高精度 Shapley 路径不一致")
    if allocations["V_count"] != count_closed_form(spec, suite):
        raise AssertionError("V-count 闭式与枚举 Shapley 不一致")

    decomposition = [Fraction() for _ in spec.records]
    coordinate_rows = []
    for node in spec.nodes:
        for metric in METRICS:
            weight = suite.coordinate_weights[(node, metric)]
            table = [
                suite.revenue * weight * suite.coordinate_score(state, node, metric)
                for state in incremental
            ]
            coordinate_phi = exact_shapley_subset(table, spec.player_count)
            for index, value in enumerate(coordinate_phi):
                decomposition[index] += value
                coordinate_rows.append(
                    {
                        "node": node, "metric": metric,
                        "player_id": spec.records[index].record_id,
                        "shapley": serialize_number(value),
                    }
                )
    if decomposition != allocations["V1"]:
        raise AssertionError("V1 坐标线性分解与直接枚举不一致")

    for name, allocation in allocations.items():
        if isinstance(allocation[0], Fraction):
            if sum(allocation, Fraction()) != Fraction(1000):
                raise AssertionError(f"{name} 预算平衡失败")
        else:
            with localcontext() as context:
                context.prec = 100
                if abs(sum(allocation, Decimal(0)) - Decimal(1000)) >= Decimal("1e-70"):
                    raise AssertionError(f"{name} 高精度预算平衡失败")
    log("S1 Shapley 通过：子集公式、Mobius/Harsanyi、闭式及坐标分解相互一致。")

    write_truth_table(incremental, spec)
    with gzip.open(S1 / "coalition_values.csv.gz", "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["mask", *values.keys()])
        for mask in range(1 << spec.player_count):
            writer.writerow([mask, *(serialize_number(values[name][mask]) for name in values)])
    with (S1 / "shapley_payments.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["player_index", "player_id", "source", *allocations.keys()])
        for index, record in enumerate(spec.records):
            writer.writerow(
                [index, record.record_id, record.source,
                 *(serialize_number(allocations[name][index]) for name in allocations)]
            )
    with (S1 / "v1_coordinate_decomposition.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["node", "metric", "player_id", "shapley"])
        writer.writeheader()
        writer.writerows(coordinate_rows)

    timing = {
        "T_load_seconds": load_seconds,
        "T_sql_p": timing_sql_p,
        "T_sql_u": timing_sql_u,
        "T_shared_state": timing_st,
        "T_value_eval": timing_value,
        "T_shapley_compute": timing_shapley,
        "T_total_seconds": time.perf_counter() - started,
        "peak_rss": "NA（当前无无侵入式进程峰值采集器）",
        "temporary_disk_bytes": sum(
            path.stat().st_size for path in S1.glob("*") if path.is_file()
        ),
    }
    summary = {
        "dataset": "D1-P（完全合成控制数据）",
        "players": spec.player_count,
        "nodes": len(spec.nodes),
        "coordinates": len(spec.nodes) * len(METRICS),
        "coalitions": 1 << spec.player_count,
        "directed_edges_per_value": spec.player_count * (1 << (spec.player_count - 1)),
        "implementation_hashes": digests,
        "mismatches": mismatches,
        "value_audits": audits,
        "v2_boundary_rechecks": boundary_edges,
        "independent_oracle_max_abs_diff": oracle_diffs,
        "timing": timing,
    }
    (S1 / "verification_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    audit_lines = "\n".join(
        f"| {a['value']} | {a['edges']} | {a['negative_edges']} | {a['zero_edges']} | {a['positive_edges']} | {a['minimum_marginal']} | {a['maximum_marginal']} |"
        for a in audits
    )
    payments_lines = "\n".join(
        f"| {record.record_id} | {record.source} | {serialize_number(allocations['V0'][i])} | {serialize_number(allocations['V_count'][i])} | {serialize_number(allocations['V1'][i])} | {serialize_number(allocations['V2_lambda_0_5'][i])} |"
        for i, record in enumerate(spec.records)
    )
    report = f"""# S0/S1 阶段实验报告（中文）

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run + validate
- Origin Date: {datetime.now().date().isoformat()}
- Verification Status: VERIFIED
- Version Label: multisource_report_v4_0_s0_s1

## 实验结论

S0 与 S1 已通过。D1-P 的 4096 个联盟在 SQL-P、SQL-U 和共享统计状态 ST 三条实现上逐节点、逐内部计数完全一致；V0、V-count、V1、V2(λ=0) 使用有理数精确计算，V2(λ=0.5) 使用 80 位联盟值与 100 位 Shapley 汇总。五个价值版本各审计 24576 条加边边，均未出现负边际。

## 数据来源与构造

D1-P 来自冻结文件 `config/d1p_design.yaml`，是完全合成控制数据，不来自真实人口数据库。12 个逻辑记录包 p1–p12 分布在 A1、A2、B1、B2 四个底层来源；每个包包含一条 BasicSource 记录和零或一条 OptionalAttribute 记录。固定 Hierarchy 把叶节点映射到父节点 A/B 和根节点 COUNTRY。联盟只激活逻辑记录包，固定维表不成为玩家。

报表固定包含 COUNTRY、A、B、A1、A2、B1、B2 七个节点；每节点输出记录数、E2 数、E2 占比、属性存在数、制造业占有属性记录比例五项，共 35 坐标。空节点计数为 0；SQL 比例为 NULL，进入价值层后得分为 0。

## 三条真值路径的构造

- SQL-P：四张物理 BasicSource 表先 UNION ALL，再按联盟位图激活记录，LEFT JOIN OptionalAttribute，JOIN 固定 Hierarchy，并展开到叶、父、根三个节点。
- SQL-U：先物化统一逻辑事实表，再执行等价的联盟激活、层级展开与 GROUP BY。
- ST：从空状态递推，每加入一条逻辑记录，只更新其叶、父、根三个节点上的 total/E2/present/manufacturing 四个可加计数。

三条路径的状态哈希相同：`{digests['ST']}`。联盟差异数为 0。

## 价值函数与数值规则

V0 按联盟记录数线性分配；V-count 对七个节点的记录覆盖率加权；V1 对 35 坐标的计数覆盖和带覆盖率的比例相似度加权；V2 以四个指标族的算术聚合与几何聚合组合。满联盟参考值在运行前冻结，联盟内不动态重归一化。V2(λ=0) 与 V1 逐联盟精确相同。

| 价值 | 边数 | 负边际 | 零边际 | 正边际 | 最小边际 | 最大边际 |
|---|---:|---:|---:|---:|---:|---:|
{audit_lines}

## 精确 Shapley 交叉验证

每个价值先由标准子集公式求解，再由 Möbius/Harsanyi 红利变换独立复核。V-count 还与记录所在叶、父、根节点贡献的闭式相核对；V1 还与 35 个坐标游戏分别求值后线性相加的结果核对。精确价值误差为 0；V2(λ=0.5) 两条高精度路径最大绝对差为 `{oracle_diffs['V2_lambda_0_5']}`。

| 玩家 | 来源 | V0 | V-count | V1 | V2(λ=0.5) |
|---|---|---:|---:|---:|---:|
{payments_lines}

## 运行成本

- 配置加载：{load_seconds:.6f} 秒。
- SQL-P 中位数：{timing_sql_p['median_seconds']:.6f} 秒；SQL-U 中位数：{timing_sql_u['median_seconds']:.6f} 秒。
- ST 中位数：{timing_st['median_seconds']:.6f} 秒。
- 五套联盟价值评价中位数：{timing_value['median_seconds']:.6f} 秒。
- 五套 Shapley 求解中位数：{timing_shapley['median_seconds']:.6f} 秒。
- 峰值 RSS：NA；本轮没有把 Python 分配跟踪值冒充进程峰值内存。

## 异常与解释边界

首次测试曾因 Decimal 求解与测试求和回落到默认 28 位精度而出现表观误差；修正为显式 100 位上下文后通过。这是数值实现问题，不是价值函数或算法理论误差。当前结果只建立 D1-P 精确真值与单调性，不构成新算法贡献，也不支持 S2–S5 的规模性结论。

## 输出文件

- `outputs/v4_0/S0/environment_and_input_hashes.json`
- `outputs/v4_0/S1/coalition_report_truth.csv.gz`
- `outputs/v4_0/S1/coalition_values.csv.gz`
- `outputs/v4_0/S1/shapley_payments.csv`
- `outputs/v4_0/S1/v1_coordinate_decomposition.csv`
- `outputs/v4_0/S1/verification_summary.json`
- `outputs/v4_0/S1/run_s0_s1.log`
"""
    (REPORTS / "S0_S1阶段实验报告_v4_0.md").write_text(report, encoding="utf-8")
    log("S0/S1 全部输出已写入 outputs/v4_0 与 reports。")


if __name__ == "__main__":
    main()

