from __future__ import annotations

import csv
import json
import math
import sys
import time
from dataclasses import dataclass
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
OFFICIAL = WORKSPACE / "aggregate_report_shapley" / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main"
RESULTS = ROOT / "results"
CONFIG = ROOT / "config" / "protocol.json"
sys.path.insert(0, str(OFFICIAL))

from Algorithms.LExaShap.Helper_functions import deconvolve as author_deconvolve  # noqa: E402


def write_csv(path: Path, rows: list[dict]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def decimal_conv(left: list[Decimal], right: list[Decimal]) -> list[Decimal]:
    out = [Decimal(0)] * (len(left) + len(right) - 1)
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            out[i + j] += a * b
    return out


def decimal_power(base: list[Decimal], exponent: int) -> list[Decimal]:
    out = [Decimal(1)]
    for _ in range(exponent):
        out = decimal_conv(out, base)
    return out


def disjoint_q(k: int, dtype=float) -> np.ndarray:
    denom = dtype(2 ** k)
    all_assignments = np.array([math.comb(k, i) for i in range(k + 1)], dtype=dtype) / denom
    satisfied = np.array([0] * k + [1], dtype=dtype) / denom
    return all_assignments - satisfied


@dataclass
class Counters:
    convolutions: int = 0
    deconvolutions: int = 0
    convolution_cell_products: int = 0
    deconvolution_cell_updates: int = 0
    generated_cells: int = 0


def conv(left: np.ndarray, right: np.ndarray, counters: Counters) -> np.ndarray:
    if len(left) == 1 and left[0] == 1:
        return right.copy()
    if len(right) == 1 and right[0] == 1:
        return left.copy()
    counters.convolutions += 1
    counters.convolution_cell_products += len(left) * len(right)
    out = np.convolve(left, right)
    counters.generated_cells += len(out)
    return out


def sequential_product(items: list[np.ndarray], counters: Counters) -> np.ndarray:
    out = np.array([1.0])
    for item in items:
        out = conv(out, item, counters)
    return out


def current_deconvolution(items: list[np.ndarray]) -> tuple[list[np.ndarray], Counters, dict]:
    counters = Counters()
    total = sequential_product(items, counters)
    outputs = []
    max_cancel = 1.0
    for item in items:
        counters.deconvolutions += 1
        quotient_len = len(total) - len(np.trim_zeros(item, "f")) + 1
        counters.deconvolution_cell_updates += quotient_len * len(np.trim_zeros(item, "f"))
        quotient = np.asarray(author_deconvolve(total, item), dtype=float)
        counters.generated_cells += len(quotient)
        outputs.append(quotient)
        work = total.copy()
        denominator = np.trim_zeros(item, "f")
        for i in range(quotient_len):
            q = work[i] / denominator[0]
            for j, coefficient in enumerate(denominator):
                before = work[i + j]
                term = q * coefficient
                after = before - term
                if after != 0:
                    max_cancel = max(max_cancel, (abs(before) + abs(term)) / abs(after))
                work[i + j] = after
    storage = {
        "cached_intermediate_cells": len(total),
        "peak_working_cells_estimate": len(total) + max(map(len, outputs)),
        "returned_message_cells": sum(map(len, outputs)),
        "max_cancellation_ratio": max_cancel,
    }
    return outputs, counters, storage


def prefix_suffix(items: list[np.ndarray]) -> tuple[list[np.ndarray], Counters, dict]:
    counters = Counters()
    r = len(items)
    prefixes = [np.array([1.0])]
    for item in items:
        prefixes.append(conv(prefixes[-1], item, counters))
    suffixes: list[np.ndarray] = [np.array([1.0]) for _ in range(r + 1)]
    for i in range(r - 1, -1, -1):
        suffixes[i] = conv(items[i], suffixes[i + 1], counters)
    outputs = [conv(prefixes[i], suffixes[i + 1], counters) for i in range(r)]
    cached = sum(map(len, prefixes)) + sum(map(len, suffixes))
    storage = {
        "cached_intermediate_cells": cached,
        "peak_working_cells_estimate": cached + max(map(len, outputs)),
        "returned_message_cells": sum(map(len, outputs)),
        "max_cancellation_ratio": 1.0,
    }
    return outputs, counters, storage


@dataclass
class ProductNode:
    start: int
    end: int
    product: np.ndarray
    left: "ProductNode | None" = None
    right: "ProductNode | None" = None


def product_tree(items: list[np.ndarray]) -> tuple[list[np.ndarray], Counters, dict]:
    counters = Counters()

    def build(start: int, end: int) -> ProductNode:
        if end - start == 1:
            return ProductNode(start, end, items[start])
        middle = (start + end) // 2
        left = build(start, middle)
        right = build(middle, end)
        return ProductNode(start, end, conv(left.product, right.product, counters), left, right)

    root = build(0, len(items))
    outputs: list[np.ndarray | None] = [None] * len(items)
    max_path_cells = 0

    def descend(node: ProductNode, outside: np.ndarray, path_cells: int) -> None:
        nonlocal max_path_cells
        max_path_cells = max(max_path_cells, path_cells + len(outside))
        if node.left is None or node.right is None:
            outputs[node.start] = outside
            return
        left_outside = conv(outside, node.right.product, counters)
        descend(node.left, left_outside, path_cells + len(left_outside))
        right_outside = conv(outside, node.left.product, counters)
        descend(node.right, right_outside, path_cells + len(right_outside))

    descend(root, np.array([1.0]), 0)
    final = [item for item in outputs if item is not None]

    def cached_cells(node: ProductNode) -> int:
        return len(node.product) + (cached_cells(node.left) if node.left else 0) + (cached_cells(node.right) if node.right else 0)

    cached = cached_cells(root)
    storage = {
        "cached_intermediate_cells": cached,
        "peak_working_cells_estimate": cached + max_path_cells,
        "returned_message_cells": sum(map(len, final)),
        "max_cancellation_ratio": 1.0,
    }
    return final, counters, storage


METHODS = {
    "CURRENT_DECONVOLUTION": current_deconvolution,
    "PREFIX_SUFFIX": prefix_suffix,
    "PRODUCT_TREE": product_tree,
}


def child_gradient(message: np.ndarray, root_grad: np.ndarray, child_degree: int) -> np.ndarray:
    return np.array([
        np.dot(np.pad(message, (shift, len(root_grad) - shift - len(message))), root_grad)
        for shift in range(child_degree + 1)
    ])


def decimal_oracle(m: int, k: int) -> tuple[list[Decimal], list[Decimal], Decimal]:
    with localcontext() as ctx:
        ctx.prec = 100
        denom = Decimal(2) ** k
        q = [Decimal(math.comb(k, i)) / denom for i in range(k + 1)]
        q[-1] -= Decimal(1) / denom
        message = decimal_power(q, m - 1)
        n = m * k
        root_grad = [Decimal(0)] + [Decimal(math.factorial(i) * math.factorial(n - i - 1)) for i in range(n)]
        grad = [sum((value * root_grad[shift + j] for j, value in enumerate(message)), Decimal(0)) for shift in range(k + 1)]
        share = grad[k] / (Decimal(2) ** k) * (Decimal(2) ** n) / Decimal(math.factorial(n))
        return message, grad, +share


def numeric_summary(vector: np.ndarray) -> dict:
    nonzero = np.abs(vector[np.nonzero(vector)])
    max_abs = float(np.max(np.abs(vector))) if len(vector) else 0.0
    min_nonzero = float(np.min(nonzero)) if len(nonzero) else 0.0
    return {
        "max_abs_value": max_abs,
        "min_nonzero_abs_value": min_nonzero,
        "dynamic_range": max_abs / min_nonzero if min_nonzero else math.inf,
    }


def run_correctness(cfg: dict) -> tuple[list[dict], list[dict], list[dict]]:
    correctness = []
    intermediates = []
    failure = []
    for case in cfg["correctness_cases"]:
        m, k = case["m"], case["k"]
        n = m * k
        q = disjoint_q(k)
        items = [q.copy() for _ in range(m)]
        oracle_message_dec, oracle_grad_dec, oracle_share_dec = decimal_oracle(m, k)
        oracle_message = np.array([float(x) for x in oracle_message_dec])
        oracle_grad = np.array([float(x) for x in oracle_grad_dec])
        root_grad = np.array([0] + [math.factorial(i) * math.factorial(n - i - 1) for i in range(n)], dtype=float)
        scale = float((Decimal(2) ** n) / Decimal(math.factorial(n)))
        expected = 1.0 / n
        for method_name, method in METHODS.items():
            started = time.perf_counter_ns()
            messages, counters, storage = method(items)
            elapsed = time.perf_counter_ns() - started
            grads = [child_gradient(message, root_grad, k) for message in messages]
            shares = [float(grad[k] / (2 ** k) * scale) for grad in grads for _ in range(k)]
            message_error = max(float(np.max(np.abs(message - oracle_message))) for message in messages)
            grad_error = max(float(np.max(np.abs(grad - oracle_grad))) for grad in grads)
            grad_relative = grad_error / float(np.max(np.abs(oracle_grad)))
            efficiency = math.fsum(shares)
            symmetry = max(shares) - min(shares)
            max_player_error = max(abs(share - expected) for share in shares)
            passed = max_player_error <= cfg["strict_tolerance"] and abs(efficiency - 1.0) <= cfg["strict_tolerance"] and symmetry <= cfg["strict_tolerance"]
            row = {
                "method": method_name, "m": m, "k": k, "N": n,
                "backward_vector_max_abs_error": grad_error,
                "backward_vector_max_relative_error": grad_relative,
                "sibling_message_max_abs_error": message_error,
                "expected_player_shapley": expected,
                "observed_min_shapley": min(shares), "observed_max_shapley": max(shares),
                "max_abs_player_error": max_player_error, "efficiency_sum": efficiency,
                "efficiency_abs_error": abs(efficiency - 1.0), "symmetry_spread": symmetry,
                "strict_pass": passed, "runtime_ns_auxiliary": elapsed,
                "oracle_share_decimal100": str(oracle_share_dec),
            }
            correctness.append(row)
            summary = numeric_summary(np.concatenate(messages))
            intermediates.append({
                "method": method_name, "m": m, "N": n,
                **summary, "max_cancellation_ratio": storage["max_cancellation_ratio"],
                "convolutions": counters.convolutions, "deconvolutions": counters.deconvolutions,
                "convolution_cell_products": counters.convolution_cell_products,
                "deconvolution_cell_updates": counters.deconvolution_cell_updates,
                "maximum_intermediate_error": message_error,
                "cached_intermediate_cells": storage["cached_intermediate_cells"],
                "peak_working_cells_estimate": storage["peak_working_cells_estimate"],
                "returned_message_cells": storage["returned_message_cells"],
            })
            if n == 60:
                failure.append({**row, "status": "STABLE_ALTERNATIVE_CONFIRMED_ON_FAILURE_CASE" if passed and method_name != "CURRENT_DECONVOLUTION" else ("EXPECTED_BASELINE_FAILURE" if not passed else "PASS")})
    return correctness, intermediates, failure


def cost_polynomials(r: int, total_degree: int) -> list[np.ndarray]:
    degree = total_degree // r
    base = np.array([math.comb(degree, i) for i in range(degree + 1)], dtype=float) / (2 ** degree)
    return [base.copy() for _ in range(r)]


def run_cost(cfg: dict) -> tuple[list[dict], list[dict]]:
    operations = []
    storage_rows = []
    for r in cfg["cost_child_counts"]:
        items = cost_polynomials(r, cfg["cost_total_degree"])
        for method_name, method in METHODS.items():
            started = time.perf_counter_ns()
            outputs, counters, storage = method(items)
            elapsed = time.perf_counter_ns() - started
            operations.append({
                "method": method_name, "child_count": r, "total_degree": cfg["cost_total_degree"],
                "child_degree": cfg["cost_total_degree"] // r,
                "convolutions": counters.convolutions, "deconvolutions": counters.deconvolutions,
                "convolution_cell_products": counters.convolution_cell_products,
                "deconvolution_cell_updates": counters.deconvolution_cell_updates,
                "total_primary_cell_operations": counters.convolution_cell_products + counters.deconvolution_cell_updates,
                "generated_cells": counters.generated_cells, "runtime_ns_auxiliary": elapsed,
                "output_count": len(outputs),
            })
            storage_rows.append({
                "method": method_name, "child_count": r, "total_degree": cfg["cost_total_degree"],
                **storage,
            })
    return operations, storage_rows


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    correctness, intermediates, failure = run_correctness(cfg)
    operations, storage = run_cost(cfg)
    write_csv(RESULTS / "method_correctness.csv", correctness)
    write_csv(RESULTS / "intermediate_numeric_metrics.csv", intermediates)
    write_csv(RESULTS / "failure_case_comparison.csv", failure)
    write_csv(RESULTS / "operation_counts.csv", operations)
    write_csv(RESULTS / "storage_metrics.csv", storage)
    (RESULTS / "run_manifest.json").write_text(json.dumps({
        "protocol": cfg["protocol_id"],
        "diagnostic_alternative_only": True,
        "correctness_rows": len(correctness),
        "cost_rows": len(operations),
        "author_source_modified": False,
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
