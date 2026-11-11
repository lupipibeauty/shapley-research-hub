from __future__ import annotations

import csv
import ctypes
import gc
import hashlib
import json
import math
import platform
import statistics
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aggregate_report_shapley.h5_scale import (  # noqa: E402
    ScaleConfig,
    StateLimitExceeded,
    b0_full_enumeration,
    b2_state_dp,
    b3_leaf_factor,
    b4_type_variable_elimination,
    b5_shared_linear_closed_form,
    exact_efficiency_error,
    generate_instance,
    max_abs_error,
    structural_state_count,
)


OUT = ROOT / "outputs" / "v4_0" / "H5_SCALE_2026_11_01"
SEEDS = (7301, 7302, 7303, 7304, 7305)
TIMING_REPEATS = 3
# This is an explicit experimental resource gate, not a complexity theorem.
# The unoptimized per-player state implementations are only timed below this gate;
# larger exact small-n games still retain B0 truth, and the large shared control
# uses two independent closed-form checks.
STATE_CAP = 5_000
LOCAL_ENUMERATION_CAP = 300_000
CORRECTNESS_TOLERANCE = 1e-9

HISTORICAL = (
    ROOT / "config" / "d1p_design.yaml",
    ROOT / "config" / "value_spec_v3_2.yaml",
    ROOT / "src" / "aggregate_report_shapley" / "d1p.py",
    ROOT / "src" / "aggregate_report_shapley" / "d1p_values.py",
    ROOT / "docs" / "H0_模型与实验设计审计.md",
    ROOT / "docs" / "H5_V2数学结构与充分性证明.md",
    ROOT / "reports" / "H5_V2_JOINT_STATE实验审计报告_2026-10-31.md",
    ROOT / "experiments" / "run_h5_v2_joint_state_2026_10_31.py",
    ROOT / "outputs" / "v4_0" / "H5_V2_JOINT_STATE_2026_10_31" / "summary.json",
    ROOT / "outputs" / "v4_0" / "H5_V2_JOINT_STATE_2026_10_31" / "record_shapley_comparison.csv",
    ROOT / "outputs" / "v4_0" / "H5_V2_JOINT_STATE_2026_10_31" / "family_state_growth.csv",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def historical_hashes() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): sha256(path) for path in HISTORICAL}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"拒绝写入空 CSV: {path}")
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def configs() -> list[ScaleConfig]:
    rows: list[ScaleConfig] = []
    for n in (12, 16, 18, 100, 1000):
        rows.append(
            ScaleConfig(
                config_id=f"G1_N{n}_L4_D4_ORIGINAL_FAMILIES",
                group="G1_PLAYER_SCALE",
                n=n,
                leaves=4,
                dimensions=4,
                profile="balanced_templates",
                family_map=(0, 1, 2, 3),
                score_modes=("v2",),
                exact_payments_expected=n <= 18,
            )
        )
    for leaves in (2, 4, 8):
        rows.append(
            ScaleConfig(
                config_id=f"G2_LEAF_L{leaves}_N16_D4",
                group="G2_LEAF_SCALE",
                n=16,
                leaves=leaves,
                dimensions=4,
                profile="diverse_effective",
                family_map=(0, 1, 2, 3),
                score_modes=("v2",),
                exact_payments_expected=True,
            )
        )
    for dimensions in (2, 4, 6):
        rows.append(
            ScaleConfig(
                config_id=f"G2_ATTRIBUTE_D{dimensions}_N16_L4",
                group="G2_ATTRIBUTE_SCALE",
                n=16,
                leaves=4,
                dimensions=dimensions,
                profile="diverse_effective",
                family_map=tuple(range(dimensions)),
                score_modes=("v2",),
                exact_payments_expected=True,
            )
        )
    shared_specs = {
        "INDEPENDENT": (0, 1, 2, 3),
        "PARTIAL": (0, 0, 2, 3),
        "FULL": (0, 0, 0, 0),
    }
    for label, mapping in shared_specs.items():
        rows.append(
            ScaleConfig(
                config_id=f"G3_SHARE_{label}_N16_L4_D4",
                group="G3_SHARING_AND_SCORE",
                n=16,
                leaves=4,
                dimensions=4,
                profile="balanced_templates",
                family_map=mapping,
                score_modes=("additive", "geometric"),
                exact_payments_expected=True,
            )
        )
    for n in (100, 1000):
        rows.append(
            ScaleConfig(
                config_id=f"G3_SHARE_FULL_N{n}_L4_D4",
                group="G3_SHARED_LARGE_CONTROL",
                n=n,
                leaves=4,
                dimensions=4,
                profile="balanced_templates",
                family_map=(0, 0, 0, 0),
                score_modes=("additive", "geometric"),
                exact_payments_expected=True,
            )
        )
    return rows


def percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def measured(
    call: Callable[[], tuple[list[float], dict[str, int]]],
    *,
    capture_memory: bool,
) -> tuple[list[float], dict[str, int], float, int | str]:
    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    def current_working_set() -> int:
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_process = ctypes.windll.kernel32.GetCurrentProcess
        get_process.restype = ctypes.c_void_p
        handle = get_process()
        get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory.argtypes = [ctypes.c_void_p, ctypes.POINTER(ProcessMemoryCounters), ctypes.c_ulong]
        get_memory.restype = ctypes.c_int
        ok = get_memory(handle, ctypes.byref(counters), counters.cb)
        if not ok:
            raise ctypes.WinError()
        return int(counters.WorkingSetSize)

    gc.collect()
    stop = threading.Event()
    sampled_peak = current_working_set() if capture_memory else 0

    def sample_memory() -> None:
        nonlocal sampled_peak
        while not stop.wait(0.01):
            sampled_peak = max(sampled_peak, current_working_set())

    sampler = threading.Thread(target=sample_memory, daemon=True)
    if capture_memory:
        sampler.start()
    started = time.perf_counter()
    try:
        allocation, diagnostics = call()
    finally:
        wall = time.perf_counter() - started
        if capture_memory:
            sampled_peak = max(sampled_peak, current_working_set())
            stop.set()
            sampler.join()
            peak: int | str = sampled_peak
        else:
            peak = "NA"
    return allocation, diagnostics, wall, peak


def method_callable(method: str, instance, mode: str):
    if method == "B0_FULL_ENUMERATION":
        return lambda: b0_full_enumeration(instance, mode)
    if method == "B2_STATE_DP":
        return lambda: b2_state_dp(instance, mode, state_cap=STATE_CAP)
    if method == "B3_LEAF_FACTOR":
        return lambda: b3_leaf_factor(instance, mode, state_cap=STATE_CAP)
    if method == "B4_TYPE_VARIABLE_ELIMINATION":
        return lambda: b4_type_variable_elimination(instance, mode, state_cap=STATE_CAP)
    if method == "B5_SHARED_LINEAR_CLOSED_FORM":
        return lambda: b5_shared_linear_closed_form(instance, mode)
    if method == "B6_SHARED_SYMMETRY":
        return lambda: ([1.0 / instance.n] * instance.n, {
            "actual_visited_states": 1,
            "unique_value_states": instance.n + 1,
            "intermediate_state_visits": 0,
            "state_transitions": instance.n,
            "maximum_frontier_states": 1,
        })
    raise KeyError(method)


def planned_methods(config: ScaleConfig, structural: dict[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if config.n <= 18:
        rows.append(("B0_FULL_ENUMERATION", "RUN"))
    else:
        rows.append(("B0_FULL_ENUMERATION", "SKIP_N_GT_18"))
    actual = structural["actual_reachable_states"]
    state_feasible = isinstance(actual, int) and actual <= STATE_CAP
    for method in ("B2_STATE_DP", "B3_LEAF_FACTOR", "B4_TYPE_VARIABLE_ELIMINATION"):
        rows.append((method, "RUN" if state_feasible else "SKIP_PREDICTED_STATE_CAP"))
    if set(config.family_map) == {0}:
        rows.extend(
            (
                ("B5_SHARED_LINEAR_CLOSED_FORM", "RUN"),
                ("B6_SHARED_SYMMETRY", "RUN"),
            )
        )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    before = historical_hashes()
    run_started = time.perf_counter()

    matrix_rows: list[dict[str, Any]] = []
    instance_rows: list[dict[str, Any]] = []
    timing_rows: list[dict[str, Any]] = []
    correctness_rows: list[dict[str, Any]] = []
    payment_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    representative: dict[str, tuple[Any, dict[str, Any]]] = {}

    for config in configs():
        matrix_rows.append(
            {
                "config_id": config.config_id,
                "group": config.group,
                "n": config.n,
                "leaf_count_L": config.leaves,
                "base_statistic_dimension_d": config.dimensions,
                "profile": config.profile,
                "family_map": "|".join(map(str, config.family_map)),
                "score_modes": "|".join(config.score_modes),
                "independent_instances": len(SEEDS),
                "timing_repeats_on_representative_instance": TIMING_REPEATS,
                "state_cap": STATE_CAP,
                "historical_D1P_modified": False,
            }
        )
        for instance_index, seed in enumerate(SEEDS):
            tick = time.perf_counter()
            instance = generate_instance(config, seed)
            compile_seconds = time.perf_counter() - tick
            tick = time.perf_counter()
            structural = structural_state_count(instance, enumeration_cap=LOCAL_ENUMERATION_CAP)
            structural_seconds = time.perf_counter() - tick
            type_count = len({(record.leaf, record.increments) for record in instance.records})
            row = {
                "config_id": config.config_id,
                "group": config.group,
                "instance_index": instance_index,
                "seed": seed,
                "n": config.n,
                "leaf_count_L": config.leaves,
                "base_statistic_dimension_d": config.dimensions,
                "raw_increment_type_count": type_count,
                "input_compile_seconds": compile_seconds,
                "structural_preprocess_seconds": structural_seconds,
                **structural,
            }
            instance_rows.append(row)
            if instance_index == 0:
                representative[config.config_id] = (instance, structural)

    # Timed algorithms and correctness use the prespecified first seed only.
    for config in configs():
        instance, structural = representative[config.config_id]
        print(f"RUN {config.config_id}", flush=True)
        plans = planned_methods(config, structural)
        for mode in config.score_modes:
            allocations: dict[str, list[float]] = {}
            diagnostics_by_method: dict[str, dict[str, int]] = {}
            for method, action in plans:
                if action != "RUN":
                    failure_rows.append(
                        {
                            "config_id": config.config_id,
                            "seed": instance.seed,
                            "score_mode": mode,
                            "method": method,
                            "failure_class": action,
                            "detail": f"actual_reachable_states={structural['actual_reachable_states']}; cap={STATE_CAP}",
                            "payment_reported": False,
                        }
                    )
                    timing_rows.append(
                        {
                            "config_id": config.config_id,
                            "score_mode": mode,
                            "method": method,
                            "repeat": "NA",
                            "status": action,
                            "wall_seconds": "NA",
                            "peak_sampled_rss_bytes": "NA",
                        }
                    )
                    continue
                for repeat in range(TIMING_REPEATS):
                    try:
                        allocation, diagnostics, wall, peak = measured(
                            method_callable(method, instance, mode),
                            capture_memory=repeat == 0,
                        )
                        status = "SUCCESS"
                        if repeat == 0:
                            allocations[method] = allocation
                            diagnostics_by_method[method] = diagnostics
                        timing_rows.append(
                            {
                                "config_id": config.config_id,
                                "score_mode": mode,
                                "method": method,
                                "repeat": repeat,
                                "status": status,
                                "wall_seconds": wall,
                                "peak_sampled_rss_bytes": peak,
                                **diagnostics,
                            }
                        )
                    except (StateLimitExceeded, MemoryError) as exc:
                        failure_rows.append(
                            {
                                "config_id": config.config_id,
                                "seed": instance.seed,
                                "score_mode": mode,
                                "method": method,
                                "failure_class": type(exc).__name__,
                                "detail": str(exc),
                                "payment_reported": False,
                            }
                        )
                        timing_rows.append(
                            {
                                "config_id": config.config_id,
                                "score_mode": mode,
                                "method": method,
                                "repeat": repeat,
                                "status": type(exc).__name__,
                                "wall_seconds": "NA",
                                "peak_sampled_rss_bytes": "NA",
                            }
                        )
                        break

            truth_method = None
            if "B0_FULL_ENUMERATION" in allocations:
                truth_method = "B0_FULL_ENUMERATION"
            elif "B6_SHARED_SYMMETRY" in allocations:
                truth_method = "B6_SHARED_SYMMETRY"
            elif "B5_SHARED_LINEAR_CLOSED_FORM" in allocations:
                truth_method = "B5_SHARED_LINEAR_CLOSED_FORM"

            for method, allocation in allocations.items():
                error = max_abs_error(allocation, allocations[truth_method]) if truth_method else math.nan
                efficiency = exact_efficiency_error(instance, mode, allocation)
                passes = error <= CORRECTNESS_TOLERANCE and efficiency <= CORRECTNESS_TOLERANCE
                correctness_rows.append(
                    {
                        "config_id": config.config_id,
                        "seed": instance.seed,
                        "score_mode": mode,
                        "method": method,
                        "truth_method": truth_method or "NONE",
                        "max_player_abs_error": error,
                        "efficiency_abs_error": efficiency,
                        "passes_1e_9": passes,
                        "player_count": instance.n,
                        **diagnostics_by_method[method],
                    }
                )
                if passes:
                    for player, value in enumerate(allocation):
                        payment_rows.append(
                            {
                                "config_id": config.config_id,
                                "seed": instance.seed,
                                "score_mode": mode,
                                "method": method,
                                "player": f"p{player + 1}",
                                "shapley": value,
                                "truth": allocations[truth_method][player] if truth_method else "NA",
                                "absolute_error": abs(value - allocations[truth_method][player]) if truth_method else "NA",
                            }
                        )
                elif config.exact_payments_expected:
                    failure_rows.append(
                        {
                            "config_id": config.config_id,
                            "seed": instance.seed,
                            "score_mode": mode,
                            "method": method,
                            "failure_class": "CORRECTNESS_GATE_FAILED",
                            "detail": f"max_error={error}; efficiency={efficiency}",
                            "payment_reported": False,
                        }
                    )

    # Structural summaries across five independent generated instances.
    state_summary_rows: list[dict[str, Any]] = []
    grouped_instances: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in instance_rows:
        grouped_instances[row["config_id"]].append(row)
    for config_id, rows in grouped_instances.items():
        exact_counts = [float(row["actual_reachable_states"]) for row in rows if row["actual_reachable_states"] != "NA"]
        ratios = [float(row["states_per_coalition"]) for row in rows if not math.isnan(float(row["states_per_coalition"]))]
        types = [float(row["raw_increment_type_count"]) for row in rows]
        state_summary_rows.append(
            {
                "config_id": config_id,
                "independent_instance_count": len(rows),
                "exact_state_count_instances": len(exact_counts),
                "reachable_states_median": statistics.median(exact_counts) if exact_counts else "NA",
                "reachable_states_q1": percentile(exact_counts, 0.25) if exact_counts else "NA",
                "reachable_states_q3": percentile(exact_counts, 0.75) if exact_counts else "NA",
                "reachable_states_iqr": percentile(exact_counts, 0.75) - percentile(exact_counts, 0.25) if exact_counts else "NA",
                "states_per_coalition_median": statistics.median(ratios) if ratios else "NA",
                "states_per_coalition_q1": percentile(ratios, 0.25) if ratios else "NA",
                "states_per_coalition_q3": percentile(ratios, 0.75) if ratios else "NA",
                "raw_type_count_median": statistics.median(types),
                "raw_type_count_iqr": percentile(types, 0.75) - percentile(types, 0.25),
            }
        )

    # Timing summaries across three repeated runs on the representative instance.
    performance_rows: list[dict[str, Any]] = []
    grouped_timings: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in timing_rows:
        grouped_timings[(row["config_id"], row["score_mode"], row["method"])].append(row)
    for (config_id, mode, method), rows in grouped_timings.items():
        successful = [row for row in rows if row["status"] == "SUCCESS"]
        walls = [float(row["wall_seconds"]) for row in successful]
        peaks = [float(row["peak_sampled_rss_bytes"]) for row in successful if row["peak_sampled_rss_bytes"] != "NA"]
        performance_rows.append(
            {
                "config_id": config_id,
                "score_mode": mode,
                "method": method,
                "planned_repeats": TIMING_REPEATS,
                "successful_repeats": len(successful),
                "failure_count": len(rows) - len(successful),
                "wall_median_seconds": statistics.median(walls) if walls else "NA",
                "wall_q1_seconds": percentile(walls, 0.25) if walls else "NA",
                "wall_q3_seconds": percentile(walls, 0.75) if walls else "NA",
                "wall_iqr_seconds": percentile(walls, 0.75) - percentile(walls, 0.25) if walls else "NA",
                "peak_memory_first_run_bytes": peaks[0] if peaks else "NA",
                "peak_memory_measurement_repeats": len(peaks),
                "peak_memory_method": "Windows process working-set sampling at 10 ms",
                "status": "SUCCESS" if len(successful) == TIMING_REPEATS else rows[0]["status"],
                "timing_unit": "same_representative_instance_repeated_run",
            }
        )

    write_csv(OUT / "experiment_matrix.csv", matrix_rows)
    write_csv(OUT / "instance_structural_metrics.csv", instance_rows)
    write_csv(OUT / "state_growth_summary.csv", state_summary_rows)
    write_csv(OUT / "raw_timings.csv", timing_rows)
    write_csv(OUT / "performance_summary.csv", performance_rows)
    write_csv(OUT / "correctness_audit.csv", correctness_rows)
    write_csv(OUT / "record_shapley_verified.csv", payment_rows)
    write_csv(OUT / "failures.csv", failure_rows)

    after = historical_hashes()
    if before != after:
        raise AssertionError("历史 H5/D1-P 文件哈希发生变化")
    write_json(OUT / "historical_hashes.json", {"before": before, "after": after, "unchanged": True})
    summary = {
        "status": "H5_SCALE_COMPLETED_AND_PAUSED",
        "config_count": len(configs()),
        "instances_per_config": len(SEEDS),
        "total_generated_instances": len(instance_rows),
        "timing_repeats": TIMING_REPEATS,
        "state_cap": STATE_CAP,
        "correctness_tolerance": CORRECTNESS_TOLERANCE,
        "correctness_rows": len(correctness_rows),
        "all_reported_payments_verified": all(row["passes_1e_9"] for row in correctness_rows),
        "failure_rows": len(failure_rows),
        "historical_files_unchanged": True,
        "total_wall_seconds": time.perf_counter() - run_started,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "statistical_scope": "five independent generated instances summarize structural variability; three timing repeats on the prespecified first seed summarize runtime noise; no significance tests",
    }
    write_json(OUT / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
