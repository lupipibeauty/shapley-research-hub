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
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from aggregate_report_shapley.d1p import D1PState, load_d1p_spec, state_for_mask  # noqa: E402
from aggregate_report_shapley.d1p_values import D1PValueSuite  # noqa: E402
from aggregate_report_shapley.h5_scale import (  # noqa: E402
    ScaleConfig,
    generate_instance,
    make_value_function,
    record_delta as scale_record_delta,
)
from aggregate_report_shapley.h5_shared import (  # noqa: E402
    S3SharedForward,
    S4PrefixSuffix,
    S5TypeMultiOutput,
    S6ReverseMultilinearAD,
    SharedStateLimitExceeded,
    StateGame,
    add_state,
    efficiency_error,
    exact_b0,
    max_abs_error,
    s0_per_focus_b2,
    s1_per_focus_b3,
    s2_per_focus_b4,
)


OUT = ROOT / "outputs" / "v4_0" / "H5_R_2026_11_01"
CONFIG = ROOT / "config" / "d1p_design.yaml"
VALUE_CONFIG = ROOT / "config" / "value_spec_v3_2.yaml"
HISTORICAL_TRUTH = ROOT / "outputs" / "v4_0" / "R2_3" / "exact_targets.json"
LEAVES = ("A1", "A2", "B1", "B2")
FAMILY_ORDER = ("P", "E", "J", "M")
CAP_TIERS = (5_000, 10_000, 25_000)
TIMING_REPEATS = 3
TOLERANCE = 1e-9

HISTORICAL_FILES = (
    CONFIG,
    VALUE_CONFIG,
    ROOT / "src" / "aggregate_report_shapley" / "d1p.py",
    ROOT / "src" / "aggregate_report_shapley" / "d1p_values.py",
    ROOT / "src" / "aggregate_report_shapley" / "h5_scale.py",
    ROOT / "experiments" / "run_h5_v2_joint_state_2026_10_31.py",
    ROOT / "experiments" / "run_h5_scale_2026_11_01.py",
    ROOT / "reports" / "H5_V2_JOINT_STATE实验审计报告_2026-10-31.md",
    ROOT / "reports" / "H5_SCALE联合状态与规模结构审计报告_2026-11-01.md",
    ROOT / "outputs" / "v4_0" / "H5_V2_JOINT_STATE_2026_10_31" / "summary.json",
    ROOT / "outputs" / "v4_0" / "H5_SCALE_2026_11_01" / "summary.json",
    ROOT / "outputs" / "v4_0" / "H5_SCALE_2026_11_01" / "performance_summary.csv",
    ROOT / "outputs" / "v4_0" / "H5_SCALE_2026_11_01" / "failures.csv",
    ROOT / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main" / "Advancing_Fact_Attribution_for_Query_Answering.pdf",
    ROOT / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main" / "Algorithms" / "LExaShap" / "ShapleyEngine.py",
    HISTORICAL_TRUTH,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def historical_hashes() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): sha256(path) for path in HISTORICAL_FILES}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"拒绝写入空 CSV: {path}")
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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def predecessor_weight_audit(game: StateGame) -> list[dict[str, Any]]:
    """Independently audit predecessor counts, Shapley weights, and state merging."""
    rows: list[dict[str, Any]] = []
    for focal in range(game.n):
        state_counts: dict[tuple[int, tuple[int, ...]], int] = {}
        size_counts = [0] * game.n
        others = [player for player in range(game.n) if player != focal]
        for local_mask in range(1 << (game.n - 1)):
            state = game.zero
            size = 0
            for bit, player in enumerate(others):
                if local_mask & (1 << bit):
                    state = add_state(state, game.deltas[player])
                    size += 1
            size_counts[size] += 1
            key = (size, state)
            state_counts[key] = state_counts.get(key, 0) + 1
        expected = 1 << (game.n - 1)
        weight_sum = sum(
            count / (game.n * math.comb(game.n - 1, size))
            for (size, _state), count in state_counts.items()
        )
        max_size_count_error = max(
            abs(observed - math.comb(game.n - 1, size))
            for size, observed in enumerate(size_counts)
        )
        rows.append(
            {
                "game_id": game.game_id,
                "player": game.player_ids[focal],
                "predecessor_coalitions": expected,
                "unique_size_state_pairs": len(state_counts),
                "merged_duplicate_coalitions": expected - len(state_counts),
                "maximum_state_multiplicity": max(state_counts.values()),
                "shapley_weight_sum": weight_sum,
                "maximum_size_bucket_count_error": max_size_count_error,
                "passes": abs(weight_sum - 1.0) <= 1e-12 and max_size_count_error == 0,
            }
        )
    return rows


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


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
    if not get_memory(handle, ctypes.byref(counters), counters.cb):
        raise ctypes.WinError()
    return int(counters.WorkingSetSize)


def sampled_peak(call: Callable[[], Any], *, capture: bool) -> tuple[Any, float, int | str]:
    gc.collect()
    stop = threading.Event()
    peak = current_working_set() if capture else 0

    def monitor() -> None:
        nonlocal peak
        while not stop.wait(0.01):
            peak = max(peak, current_working_set())

    thread = threading.Thread(target=monitor, daemon=True)
    if capture:
        thread.start()
    started = time.perf_counter()
    try:
        result = call()
    finally:
        elapsed = time.perf_counter() - started
        if capture:
            peak = max(peak, current_working_set())
            stop.set()
            thread.join()
    return result, elapsed, peak if capture else "NA"


def d1p_record_delta(record, spec) -> tuple[int, ...]:
    values = [0] * 16
    offset = LEAVES.index(record.leaf_node_id) * 4
    values[offset : offset + 4] = [
        1,
        int(record.category_a_id == spec.category_a_target),
        int(record.attribute_present),
        int(record.attribute_present and record.category_b_id == spec.category_b_target),
    ]
    return tuple(values)


def d1p_report_state(state: tuple[int, ...], spec) -> D1PState:
    result = D1PState.empty(spec.nodes)
    for leaf_index, leaf in enumerate(LEAVES):
        local = state[4 * leaf_index : 4 * leaf_index + 4]
        for node in spec.ancestors[leaf]:
            for counter, value in enumerate(local):
                result.counts[node][counter] += value
    return result


def build_games() -> tuple[list[StateGame], Any, D1PValueSuite]:
    spec = load_d1p_spec(CONFIG)
    suite = D1PValueSuite(spec, state_for_mask(spec.full_mask, spec), VALUE_CONFIG)
    deltas = tuple(d1p_record_delta(record, spec) for record in spec.records)
    player_ids = tuple(record.record_id for record in spec.records)
    leaves = tuple(LEAVES.index(record.leaf_node_id) for record in spec.records)

    def v1(state: tuple[int, ...]) -> float:
        return float(suite.v1(d1p_report_state(state, spec)))

    def v2(state: tuple[int, ...]) -> float:
        return float(suite.v2_decimal(d1p_report_state(state, spec), Fraction(1, 2), precision=110))

    games = [
        StateGame("D1P_V1", player_ids, deltas, v1, leaves, 4, 4),
        StateGame("D1P_V2", player_ids, deltas, v2, leaves, 4, 4),
    ]
    for n in (12, 16):
        config = ScaleConfig(
            config_id=f"G1_N{n}_L4_D4_ORIGINAL_FAMILIES",
            group="H5_R_SCALE_CONTROL",
            n=n,
            leaves=4,
            dimensions=4,
            profile="balanced_templates",
            family_map=(0, 1, 2, 3),
            score_modes=("v2",),
            exact_payments_expected=True,
        )
        instance = generate_instance(config, 7301)
        games.append(
            StateGame(
                f"SCALE_N{n}_V2",
                tuple(f"p{player + 1}" for player in range(n)),
                tuple(scale_record_delta(record, 4, 4) for record in instance.records),
                make_value_function(instance, "v2"),
                tuple(record.leaf for record in instance.records),
                4,
                4,
            )
        )
    return games, spec, suite


METHODS = {
    "S0_PER_FOCUS_B2": s0_per_focus_b2,
    "S1_PER_FOCUS_B3": s1_per_focus_b3,
    "S2_PER_FOCUS_B4": s2_per_focus_b4,
    "S3_SHARED_FORWARD_DIVISION": S3SharedForward,
    "S4_PREFIX_SUFFIX_REUSE": S4PrefixSuffix,
    "S5_TYPE_MULTI_OUTPUT_VE": S5TypeMultiOutput,
    "S6_REVERSE_MULTILINEAR_AD": S6ReverseMultilinearAD,
}


def run_method(
    game: StateGame,
    method: str,
    cap: int,
    *,
    capture_memory: bool,
) -> tuple[list[float], dict[str, Any]]:
    implementation = METHODS[method]
    if method.startswith(("S0_", "S1_", "S2_")):
        _, single_seconds, _ = sampled_peak(
            lambda: implementation(game, [0], state_cap=cap), capture=False
        )

        def full_call():
            return implementation(game, range(game.n), state_cap=cap)

        (mapping, diagnostics), full_seconds, peak = sampled_peak(full_call, capture=capture_memory)
        allocation = [mapping[player] for player in range(game.n)]
        return allocation, {
            "shared_preprocess_seconds": 0.0,
            "single_player_query_seconds": single_seconds,
            "all_player_solve_seconds": full_seconds,
            "end_to_end_seconds": full_seconds,
            "peak_sampled_rss_bytes": peak,
            "single_player_query_scope": "one_focal_only",
            **diagnostics,
        }

    solver_box: dict[str, Any] = {}

    def prepare():
        solver_box["solver"] = implementation(game, state_cap=cap)
        return solver_box["solver"]

    solver, preprocess_seconds, peak_prepare = sampled_peak(prepare, capture=capture_memory)
    _, single_seconds, peak_single = sampled_peak(lambda: solver.query(0), capture=capture_memory)
    solver.clear_query_cache()
    allocation, full_seconds, peak_full = sampled_peak(solver.solve_all, capture=capture_memory)
    diagnostics = solver.diagnostics()
    peaks = [item for item in (peak_prepare, peak_single, peak_full) if item != "NA"]
    return allocation, {
        "shared_preprocess_seconds": preprocess_seconds,
        "single_player_query_seconds": single_seconds,
        "all_player_solve_seconds": full_seconds,
        "end_to_end_seconds": preprocess_seconds + full_seconds,
        "peak_sampled_rss_bytes": max(peaks) if peaks else "NA",
        **diagnostics,
    }


def v1_coordinate_decomposition(spec, suite: D1PValueSuite) -> tuple[list[float], dict[str, Any]]:
    started = time.perf_counter()
    payments = {record.record_id: Fraction() for record in spec.records}
    coordinate_states = 0
    transition_terms = 0
    linear_metrics = (
        ("record_count", 0),
        ("category_a_target_count", 1),
        ("attribute_present_count", 2),
    )
    ratio_metrics = ("category_a_target_share", "category_b_target_share")
    full_state = state_for_mask(spec.full_mask, spec)
    for node in spec.nodes:
        for metric, counter_index in linear_metrics:
            full = full_state.counts[node][counter_index]
            if full <= 0:
                continue
            scale = suite.revenue * suite.coordinate_weights[(node, metric)] / full
            for record in spec.records:
                if node not in spec.ancestors[record.leaf_node_id]:
                    continue
                contributes = (
                    metric == "record_count"
                    or (metric == "category_a_target_count" and record.category_a_id == spec.category_a_target)
                    or (metric == "attribute_present_count" and record.attribute_present)
                )
                if contributes:
                    payments[record.record_id] += scale
                    transition_terms += 1

        for metric in ratio_metrics:
            kinds: dict[str, str] = {}
            for record in spec.records:
                if node not in spec.ancestors[record.leaf_node_id]:
                    kinds[record.record_id] = "irrelevant"
                elif metric == "category_a_target_share":
                    kinds[record.record_id] = (
                        "target" if record.category_a_id == spec.category_a_target else "non_target"
                    )
                elif not record.attribute_present:
                    kinds[record.record_id] = "irrelevant"
                else:
                    kinds[record.record_id] = (
                        "target" if record.category_b_id == spec.category_b_target else "non_target"
                    )
            target_count = sum(kind == "target" for kind in kinds.values())
            non_target_count = sum(kind == "non_target" for kind in kinds.values())
            irrelevant_count = spec.player_count - target_count - non_target_count
            full = target_count + non_target_count
            target_full = target_count
            coordinate_payments: dict[str, Fraction] = {}
            for focal_kind in ("target", "non_target"):
                if focal_kind not in kinds.values():
                    continue
                t_other = target_count - int(focal_kind == "target")
                n_other = non_target_count - int(focal_kind == "non_target")
                i_other = irrelevant_count
                phi = Fraction()
                for a in range(t_other + 1):
                    for b in range(n_other + 1):
                        for irrelevant in range(i_other + 1):
                            size = a + b + irrelevant
                            multiplicity = (
                                math.comb(t_other, a)
                                * math.comb(n_other, b)
                                * math.comb(i_other, irrelevant)
                            )
                            before = Fraction(a + b, full) - Fraction(
                                abs(a * full - (a + b) * target_full), full * full
                            )
                            after_a = a + int(focal_kind == "target")
                            after_total = a + b + 1
                            after = Fraction(after_total, full) - Fraction(
                                abs(after_a * full - after_total * target_full), full * full
                            )
                            phi += multiplicity * (after - before) / (
                                spec.player_count * math.comb(spec.player_count - 1, size)
                            )
                            coordinate_states += 1
                            transition_terms += 1
                coordinate_payments[focal_kind] = phi
            scale = suite.revenue * suite.coordinate_weights[(node, metric)]
            for player, kind in kinds.items():
                if kind in coordinate_payments:
                    payments[player] += scale * coordinate_payments[kind]
    allocation = [float(payments[record.record_id]) for record in spec.records]
    elapsed = time.perf_counter() - started
    return allocation, {
        "shared_preprocess_seconds": 0.0,
        "single_player_query_seconds": "NOT_SEPARATELY_MATERIALIZED",
        "all_player_solve_seconds": elapsed,
        "end_to_end_seconds": elapsed,
        "peak_sampled_rss_bytes": "NA",
        "terminal_state_visits": coordinate_states,
        "state_transitions": transition_terms,
        "intermediate_state_visits": coordinate_states,
        "maximum_frontier_states": "PER_COORDINATE_CLOSED_FORM",
        "state_rebuild_count": 14,
        "value_cache_entries": 0,
        "value_cache_requests": 0,
        "value_cache_hits": 0,
        "value_cache_hit_rate": 0.0,
        "result_cache_requests": spec.player_count * 14,
        "result_cache_hits": sum(max(0, list(kinds.values()).count(kind) - 1) for kind in set(kinds.values())),
        "result_cache_hit_rate": "TYPE_SYMMETRY_PER_COORDINATE",
        "sharing_mechanism": "V1 linear coordinates plus exact ratio type-count closed form",
        "single_player_query_scope": "coordinate_decomposition_all_outputs",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    before_hashes = historical_hashes()
    total_started = time.perf_counter()
    games, spec, suite = build_games()
    game_rows = [
        {
            "game_id": game.game_id,
            "player_count": game.n,
            "state_width": len(game.zero),
            "leaf_count": game.leaf_count,
            "leaf_width": game.leaf_width,
            "unique_delta_types": len(set(game.deltas)),
            "value_target": "frozen D1-P" if game.game_id.startswith("D1P") else "H5-SCALE generated control",
            "seed": "FROZEN" if game.game_id.startswith("D1P") else 7301,
        }
        for game in games
    ]

    # Independent truth is computed before any historical payment file is read.
    truth: dict[str, list[float]] = {}
    truth_cost_rows: list[dict[str, Any]] = []
    for game in games:
        print(f"B0 {game.game_id}", flush=True)
        (allocation, diagnostics), elapsed, peak = sampled_peak(lambda game=game: exact_b0(game), capture=True)
        truth[game.game_id] = allocation
        truth_cost_rows.append(
            {
                "game_id": game.game_id,
                "method": "B0_FULL_COALITION_TRUTH",
                "repeat": 0,
                "status": "SUCCESS",
                "shared_preprocess_seconds": 0.0,
                "single_player_query_seconds": "NOT_SEPARATELY_TIMED",
                "all_player_solve_seconds": elapsed,
                "end_to_end_seconds": elapsed,
                "peak_sampled_rss_bytes": peak,
                **diagnostics,
            }
        )

    predecessor_rows = [row for game in games for row in predecessor_weight_audit(game)]
    if not all(row["passes"] for row in predecessor_rows):
        raise AssertionError("predecessor coalition combination or Shapley-weight audit failed")

    resource_rows: list[dict[str, Any]] = []
    selected_cap: dict[tuple[str, str], int | None] = {}
    for game in games:
        for method in METHODS:
            selected_cap[(game.game_id, method)] = None
            for cap in CAP_TIERS:
                started = time.perf_counter()
                try:
                    allocation, diagnostics = run_method(game, method, cap, capture_memory=False)
                    status = "SUCCESS"
                    error = max_abs_error(allocation, truth[game.game_id])
                    selected_cap[(game.game_id, method)] = cap
                    detail = f"max_error={error}"
                except SharedStateLimitExceeded as exc:
                    status = "STATE_CAP_EXCEEDED"
                    diagnostics = {}
                    detail = str(exc)
                elapsed = time.perf_counter() - started
                resource_rows.append(
                    {
                        "game_id": game.game_id,
                        "method": method,
                        "state_cap": cap,
                        "status": status,
                        "attempt_seconds": elapsed,
                        "detail": detail,
                        "payment_reported": status == "SUCCESS" and error <= TOLERANCE,
                        **diagnostics,
                    }
                )
                if status == "SUCCESS":
                    break

    raw_rows: list[dict[str, Any]] = list(truth_cost_rows)
    correctness_rows: list[dict[str, Any]] = []
    payment_rows: list[dict[str, Any]] = []
    allocation_first: dict[tuple[str, str], list[float]] = {}
    for game in games:
        for method in METHODS:
            cap = selected_cap[(game.game_id, method)]
            if cap is None:
                raw_rows.append(
                    {
                        "game_id": game.game_id,
                        "method": method,
                        "repeat": "NA",
                        "status": "FAILED_ALL_CAP_TIERS",
                        "state_cap": CAP_TIERS[-1],
                    }
                )
                continue
            print(f"TIMING {game.game_id} {method} cap={cap}", flush=True)
            for repeat in range(TIMING_REPEATS):
                allocation, diagnostics = run_method(
                    game, method, cap, capture_memory=repeat == 0
                )
                if repeat == 0:
                    allocation_first[(game.game_id, method)] = allocation
                raw_rows.append(
                    {
                        "game_id": game.game_id,
                        "method": method,
                        "repeat": repeat,
                        "status": "SUCCESS",
                        "state_cap": cap,
                        **diagnostics,
                    }
                )

            allocation = allocation_first[(game.game_id, method)]
            error = max_abs_error(allocation, truth[game.game_id])
            efficiency = efficiency_error(game, allocation)
            passes = error <= TOLERANCE and efficiency <= TOLERANCE
            correctness_rows.append(
                {
                    "game_id": game.game_id,
                    "method": method,
                    "state_cap": cap,
                    "max_player_abs_error_vs_B0": error,
                    "efficiency_abs_error": efficiency,
                    "passes_1e_9": passes,
                    "truth_computed_before_historical_payment_read": True,
                }
            )
            if not passes:
                raise AssertionError(f"{game.game_id}/{method} correctness gate failed")
            for player, (estimate, expected) in enumerate(zip(allocation, truth[game.game_id], strict=True)):
                payment_rows.append(
                    {
                        "game_id": game.game_id,
                        "method": method,
                        "player": game.player_ids[player],
                        "shapley": estimate,
                        "B0_truth": expected,
                        "absolute_error": abs(estimate - expected),
                    }
                )

    # Strongest applicable frozen-V1 decomposition; no historical payment is used as input.
    v1_special_rows: list[dict[str, Any]] = []
    v1_special_allocation: list[float] | None = None
    for repeat in range(TIMING_REPEATS):
        (allocation, diagnostics), elapsed, peak = sampled_peak(
            lambda: v1_coordinate_decomposition(spec, suite), capture=repeat == 0
        )
        diagnostics["peak_sampled_rss_bytes"] = peak
        diagnostics["end_to_end_seconds"] = elapsed
        diagnostics["all_player_solve_seconds"] = elapsed
        if repeat == 0:
            v1_special_allocation = allocation
        v1_special_rows.append(
            {
                "game_id": "D1P_V1",
                "method": "V1_COORDINATE_DECOMPOSITION",
                "repeat": repeat,
                "status": "SUCCESS",
                **diagnostics,
            }
        )
    raw_rows.extend(v1_special_rows)
    assert v1_special_allocation is not None
    v1_error = max_abs_error(v1_special_allocation, truth["D1P_V1"])
    correctness_rows.append(
        {
            "game_id": "D1P_V1",
            "method": "V1_COORDINATE_DECOMPOSITION",
            "state_cap": "NOT_APPLICABLE",
            "max_player_abs_error_vs_B0": v1_error,
            "efficiency_abs_error": abs(sum(v1_special_allocation) - 1000.0),
            "passes_1e_9": v1_error <= TOLERANCE,
            "truth_computed_before_historical_payment_read": True,
        }
    )
    if v1_error > TOLERANCE:
        raise AssertionError(f"V1 coordinate decomposition error {v1_error}")
    d1p_v1_game = next(game for game in games if game.game_id == "D1P_V1")
    for player, (estimate, expected) in enumerate(
        zip(v1_special_allocation, truth["D1P_V1"], strict=True)
    ):
        payment_rows.append(
            {
                "game_id": "D1P_V1",
                "method": "V1_COORDINATE_DECOMPOSITION",
                "player": d1p_v1_game.player_ids[player],
                "shapley": estimate,
                "B0_truth": expected,
                "absolute_error": abs(estimate - expected),
            }
        )

    # Historical payments are loaded only now, post hoc.
    historical_loaded_after_algorithms = True
    historical = json.loads(HISTORICAL_TRUTH.read_text(encoding="utf-8"))
    historical_audit_rows: list[dict[str, Any]] = []
    for value_name, game_id in (("V1", "D1P_V1"), ("V2_lambda_0_5", "D1P_V2")):
        historical_values = [float(Fraction(str(value))) for value in historical["record_shapley"][value_name]]
        historical_audit_rows.append(
            {
                "game_id": game_id,
                "historical_target": value_name,
                "max_abs_error_B0_vs_historical": max_abs_error(truth[game_id], historical_values),
                "historical_loaded_after_algorithms": historical_loaded_after_algorithms,
            }
        )

    # Descriptive summaries: repeated timings on the same frozen instance are not independent instances.
    summary_rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in raw_rows:
        if row.get("status") != "SUCCESS" or row.get("method") == "B0_FULL_COALITION_TRUTH":
            continue
        grouped.setdefault((row["game_id"], row["method"]), []).append(row)
    for (game_id, method), rows in grouped.items():
        summary: dict[str, Any] = {
            "game_id": game_id,
            "method": method,
            "successful_repeats": len(rows),
            "timing_scope": "same_frozen_instance_repeated_run",
        }
        for field in (
            "shared_preprocess_seconds",
            "single_player_query_seconds",
            "all_player_solve_seconds",
            "end_to_end_seconds",
        ):
            values = [float(row[field]) for row in rows if row.get(field) not in (None, "NA", "NOT_SEPARATELY_MATERIALIZED")]
            summary[f"{field}_median"] = statistics.median(values) if values else "NA"
            summary[f"{field}_q1"] = percentile(values, 0.25) if values else "NA"
            summary[f"{field}_q3"] = percentile(values, 0.75) if values else "NA"
            summary[f"{field}_iqr"] = percentile(values, 0.75) - percentile(values, 0.25) if values else "NA"
        first = rows[0]
        for field in (
            "state_cap",
            "terminal_state_visits",
            "state_transitions",
            "intermediate_state_visits",
            "maximum_frontier_states",
            "state_rebuild_count",
            "value_cache_entries",
            "value_cache_hit_rate",
            "result_cache_hit_rate",
            "cached_factor_states",
            "quadrature_order",
            "sharing_mechanism",
            "single_player_query_scope",
        ):
            summary[field] = first.get(field, "NA")
        peaks = [float(row["peak_sampled_rss_bytes"]) for row in rows if row.get("peak_sampled_rss_bytes") not in (None, "NA")]
        summary["peak_sampled_rss_first_repeat_bytes"] = peaks[0] if peaks else "NA"
        summary_rows.append(summary)

    # V1/V2 comparison under identical state representation and strongest applicable method.
    v1_v2_rows: list[dict[str, Any]] = []
    v2_best_method = min(
        (row for row in summary_rows if row["game_id"] == "D1P_V2" and row["method"] in METHODS),
        key=lambda row: float(row["end_to_end_seconds_median"]),
    )["method"]
    for scope, methods in (
        ("A_SAME_JOINT_STATE", tuple(METHODS)),
        ("B_STRONGEST_APPLICABLE", ("V1_COORDINATE_DECOMPOSITION", v2_best_method)),
    ):
        for method in methods:
            if scope.startswith("A_"):
                game_ids = ("D1P_V1", "D1P_V2")
            else:
                game_ids = ("D1P_V1",) if method == "V1_COORDINATE_DECOMPOSITION" else ("D1P_V2",)
            for game_id in game_ids:
                match = next(
                    (row for row in summary_rows if row["game_id"] == game_id and row["method"] == method),
                    None,
                )
                if match:
                    v1_v2_rows.append(
                        {
                            "comparison_scope": scope,
                            "game_id": game_id,
                            "method": method,
                            "end_to_end_median_seconds": match["end_to_end_seconds_median"],
                            "shared_preprocess_median_seconds": match["shared_preprocess_seconds_median"],
                            "all_player_solve_median_seconds": match["all_player_solve_seconds_median"],
                            "state_rebuild_count": match["state_rebuild_count"],
                            "maximum_frontier_states": match["maximum_frontier_states"],
                        }
                    )

    write_csv(OUT / "game_manifest.csv", game_rows)
    write_csv(OUT / "resource_tier_attempts.csv", resource_rows)
    write_csv(OUT / "raw_performance.csv", raw_rows)
    write_csv(OUT / "performance_summary.csv", summary_rows)
    write_csv(OUT / "correctness_audit.csv", correctness_rows)
    write_csv(OUT / "record_shapley_validation.csv", payment_rows)
    write_csv(OUT / "historical_truth_posthoc_audit.csv", historical_audit_rows)
    write_csv(OUT / "v1_v2_method_comparison.csv", v1_v2_rows)
    write_csv(OUT / "predecessor_weight_audit.csv", predecessor_rows)
    write_csv(
        OUT / "method_boundary_records.csv",
        [
            {
                "method": "Abramovich official Boolean d-tree gradient",
                "status": "NOT_DIRECTLY_IMPLEMENTED_FOR_V2",
                "reason_category": "MATHEMATICAL_INPUT_AND_INTERFACE_MISMATCH",
                "evidence": "Frozen V2 is a nonlinear numeric terminal function over joint count states, not the official Boolean d-tree input.",
            },
            {
                "method": "S6 reverse multilinear expectation circuit",
                "status": "INDEPENDENT_CLASSIC_AD_IMPLEMENTATION",
                "reason_category": "NOT_AN_OFFICIAL_ABRAMOVICH_ADAPTER",
                "evidence": "Reverse differentiation is applied to coalition-probability arithmetic layers; terminal V2 values are constants and are not differentiated.",
            },
        ],
    )

    after_hashes = historical_hashes()
    if before_hashes != after_hashes:
        raise AssertionError("历史 H5/H5-SCALE/D1-P/Abramovich 文件哈希发生变化")
    write_json(OUT / "historical_hashes.json", {"before": before_hashes, "after": after_hashes, "unchanged": True})
    result = {
        "status": "H5_R_COMPLETED_AND_PAUSED",
        "games": game_rows,
        "game_ids": [game.game_id for game in games],
        "methods": list(METHODS) + ["V1_COORDINATE_DECOMPOSITION"],
        "cap_tiers": list(CAP_TIERS),
        "timing_repeats": TIMING_REPEATS,
        "correctness_tolerance": TOLERANCE,
        "all_correctness_passed": all(str(row["passes_1e_9"]).lower() == "true" for row in correctness_rows),
        "historical_truth_loaded_posthoc_only": historical_loaded_after_algorithms,
        "historical_files_unchanged": True,
        "predecessor_weight_audit_passed": True,
        "strongest_observed_v2_method": v2_best_method,
        "total_wall_seconds": time.perf_counter() - total_started,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "statistical_scope": "three repeated timings on each same frozen instance; median and IQR are runtime-noise summaries, not independent-instance confidence intervals",
    }
    write_json(OUT / "summary.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
