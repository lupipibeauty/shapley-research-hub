from __future__ import annotations

import json
import math
import statistics
import sys
import time
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(OFFICIAL))

from Algorithms.LExaShap.ShapleyCircuit import DNFCircuit  # noqa: E402
from aggregate_report_shapley.d1p import all_incremental_states, load_d1p_spec  # noqa: E402
from aggregate_report_shapley.d1p_values import D1PValueSuite  # noqa: E402
from aggregate_report_shapley.exact_shapley import (  # noqa: E402
    exact_shapley_decimal,
    exact_shapley_subset,
)


R0 = ROOT / "outputs" / "v4_0" / "R0"
R1 = ROOT / "outputs" / "v4_0" / "R1"
REPORTS = ROOT / "reports"
for directory in (R0, R1, REPORTS):
    directory.mkdir(parents=True, exist_ok=True)


def fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def official_dnf_shapley(dnf: list[set[str]]) -> tuple[dict[str, float], dict[str, dict]]:
    """Run untouched official circuit, then apply a documented external normalization.

    The official leaf probability vector is [0, 1/2]. Root coefficients are scaled
    by assignment probabilities and omit the final 2^n/n! normalization. The
    repository exposes raw gradient vectors via the attribute named
    ``banzhaf_values`` even in LExaShap.
    """
    circuit = DNFCircuit(dnf)
    n = len(circuit.vars)
    scale = (2**n) / math.factorial(n)
    result: dict[str, float] = {}
    raw: dict[str, dict] = {}
    for value in circuit.vars:
        label = str(value.label)
        grad = [float(item) for item in value.grad]
        prob = [float(item) for item in value.prob]
        scalar = sum(g * p for g, p in zip(grad, prob)) * scale
        result[label] = scalar
        raw[label] = {"grad": grad, "prob": prob, "scale": scale, "scalar": scalar}
    return result, raw


def boolean_values(dnf: list[set[str]]) -> tuple[list[str], list[Fraction]]:
    variables = sorted({variable for clause in dnf for variable in clause})
    values: list[Fraction] = []
    for mask in range(1 << len(variables)):
        selected = {variables[index] for index in range(len(variables)) if mask & (1 << index)}
        values.append(Fraction(int(any(clause <= selected for clause in dnf))))
    return variables, values


def exact_boolean_shapley(dnf: list[set[str]]) -> dict[str, Fraction]:
    variables, values = boolean_values(dnf)
    allocation = exact_shapley_subset(values, len(variables))
    return dict(zip(variables, allocation))


def mobius_fraction(values: list[Fraction], player_count: int) -> list[Fraction]:
    result = list(values)
    for player in range(player_count):
        bit = 1 << player
        for mask in range(1 << player_count):
            if mask & bit:
                result[mask] -= result[mask ^ bit]
    return result


def mobius_decimal(values: list[Decimal], player_count: int) -> list[Decimal]:
    with localcontext() as context:
        context.prec = 120
        result = list(values)
        for player in range(player_count):
            bit = 1 << player
            for mask in range(1 << player_count):
                if mask & bit:
                    result[mask] -= result[mask ^ bit]
        return [+value for value in result]


def zeta_fraction(dividends: list[Fraction], player_count: int) -> list[Fraction]:
    result = list(dividends)
    for player in range(player_count):
        bit = 1 << player
        for mask in range(1 << player_count):
            if mask & bit:
                result[mask] += result[mask ^ bit]
    return result


def zeta_decimal(dividends: list[Decimal], player_count: int) -> list[Decimal]:
    with localcontext() as context:
        context.prec = 120
        result = list(dividends)
        for player in range(player_count):
            bit = 1 << player
            for mask in range(1 << player_count):
                if mask & bit:
                    result[mask] += result[mask ^ bit]
        return [+value for value in result]


def main() -> None:
    run_started = time.perf_counter()
    cases = {
        "single": [{"x"}],
        "or2": [{"x1"}, {"x2"}],
        "and2": [{"x1", "x2"}],
        "readme_mixed": [{"x1", "x2"}, {"x3"}],
    }
    original_cases = {}
    for name, dnf in cases.items():
        started = time.perf_counter()
        official, raw = official_dnf_shapley(dnf)
        duration = time.perf_counter() - started
        oracle = exact_boolean_shapley(dnf)
        error = max(abs(official[key] - float(oracle[key])) for key in oracle)
        original_cases[name] = {
            "dnf": [sorted(clause) for clause in dnf],
            "official_raw": raw,
            "adapter_scalar": official,
            "exact_oracle": {key: fraction_text(value) for key, value in oracle.items()},
            "maximum_absolute_error": error,
            "duration_seconds": duration,
        }
        if error >= 1e-12:
            raise AssertionError(f"官方 Boolean DNF 与精确真值不一致: {name}, {error}")

    aggregate_input = [
        ([{"x1", "x2"}, {"x3"}], Fraction(3)),
        ([{"x4"}], Fraction(5)),
    ]
    aggregate = {key: 0.0 for key in ("x1", "x2", "x3", "x4")}
    aggregate_raw = []
    for dnf, coefficient in aggregate_input:
        component, raw = official_dnf_shapley(dnf)
        aggregate_raw.append(
            {
                "dnf": [sorted(clause) for clause in dnf],
                "coefficient": fraction_text(coefficient),
                "official_raw": raw,
            }
        )
        for player, value in component.items():
            aggregate[player] += float(coefficient) * value
    aggregate_oracle = {"x1": 0.5, "x2": 0.5, "x3": 2.0, "x4": 5.0}
    aggregate_error = max(abs(aggregate[key] - aggregate_oracle[key]) for key in aggregate)
    if aggregate_error >= 1e-12:
        raise AssertionError("README SUM/COUNT 线性组合例与精确真值不一致")

    r0_result = {
        "stage": "R0",
        "source": "用户提供的官方 GitHub ZIP",
        "archive_sha256": "7E28BA907C2D1AF830D49B89D8647F4ECD4D14DC6817ED73CABC791D2C31EF3C",
        "commit_sha": "ZIP 未携带 .git，无法从归档内确认",
        "license": "归档中未发现 LICENSE/COPYING，状态为未核验",
        "python": sys.version,
        "dependencies": {"numpy": "2.4.6", "scipy": "1.17.1"},
        "official_interface_note": "LExaShap 的 banzhaf_values 属性暴露梯度向量；最终标量需由外部适配器归一化。",
        "normalization": "sum(grad_i * prob_i) * 2^n / n!",
        "boolean_cases": original_cases,
        "aggregate_readme_case": {
            "input": aggregate_raw,
            "adapter_scalar": aggregate,
            "exact_oracle": aggregate_oracle,
            "maximum_absolute_error": aggregate_error,
        },
        "status": "REPRODUCED_ORIGINAL_WITH_EXPLICIT_POSTPROCESS",
    }
    (R0 / "abramovich_official_zip_run.json").write_text(
        json.dumps(r0_result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    spec = load_d1p_spec(ROOT / "config" / "d1p_design.yaml")
    states = all_incremental_states(spec)
    suite = D1PValueSuite(spec, states[-1], ROOT / "config" / "value_spec_v3_2.yaml")
    values = suite.all_values(states)

    vcount_coefficients: dict[str, Fraction] = {}
    official_vcount: dict[str, float] = {}
    vcount_started = time.perf_counter()
    for record in spec.records:
        coefficient = suite.revenue * sum(
            (
                suite.count_weights[node] / suite.full.counts[node][0]
                for node in spec.ancestors[record.leaf_node_id]
            ),
            Fraction(),
        )
        vcount_coefficients[record.record_id] = coefficient
        singleton, _ = official_dnf_shapley([{record.record_id}])
        official_vcount[record.record_id] = float(coefficient) * singleton[record.record_id]
    vcount_duration = time.perf_counter() - vcount_started
    exact_vcount = exact_shapley_subset(values["V_count"], spec.player_count)
    vcount_payment_error = max(
        abs(official_vcount[record.record_id] - float(exact_vcount[index]))
        for index, record in enumerate(spec.records)
    )
    vcount_coalition_error = max(
        abs(
            sum(
                float(vcount_coefficients[record.record_id])
                for record in spec.records
                if mask & (1 << record.player_index)
            )
            - float(values["V_count"][mask])
        )
        for mask in range(1 << spec.player_count)
    )
    if vcount_payment_error >= 1e-12 or vcount_coalition_error >= 1e-12:
        raise AssertionError("AB-3 V-count 适配未通过")

    basis = {}
    basis_started = time.perf_counter()
    for size in range(1, spec.player_count + 1):
        clause = {f"x{index}" for index in range(size)}
        official, raw = official_dnf_shapley([clause])
        expected = 1.0 / size
        maximum_error = max(abs(value - expected) for value in official.values())
        if maximum_error >= 1e-12:
            raise AssertionError(f"一致基官方输出错误: size={size}")
        basis[size] = {
            "expected": expected,
            "official": statistics.fmean(official.values()),
            "maximum_absolute_error": maximum_error,
            "raw_example": next(iter(raw.values())),
        }
    basis_duration = time.perf_counter() - basis_started

    v1_table = values["V1"]
    v1_compile_started = time.perf_counter()
    v1_dividends = mobius_fraction(v1_table, spec.player_count)
    v1_compile_duration = time.perf_counter() - v1_compile_started
    if zeta_fraction(v1_dividends, spec.player_count) != v1_table:
        raise AssertionError("V1 Harsanyi 展开未能精确重建联盟值")
    v1_official_basis = [0.0 for _ in spec.records]
    for mask in range(1, 1 << spec.player_count):
        if v1_dividends[mask] == 0:
            continue
        share = basis[mask.bit_count()]["official"]
        for player in range(spec.player_count):
            if mask & (1 << player):
                v1_official_basis[player] += float(v1_dividends[mask]) * share
    v1_exact = exact_shapley_subset(v1_table, spec.player_count)
    v1_payment_error = max(abs(v1_official_basis[i] - float(v1_exact[i])) for i in range(spec.player_count))

    v2_table = values["V2_lambda_0_5"]
    v2_compile_started = time.perf_counter()
    v2_dividends = mobius_decimal(v2_table, spec.player_count)
    v2_compile_duration = time.perf_counter() - v2_compile_started
    reconstructed_v2 = zeta_decimal(v2_dividends, spec.player_count)
    v2_reconstruction_error = max(abs(a - b) for a, b in zip(reconstructed_v2, v2_table))
    with localcontext() as context:
        context.prec = 120
        v2_official_basis = [Decimal(0) for _ in spec.records]
        for mask in range(1, 1 << spec.player_count):
            if v2_dividends[mask] == 0:
                continue
            share = Decimal(str(basis[mask.bit_count()]["official"]))
            for player in range(spec.player_count):
                if mask & (1 << player):
                    v2_official_basis[player] += v2_dividends[mask] * share
        v2_official_basis = [+value for value in v2_official_basis]
    v2_exact = exact_shapley_decimal(v2_table, spec.player_count, precision=100)
    v2_payment_error = max(abs(v2_official_basis[i] - v2_exact[i]) for i in range(spec.player_count))

    r1_result = {
        "stage": "R1",
        "same_game_contract": {
            "players": [record.record_id for record in spec.records],
            "coalitions": 4096,
            "report": "D1-P 35 坐标整表",
            "source_binding": "一个 record_id 对应一个来源变量；Basic 与 Optional 物理行共同激活",
        },
        "AB-1_AB-2_AB-3": {
            "construction": "每条记录使用单变量单子句 DNF，系数等于该记录对归一化 COUNT 线性组合的贡献",
            "vcount_coefficients": {key: fraction_text(value) for key, value in vcount_coefficients.items()},
            "official_payments": official_vcount,
            "exact_payments": {
                record.record_id: fraction_text(exact_vcount[index])
                for index, record in enumerate(spec.records)
            },
            "maximum_payment_error": vcount_payment_error,
            "maximum_coalition_value_error": vcount_coalition_error,
            "duration_seconds": vcount_duration,
            "status": "FULL_SAME_GAME",
        },
        "official_unanimity_basis": {
            "sizes_1_to_12": basis,
            "duration_seconds": basis_duration,
        },
        "AB-4_V1": {
            "construction": "先精确枚举 4096 联盟，再用 Harsanyi/Mobius 变换为带系数的一致游戏 DNF 之和",
            "nonzero_terms": sum(value != 0 for value in v1_dividends[1:]),
            "total_possible_terms": 4095,
            "coalition_reconstruction_error": "0/1",
            "maximum_payment_error": v1_payment_error,
            "compile_seconds": v1_compile_duration,
            "status": "FULL_SAME_GAME_BUT_EXPONENTIAL_PRECOMPILATION",
        },
        "AB-5_V2_lambda_0_5": {
            "construction": "先高精度枚举 4096 联盟，再用 Harsanyi/Mobius 变换为带实系数的一致游戏 DNF 之和",
            "nonzero_terms": sum(value != 0 for value in v2_dividends[1:]),
            "total_possible_terms": 4095,
            "coalition_reconstruction_max_error": format(v2_reconstruction_error, "f"),
            "maximum_payment_error": format(v2_payment_error, "f"),
            "compile_seconds": v2_compile_duration,
            "status": "FULL_SAME_GAME_BUT_EXPONENTIAL_PRECOMPILATION_AND_NUMERICAL",
        },
        "interpretation": "V1/V2 可在固定 12 玩家上通过完整联盟真值的指数展开输入官方一致基，但该转换先支付了精确枚举成本，不能作为高效适配或新算法。",
        "total_seconds": time.perf_counter() - run_started,
    }
    (R1 / "abramovich_d1p_adaptation.json").write_text(
        json.dumps(r1_result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report = f"""# Abramovich 官方 ZIP 复现与 D1-P 同目标适配报告

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run + validate
- Origin Date: 2026-10-30
- Verification Status: VERIFIED（限 ZIP 内代码与本报告所列输入）
- Version Label: multisource_report_v4_0_abramovich_zip

## 官方代码来源

源码来自用户提供的 `LExaBan-LExaShap-main.zip`，SHA-256 为 `7E28BA907C2D1AF830D49B89D8647F4ECD4D14DC6817ED73CABC791D2C31EF3C`。ZIP 不含 `.git`，无法从归档内部确认提交 SHA；归档也未发现 LICENSE/COPYING 文件，因此许可证状态保持未核验。官方源码未补丁修改，本项目后处理位于独立实验脚本中。

## R0 原目标复现

README 的 Boolean DNF 最小例 `(x1 AND x2) OR x3` 成功运行。官方 `banzhaf_values` 属性返回梯度向量，不是最终标量；外部后处理公式为 `sum(grad_i * prob_i) × 2^n / n!`。处理后得到 `x1=1/6、x2=1/6、x3=2/3`，与独立联盟枚举完全一致。

单变量、二元 OR、二元 AND、README 混合例的最大绝对误差均小于 `1e-12`。README 的带系数聚合例 `3*((x1 AND x2) OR x3)+5*x4` 得到 `(0.5,0.5,2,5)`，与精确真值一致。

## R1 D1-P 适配

AB-1 至 AB-3 使用一个 `record_id` 对应一个来源变量的单子句 DNF，BasicSource 与 OptionalAttribute 仍绑定为同一逻辑玩家。完整 V-count 的 4096 个联盟最大价值误差为 `{vcount_coalition_error}`，记录支付最大误差为 `{vcount_payment_error}`，状态为 `FULL_SAME_GAME`。

AB-4 的 V1 可以先由完整联盟真值做 Harsanyi 展开，再写成带系数一致游戏 DNF 之和；非零项为 `{sum(value != 0 for value in v1_dividends[1:])}/4095`，支付最大误差为 `{v1_payment_error}`。

AB-5 的 V2(λ=0.5) 也能在固定 12 玩家上做同样转换；非零项为 `{sum(value != 0 for value in v2_dividends[1:])}/4095`，支付最大数值误差为 `{format(v2_payment_error, 'f')}`。

## 研究边界

V1/V2 的转换虽然保持同一玩家、同一联盟价值和同一 Shapley 目标，但它以预先枚举全部 4096 个联盟并构造最多 4095 个一致基项为代价。它证明固定小实例“可表达”，没有证明原生 SQL 到来源表达的高效编译，也没有减少精确 Shapley 的指数成本。因此不能把该结果写成现有算法对完整报表的高效解决方案。

## 原始结果

- `outputs/v4_0/R0/abramovich_official_zip_run.json`
- `outputs/v4_0/R1/abramovich_d1p_adaptation.json`
"""
    (REPORTS / "Abramovich官方ZIP复现与D1P适配_v4_0.md").write_text(report, encoding="utf-8")
    print("Abramovich R0/R1 completed", flush=True)


if __name__ == "__main__":
    main()
