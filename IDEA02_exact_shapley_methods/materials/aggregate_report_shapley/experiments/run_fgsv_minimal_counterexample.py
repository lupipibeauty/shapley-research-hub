from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "external" / "fgsv" / "source" / "Faithful_GSV-main" / "exp1_benchmark"
sys.path.insert(0, str(OFFICIAL))

from estimators import FGSV  # noqa: E402


def utility(selection, *_ignored) -> float:
    weights = np.asarray([1.0, 0.0])
    indexes = np.asarray(selection, dtype=int)
    return float(weights[indexes].sum()) if indexes.size else 0.0


def main() -> None:
    np.random.seed(0)
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
    exact = 1.0
    official_result = float(curve[-1])
    # n=2, s=1, s0=1: linear=1/2 and the direct term in released code is 1/4.
    # Equation (8) multiplies that direct expectation by n/[s(n-s)]=2, giving 1/2.
    result = {
        "status": "CONFIRMED_MINIMAL_COUNTEREXAMPLE",
        "official_source_modified": False,
        "n": 2,
        "group": [0],
        "weights": [1.0, 0.0],
        "utility": "U(S)=sum_{i in S} weights[i]",
        "exact_faithful_group_shapley": exact,
        "official_code_final_estimate": official_result,
        "absolute_error": abs(official_result - exact),
        "released_code_linear_term": 0.5,
        "released_code_direct_term": 0.25,
        "paper_equation_8_multiplier": 2.0,
        "paper_equation_8_corrected_direct_term": 0.5,
        "paper_equation_8_total": 1.0,
        "curve": curve.tolist(),
        "source_location": "exp1_benchmark/estimators.py:361-370",
        "source_sha256": hashlib.sha256((OFFICIAL / "estimators.py").read_bytes()).hexdigest(),
        "interpretation": (
            "The direct small-s branch omits n/[s(n-s)]. The n=2 additive game is deterministic, "
            "so the 0.25 error is implementation bias rather than Monte Carlo variance."
        ),
    }
    output = ROOT / "outputs" / "v4_0" / "R2" / "minimal_counterexample.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    assert abs(official_result - 0.75) < 1e-12
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
