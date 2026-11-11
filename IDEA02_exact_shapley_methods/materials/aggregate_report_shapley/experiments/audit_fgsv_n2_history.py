from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "external" / "fgsv" / "source" / "Faithful_GSV-main" / "exp1_benchmark"
sys.path[:0] = [str(ROOT / "src"), str(OFFICIAL)]

from aggregate_report_shapley.fgsv_ablation import STAGES, fgsv_sequential_ablation  # noqa: E402
from estimators import FGSV  # noqa: E402


OUT = ROOT / "outputs" / "v4_0" / "AUDIT_FGSV_N2"
HISTORICAL = (
    ROOT / "outputs" / "v4_0" / "R2" / "minimal_counterexample.json",
    ROOT / "outputs" / "v4_0" / "R2_3" / "audit.json",
    ROOT / "outputs" / "v4_0" / "R2_4" / "analytic_smoke_tests.csv",
    ROOT / "outputs" / "v4_0" / "R2_4" / "audit.json",
    ROOT / "reports" / "fgsv_r2_3_formula_audit.md",
    ROOT / "reports" / "fgsv_r2_3_formula_verification.md",
    ROOT / "reports" / "fgsv_r2_4_error_source_decomposition.md",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CappedUtility:
    def __init__(self, weights: list[float]):
        self.weights = np.asarray(weights, dtype=float)
        self.calls = 0

    def __call__(self, selection) -> float:
        self.calls += 1
        indexes = np.asarray(selection, dtype=int)
        return float(self.weights[indexes].sum()) if indexes.size else 0.0


def run_official(weights: list[float]) -> tuple[float, list[float]]:
    array = np.asarray(weights, dtype=float)

    def utility(selection, *_ignored) -> float:
        indexes = np.asarray(selection, dtype=int)
        return float(array[indexes].sum()) if indexes.size else 0.0

    np.random.seed(20261031)
    curve = FGSV(
        utility,
        2,
        None,
        None,
        None,
        np.asarray([0], dtype=int),
        100,
        10,
        thres=10,
    )
    return float(curve[-1]), [float(value) for value in curve]


def run_a0(weights: list[float]) -> tuple[float, dict[str, object]]:
    utility = CappedUtility(weights)
    detail = fgsv_sequential_ablation(
        utility,
        2,
        [0],
        100,
        np.random.RandomState(20261031),
        10,
        STAGES[0],
    )
    return float(detail["estimate"]), detail


def analytic_parts(weights: list[float]) -> dict[str, float]:
    a, b = weights
    linear = (a + b) / 2
    s1_zero = -b / 4
    s1_one = a / 4
    direct = s1_zero + s1_one
    return {
        "linear_base": linear,
        "s1_0_direct": s1_zero,
        "s1_1_direct": s1_one,
        "released_direct_sum": direct,
        "released_total": linear + direct,
        "equation_8_multiplier": 2.0,
        "equation_8_total": linear + 2 * direct,
        "exact_group_shapley": a,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    before = {str(path.relative_to(ROOT)): sha256(path) for path in HISTORICAL}
    cases = {
        "R2_3_history_input": [1.0, 0.0],
        "R2_4_history_input": [1.0, 4.0],
    }
    rows: list[dict[str, object]] = []
    details: dict[str, object] = {}
    for case, weights in cases.items():
        official, curve = run_official(weights)
        a0, a0_detail = run_a0(weights)
        parts = analytic_parts(weights)
        if abs(official - a0) > 1e-12 or abs(official - parts["released_total"]) > 1e-12:
            raise AssertionError(f"交叉核验失败: {case}")
        for implementation, estimate in (("OFFICIAL_FGSV", official), ("A0_RELEASE_LOGIC_CAPPED", a0)):
            rows.append(
                {
                    "case": case,
                    "weights": json.dumps(weights),
                    "group": "[0]",
                    "n": 2,
                    "threshold": 10,
                    "implementation": implementation,
                    "estimate": estimate,
                    "exact_truth": weights[0],
                    "absolute_error": abs(estimate - weights[0]),
                    **parts,
                }
            )
        details[case] = {
            "weights": weights,
            "official_curve": curve,
            "a0_detail": a0_detail,
            "analytic_parts": parts,
        }
    with (OUT / "cross_implementation_n2.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    after = {str(path.relative_to(ROOT)): sha256(path) for path in HISTORICAL}
    if before != after:
        raise AssertionError("历史 R2/R2-4 结果被修改")
    payload = {
        "status": "HISTORICAL_RESULTS_CONSISTENT_DIFFERENT_INPUT_GAMES",
        "conclusion": "同一官方逻辑对[1,0]返回0.75，对[1,4]返回1.75；差异由补集玩家权重不同造成。",
        "general_released_formula": "estimate = 0.75*a + 0.25*b for n=2, group={0}, additive weights=[a,b]",
        "n2_branch": "s=1<threshold=10, only small-s branch; both hypergeometric strata contain exactly one coalition",
        "sampling_effect": "none: n=2 strata are singleton and the estimate is deterministic",
        "historical_hashes_before": before,
        "historical_hashes_after": after,
        "details": details,
    }
    (OUT / "audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
