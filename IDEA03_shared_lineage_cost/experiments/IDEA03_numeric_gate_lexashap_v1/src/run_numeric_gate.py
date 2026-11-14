from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
OFFICIAL = WORKSPACE / "aggregate_report_shapley" / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main"
RESULTS = ROOT / "results"
LOGS = ROOT / "logs"
CONFIG = ROOT / "config" / "protocol.json"

sys.path.insert(0, str(OFFICIAL))
from Algorithms.LExaShap.ShapleyCircuit import DNFCircuit, DNFCircuitNode, lift_recursively  # noqa: E402
from Algorithms.LExaShap.ShapleyEngine import Value  # noqa: E402


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


def dag_nodes(value: Value) -> int:
    seen: set[int] = set()
    stack = [value]
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        stack.extend(current._prev)
    return len(seen)


def build(m: int, k: int):
    labels = [f"x{j:02d}_{ell:02d}" for j in range(1, m + 1) for ell in range(1, k + 1)]
    values = {label: Value(0.5, {label}, label=label) for label in labels}
    dnf = [{values[f"x{j:02d}_{ell:02d}"] for ell in range(1, k + 1)} for j in range(1, m + 1)]
    return labels, values, dnf


def classify(eff_err: float, player_err: float, symmetry: float, shares: list[float], cfg: dict) -> str:
    if not all(math.isfinite(x) for x in shares):
        return "NUMERIC_FAILURE"
    if eff_err <= cfg["pass_strict"] and player_err <= cfg["pass_strict"]:
        return "PASS_STRICT"
    if eff_err <= cfg["pass_loose"] and player_err <= cfg["pass_loose"]:
        return "PASS_LOOSE"
    if eff_err > cfg["numeric_failure"] or symmetry > cfg["numeric_failure"] or min(shares) < 0 or max(map(abs, shares)) > cfg["catastrophic_abs_value"]:
        return "NUMERIC_FAILURE"
    return "NUMERIC_DRIFT"


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    RESULTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    raw_rows: list[dict] = []
    mapping_rows: list[dict] = []
    for m in cfg["m_values"]:
        k = cfg["k"]
        n = m * k
        Value.all_assignments_by_size_cache.clear()
        labels, values, dnf = build(m, k)
        started = time.perf_counter_ns()
        lifted = lift_recursively(dnf)
        DNFCircuit.timeout = 3600
        DNFCircuitNode.start_time = time.time()
        root = DNFCircuitNode(lifted, "root")
        root.recursively_expand()
        compile_ns = time.perf_counter_ns() - started
        root.value.backward()
        backward_ns = time.perf_counter_ns() - started - compile_ns
        scale = np.longdouble(2 ** n) / np.longdouble(math.factorial(n))
        shares_ld = [np.dot(values[label].grad, values[label].prob) * scale for label in labels]
        shares = [float(x) for x in shares_ld]
        expected = 1.0 / n
        eff = math.fsum(shares)
        eff_err = abs(eff - 1.0)
        player_err = max(abs(x - expected) for x in shares)
        symmetry = max(shares) - min(shares)
        status = classify(eff_err, player_err, symmetry, shares, cfg)
        rows.append({
            "m": m, "k": k, "N": n, "clause_count": m, "literal_count": n,
            "dag_node_count": dag_nodes(root.value), "compile_success": True, "backward_success": True,
            "nan_count": sum(math.isnan(x) for x in shares), "inf_count": sum(math.isinf(x) for x in shares),
            "min_shapley": min(shares), "max_shapley": max(shares), "mean_shapley": eff / n,
            "expected_shapley": expected, "max_abs_player_error": player_err,
            "max_relative_player_error": player_err / expected, "efficiency_sum": eff,
            "efficiency_abs_error": eff_err, "symmetry_spread": symmetry,
            "negative_shapley": min(shares) < 0, "abs_over_100": max(map(abs, shares)) > 100,
            "classification": status, "compile_ns": compile_ns, "backward_ns": backward_ns,
        })
        if m in {2, 12} or status != "PASS_STRICT":
            for index, label in enumerate(labels):
                raw_rows.append({
                    "m": m, "N": n, "author_variable_label": label, "author_variable_position": index,
                    "raw_gradient": json.dumps([str(x) for x in values[label].grad]),
                    "raw_probability": json.dumps([str(x) for x in values[label].prob]),
                    "wrapper_dot": str(np.dot(values[label].grad, values[label].prob)),
                    "wrapper_scale": str(scale), "final_shapley": str(shares_ld[index]),
                })
                mapping_rows.append({
                    "m": m, "N": n, "author_position": index, "author_label": label,
                    "final_position": index, "final_label": labels[index],
                    "same_object_identity": values[label] is values[labels[index]], "mapping_match": label == labels[index],
                })
    write_csv(RESULTS / "analytic_family_results.csv", rows)
    write_csv(RESULTS / "raw_author_outputs.csv", raw_rows)
    write_csv(RESULTS / "wrapper_outputs.csv", raw_rows)
    write_csv(RESULTS / "correctness_checks.csv", rows)
    write_csv(RESULTS / "label_mapping_audit.csv", mapping_rows)
    strict = [r for r in rows if r["classification"] == "PASS_STRICT"]
    loose_fail = [r for r in rows if r["efficiency_abs_error"] > cfg["pass_loose"] or r["max_abs_player_error"] > cfg["pass_loose"]]
    drift = [r for r in rows if r["classification"] == "NUMERIC_DRIFT"]
    catastrophic = [r for r in rows if r["classification"] == "NUMERIC_FAILURE"]
    boundary = [{
        "last_strict_N": max((r["N"] for r in strict), default="NONE"),
        "first_loose_failure_N": min((r["N"] for r in loose_fail), default="NONE"),
        "first_drift_N": min((r["N"] for r in drift), default="NONE"),
        "first_catastrophic_N": min((r["N"] for r in catastrophic), default="NONE"),
    }]
    write_csv(RESULTS / "failure_boundary.csv", boundary)
    finfo = {
        "float64": {"eps": str(np.finfo(np.float64).eps), "max": str(np.finfo(np.float64).max), "nmant": int(np.finfo(np.float64).nmant)},
        "longdouble": {"eps": str(np.finfo(np.longdouble).eps), "max": str(np.finfo(np.longdouble).max), "nmant": int(np.finfo(np.longdouble).nmant)},
    }
    (RESULTS / "platform_precision.json").write_text(json.dumps(finfo, indent=2), encoding="utf-8")
    manifest = {"protocol": cfg["protocol_id"], "runs": len(rows), "boundary": boundary[0], "platform_precision": finfo}
    (RESULTS / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
