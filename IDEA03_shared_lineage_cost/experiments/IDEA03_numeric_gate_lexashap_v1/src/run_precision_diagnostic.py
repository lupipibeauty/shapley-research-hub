from __future__ import annotations

import csv
import json
import math
import sys
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
OFFICIAL = WORKSPACE / "aggregate_report_shapley" / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main"
RESULTS = ROOT / "results"
sys.path.insert(0, str(OFFICIAL))

from Algorithms.LExaShap.Helper_functions import deconvolve as author_deconvolve  # noqa: E402


def conv(left, right):
    out = [left[0] * 0 for _ in range(len(left) + len(right) - 1)]
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            out[i + j] += a * b
    return out


def power(base, exponent):
    out = [base[0] * 0 + 1]
    for _ in range(exponent):
        out = conv(out, base)
    return out


def polynomial_division_descending(output, denominator):
    # Mirrors scipy.signal.deconvolve's descending-coefficient convention.
    work = list(output)
    quotient_len = len(output) - len(denominator) + 1
    quotient = [output[0] * 0 for _ in range(quotient_len)]
    for i in range(quotient_len):
        q = work[i] / denominator[0]
        quotient[i] = q
        for j, d in enumerate(denominator):
            work[i + j] -= q * d
    return quotient


def decimal_share(m: int, k: int, precision: int) -> tuple[Decimal, dict]:
    with localcontext() as ctx:
        ctx.prec = precision
        two = Decimal(2)
        denom = two ** k
        all_clause = [Decimal(math.comb(k, i)) / denom for i in range(k + 1)]
        clause_true = [Decimal(0)] * k + [Decimal(1) / denom]
        unsat_clause = [a - b for a, b in zip(all_clause, clause_true)]
        unsat_root = power(unsat_clause, m)
        quotient = polynomial_division_descending(unsat_root, unsat_clause)
        expected_quotient = power(unsat_clause, m - 1)
        n = m * k
        root_grad = [Decimal(0)] + [Decimal(math.factorial(i) * math.factorial(n - i - 1)) for i in range(n)]
        clause_grad = []
        for shift in range(k + 1):
            clause_grad.append(sum((q * root_grad[shift + j] for j, q in enumerate(quotient)), Decimal(0)))
        leaf_dot = clause_grad[k] / (two ** k)
        scale = (two ** n) / Decimal(math.factorial(n))
        share = leaf_dot * scale
        qerr = max(abs(a - b) for a, b in zip(quotient, expected_quotient))
        return +share, {
            "quotient_max_abs_error": +qerr,
            "quotient_max_abs": +max(abs(x) for x in quotient),
            "root_grad_max_abs": +max(abs(x) for x in root_grad),
            "clause_grad_max_abs": +max(abs(x) for x in clause_grad),
            "leaf_dot": +leaf_dot,
            "scale": +scale,
        }


def float_trace(m: int, k: int) -> dict:
    denom = np.longdouble(2 ** k)
    all_clause = np.array([math.comb(k, i) for i in range(k + 1)], dtype=np.longdouble) / denom
    clause_true = np.array([0] * k + [1], dtype=np.longdouble) / denom
    u = all_clause - clause_true
    root = np.array(power(list(u), m), dtype=np.longdouble)
    observed = np.array(author_deconvolve(root, u), dtype=np.longdouble)
    expected = np.array(power(list(u), m - 1), dtype=np.longdouble)
    work = root.copy()
    manual = np.zeros(len(root) - len(u) + 1, dtype=np.longdouble)
    max_finite_cancellation = np.longdouble(0)
    exact_cancellation_updates = 0
    for i in range(len(manual)):
        q = work[i] / u[0]
        manual[i] = q
        for j, coefficient in enumerate(u):
            before = work[i + j]
            term = q * coefficient
            after = before - term
            numerator = abs(before) + abs(term)
            if after == 0 and numerator != 0:
                exact_cancellation_updates += 1
            elif after != 0:
                max_finite_cancellation = max(max_finite_cancellation, numerator / abs(after))
            work[i + j] = after
    diff = observed - expected
    n = m * k
    root_grad = np.array([0] + [math.factorial(i) * math.factorial(n - i - 1) for i in range(n)], dtype=np.longdouble)
    clause_grad_observed = np.array([np.dot(np.pad(observed, (i, len(root_grad) - i - len(observed))), root_grad) for i in range(k + 1)], dtype=np.longdouble)
    clause_grad_expected = np.array([np.dot(np.pad(expected, (i, len(root_grad) - i - len(expected))), root_grad) for i in range(k + 1)], dtype=np.longdouble)
    return {
        "m": m, "N": n, "stage": "ROOT_N_ADD_DECONVOLUTION",
        "quotient_max_abs_error": str(np.max(np.abs(diff))),
        "quotient_l1_error": str(np.sum(np.abs(diff))),
        "quotient_expected_max_abs": str(np.max(np.abs(expected))),
        "root_gradient_max_abs": str(np.max(np.abs(root_grad))),
        "clause_gradient_observed_max_abs": str(np.max(np.abs(clause_grad_observed))),
        "clause_gradient_expected_max_abs": str(np.max(np.abs(clause_grad_expected))),
        "clause_gradient_max_abs_error": str(np.max(np.abs(clause_grad_observed - clause_grad_expected))),
        "first_bad_quotient_index": next((i for i, x in enumerate(diff) if x != 0), "NONE"),
        "manual_vs_scipy_quotient_max_abs_error": str(np.max(np.abs(manual - observed))),
        "max_finite_subtractive_cancellation_ratio": str(max_finite_cancellation),
        "exact_cancellation_updates": exact_cancellation_updates,
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    precision_rows = []
    for m in range(1, 21):
        n = 5 * m
        for precision in (50, 100):
            share, trace = decimal_share(m, 5, precision)
            expected = Decimal(1) / Decimal(n)
            precision_rows.append({
                "family": "DISJOINT", "m": m, "k": 5, "N": n,
                "implementation": "SAME_RECURRENCE_DECIMAL_DIAGNOSTIC", "decimal_digits": precision,
                "share": str(share), "expected_share": str(expected),
                "abs_player_error": str(abs(share - expected)),
                "efficiency_sum": str(share * Decimal(n)),
                "efficiency_abs_error": str(abs(share * Decimal(n) - Decimal(1))),
                **{key: str(value) for key, value in trace.items()},
            })
    trace_rows = [float_trace(11, 5), float_trace(12, 5)]
    write_csv(RESULTS / "precision_comparison.csv", precision_rows)
    write_csv(RESULTS / "numeric_trace.csv", trace_rows)
    (RESULTS / "precision_diagnostic_manifest.json").write_text(json.dumps({
        "mpmath": "UNAVAILABLE_NOT_INSTALLED",
        "numpy_longdouble_extra_precision": False,
        "decimal_precisions": [50, 100],
        "algorithm_change": "NONE; same convolution/polynomial-division/gradient recurrence",
        "scope": "HIGH_PRECISION_DIAGNOSTIC_ONLY",
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
