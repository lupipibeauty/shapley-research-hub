from __future__ import annotations

import argparse
import json
import random
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rq3_core import (  # noqa: E402
    VALUE_NAMES,
    b0_cost_row,
    compare_pair,
    environment_manifest,
    generate_fixture,
    interaction_rows,
    metric_arrays,
    metric_arrays_witness_states,
    nondegeneracy_rows,
    paired_references,
    player_rows,
    popcounts,
    run_s6_baseline,
    save_fixture,
    structure_metrics,
    validate_sql_all_coalitions,
    validate_sql_sample,
    value_arrays,
    write_csv,
    write_json,
)


def load_config() -> dict[str, Any]:
    return json.loads((ROOT / "configs" / "experiment_v2.json").read_text(encoding="utf-8"))


class RunLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **payload: Any) -> None:
        row = {
            "timestamp": datetime.now().astimezone().isoformat(),
            "event": event,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps(row, ensure_ascii=False), flush=True)


def fixture_specs(config: dict[str, Any], stage: str):
    for group in config["stages"][stage]:
        for seed in group["seeds"]:
            yield {
                "pair_id": f"{stage}_N{group['n']}_S{seed}",
                "seed": seed,
                "n": group["n"],
                "e": group["e"],
                "b": group["b"],
                "h": group["h"],
            }


def sampled_masks(n: int, seed: int, count: int = 64) -> list[int]:
    upper = 1 << n
    masks = {0, upper - 1}
    masks.update(1 << player for player in range(n))
    masks.update((upper - 1) ^ (1 << player) for player in range(n))
    rng = random.Random(seed + 301)
    while len(masks) < min(count, upper):
        masks.add(rng.randrange(upper))
    return sorted(masks)


def allocation_rows(fixture, value_name: str, method: str, reference_mode: str, allocation: np.ndarray):
    players = player_rows(fixture)
    return [
        {
            "pair_id": fixture.pair_id,
            "seed": fixture.seed,
            "n": fixture.n,
            "structure": fixture.structure,
            "value_name": value_name,
            "method": method,
            "reference_mode": reference_mode,
            "player_index": player["player_index"],
            "player_id": player["player_id"],
            "relation": player["relation"],
            "shapley": float(allocation[player["player_index"]]),
        }
        for player in players
    ]


def aggregate_separate_rows(first: dict[str, Any], second: dict[str, Any], status: str) -> dict[str, Any]:
    phases = ("source_seconds", "transform_seconds", "compile_seconds", "solve_seconds")
    row = {
        "pair_id": first["pair_id"],
        "seed": first["seed"],
        "n": first["n"],
        "structure": first["structure"],
        "value_name": "cross_add",
        "method": "H3_S6_SEPARATE_LINEAR",
        "player_order": first["player_order"],
        "status": status,
        "detail": "cross_f1 and cross_f2 compiled separately; allocations averaged by linearity",
        "max_abs_error": None,
        "efficiency_error": None,
    }
    for phase in phases:
        row[phase] = float(first.get(phase, 0.0)) + float(second.get(phase, 0.0))
    row["total_cold_seconds"] = sum(row[p] for p in phases)
    row["total_reuse_seconds"] = row["compile_seconds"] + row["solve_seconds"]
    row["peak_rss_bytes"] = max(first.get("peak_rss_bytes") or 0, second.get("peak_rss_bytes") or 0)
    row["python_peak_bytes"] = max(first.get("python_peak_bytes") or 0, second.get("python_peak_bytes") or 0)
    row["terminal_value_states"] = (first.get("terminal_value_states") or 0) + (second.get("terminal_value_states") or 0)
    return row


def status_rows_for_unadapted(pair_id: str, n: int) -> list[dict[str, Any]]:
    return [
        {
            "pair_id": pair_id,
            "n": n,
            "method": "P3_MTBDD_HISTORICAL",
            "status": "INPUT_UNSUPPORTED",
            "reason": "历史 P3 对象不是本轮冻结 E/B/H 物理玩家与 35 坐标联合价值；本轮未改写作者/历史算法。",
        },
        {
            "pair_id": pair_id,
            "n": n,
            "method": "LEXASHAP_REDUCTION",
            "status": "INPUT_UNSUPPORTED",
            "reason": "尚无对当前双坐标乘积价值的已核验精确归约适配；不得把理论可能性记作已实现。",
        },
        {
            "pair_id": pair_id,
            "n": n,
            "method": "ABRAMOVICH_AUTHOR_PIPELINE",
            "status": "ENV_BLOCKED",
            "reason": "作者流水线未在本轮本地环境形成可执行、同目标适配。",
        },
        {
            "pair_id": pair_id,
            "n": n,
            "method": "M3_VARIABLE_ORDERING",
            "status": "REPORTED_ONLY",
            "reason": "M3 仍是历史设计记录，没有可恢复的 M3 BDD 原始执行证据。",
        },
    ]


def run_pair(stage: str, spec: dict[str, Any], config: dict[str, Any], run_dir: Path, log: RunLog):
    year = config["year"]
    fixtures = {
        structure: generate_fixture(
            pair_id=spec["pair_id"], structure=structure, seed=spec["seed"],
            e_count=spec["e"], b_count=spec["b"], h_count=spec["h"], year=year,
        )
        for structure in ("low", "high")
    }
    pair_check = {"pair_id": spec["pair_id"], "seed": spec["seed"], "n": spec["n"], **compare_pair(fixtures["low"], fixtures["high"])}
    pair_check["status"] = "VERIFIED" if pair_check["province_enterprise_changed"] else "FAILED_CORRECTNESS"
    log.emit("fixtures_generated", pair_id=spec["pair_id"], pair_check_status=pair_check["status"])

    manifests = []
    structure_rows = []
    for structure, fixture in fixtures.items():
        manifests.append(save_fixture(fixture, run_dir / "fixtures" / spec["pair_id"] / structure))
        structure_rows.append(structure_metrics(fixture))

    sql_rows = []
    sql_samples = []
    sql_path = ROOT / "sql" / "report_v1.sql"
    for structure, fixture in fixtures.items():
        if stage == "E0":
            row, samples = validate_sql_all_coalitions(fixture, sql_path)
            row["validation_mode"] = "ALL_COALITIONS"
        else:
            row, samples = validate_sql_sample(fixture, sql_path, sampled_masks(fixture.n, fixture.seed))
        sql_rows.append(row)
        sql_samples.extend({"pair_id": fixture.pair_id, "structure": structure, **sample} for sample in samples)
        log.emit("sql_validation", pair_id=spec["pair_id"], structure=structure, status=row["status"], masks=row["coalitions"])

    arrays_by_structure = {}
    phase_by_structure = {}
    for structure, fixture in fixtures.items():
        if stage == "E2":
            arrays_by_structure[structure], phase_by_structure[structure] = metric_arrays_witness_states(fixture)
        else:
            arrays_by_structure[structure], phase_by_structure[structure] = metric_arrays(fixture)
    common_refs = paired_references(arrays_by_structure["low"], arrays_by_structure["high"])
    own_refs = {
        structure: {key: float(array[-1]) for key, array in arrays.items()}
        for structure, arrays in arrays_by_structure.items()
    }
    reference_payload = {"paired_common": common_refs, "structure_own": own_refs}

    nondegenerate = []
    lambda_zero = []
    primary_values = {}
    for structure, fixture in fixtures.items():
        arrays = arrays_by_structure[structure]
        primary_values[structure] = value_arrays(arrays, common_refs, config["revenue"], config["lambda"])
        nondegenerate.extend(nondegeneracy_rows(fixture, arrays, primary_values[structure], common_refs))
        zero_values = value_arrays(arrays, common_refs, config["revenue"], 0.0)
        for scope in ("local", "cross"):
            error = float(np.max(np.abs(zero_values[f"{scope}_joint"] - zero_values[f"{scope}_add"])))
            lambda_zero.append({
                "pair_id": fixture.pair_id,
                "structure": structure,
                "scope": scope,
                "max_abs_error": error,
                "status": "VERIFIED" if error <= config["tolerance"] else "FAILED_CORRECTNESS",
            })

    cost_rows = []
    allocation_output = []
    baseline_rows = status_rows_for_unadapted(spec["pair_id"], spec["n"])
    exact_allocations: dict[tuple[str, str], np.ndarray] = {}

    if stage in ("E0", "E1"):
        counts = popcounts(spec["n"])
        for structure, fixture in fixtures.items():
            phase = phase_by_structure[structure]
            for value_name in VALUE_NAMES:
                row, allocation = b0_cost_row(
                    fixture, value_name, primary_values[structure][value_name], counts,
                    phase["source_seconds"], phase["transform_seconds"],
                )
                cost_rows.append(row)
                exact_allocations[(structure, value_name)] = allocation
                allocation_output.extend(allocation_rows(fixture, value_name, row["method"], "paired_common", allocation))
            own_values = value_arrays(arrays_by_structure[structure], own_refs[structure], config["revenue"], config["lambda"])
            for value_name in VALUE_NAMES:
                allocation = __import__("rq3_core").exact_shapley(own_values[value_name], fixture.n, counts)
                allocation_output.extend(allocation_rows(fixture, value_name, "B0_FULL_COALITION_NUMPY", "structure_own", allocation))

        for structure, fixture in fixtures.items():
            phase = phase_by_structure[structure]
            for value_name in VALUE_NAMES:
                row, allocation = run_s6_baseline(
                    fixture, value_name, common_refs, config["revenue"], config["lambda"],
                    config["state_cap"][stage], exact_allocations[(structure, value_name)],
                    phase["source_seconds"], config["player_order"],
                )
                cost_rows.append(row)
                if allocation is not None:
                    allocation_output.extend(allocation_rows(fixture, value_name, row["method"], "paired_common", allocation))
                log.emit("baseline", pair_id=spec["pair_id"], structure=structure, value_name=value_name, method=row["method"], status=row["status"])

        # One frozen E1 comparison: compile the two additive coordinates separately.
        if stage == "E1" and spec["seed"] == config["stages"]["E1"][0]["seeds"][0]:
            fixture = fixtures["high"]
            phase = phase_by_structure["high"]
            component_rows = []
            component_allocations = []
            for value_name in ("cross_f1", "cross_f2"):
                row, allocation = run_s6_baseline(
                    fixture, value_name, common_refs, config["revenue"], config["lambda"],
                    config["state_cap"][stage], None, phase["source_seconds"], config["player_order"],
                )
                component_rows.append(row)
                component_allocations.append(allocation)
            status = "VERIFIED" if all(row["status"] == "VERIFIED" for row in component_rows) else next(row["status"] for row in component_rows if row["status"] != "VERIFIED")
            aggregate = aggregate_separate_rows(component_rows[0], component_rows[1], status)
            if status == "VERIFIED":
                combined = (component_allocations[0] + component_allocations[1]) / 2.0
                error = float(np.max(np.abs(combined - exact_allocations[("high", "cross_add")])))
                aggregate["max_abs_error"] = error
                aggregate["status"] = "VERIFIED" if error <= config["tolerance"] else "FAILED_CORRECTNESS"
                allocation_output.extend(allocation_rows(fixture, "cross_add", aggregate["method"], "paired_common", combined))
            cost_rows.append(aggregate)
    else:
        # E2 is a gate-limited mechanism probe.  It does not enumerate 2^N.
        for structure, fixture in fixtures.items():
            phase = phase_by_structure[structure]
            for value_name in VALUE_NAMES:
                row, allocation = run_s6_baseline(
                    fixture, value_name, common_refs, config["revenue"], config["lambda"],
                    config["state_cap"][stage], None, phase["source_seconds"], config["player_order"],
                )
                cost_rows.append(row)
                if allocation is not None:
                    allocation_output.extend(allocation_rows(fixture, value_name, row["method"], "paired_common", allocation))
                log.emit("baseline", pair_id=spec["pair_id"], structure=structure, value_name=value_name, method=row["method"], status=row["status"])

    baseline_rows.extend({
        "pair_id": row["pair_id"], "n": row["n"], "method": row["method"],
        "structure": row["structure"], "value_name": row["value_name"],
        "status": row["status"], "reason": row.get("detail", ""),
    } for row in cost_rows)
    return {
        "pair_check": pair_check,
        "manifests": manifests,
        "structure": structure_rows,
        "sql": sql_rows,
        "sql_samples": sql_samples,
        "references": {spec["pair_id"]: reference_payload},
        "nondegenerate": nondegenerate,
        "lambda_zero": lambda_zero,
        "cost": cost_rows,
        "allocations": allocation_output,
        "baselines": baseline_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("E0", "E1", "E2"), required=True)
    args = parser.parse_args()
    config = load_config()
    stage = args.stage
    run_id = f"{stage}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = ROOT / "runs" / run_id
    results = run_dir / "results"
    results.mkdir(parents=True, exist_ok=False)
    log = RunLog(run_dir / "run_events.jsonl")
    write_json(run_dir / "config_snapshot.json", config)
    write_json(run_dir / "environment_manifest.json", environment_manifest())
    started = time.perf_counter()
    log.emit("run_started", run_id=run_id, stage=stage)

    combined = {key: [] for key in ("pair_check", "manifests", "structure", "sql", "sql_samples", "nondegenerate", "lambda_zero", "cost", "allocations", "baselines")}
    references = {}
    fatal = None
    attempted = 0
    try:
        specs = list(fixture_specs(config, stage))
        if stage == "E2":
            # The E2 run is deliberately sequential.  A cap failure on the first
            # frozen pair is a resource gate, not a reason to repeat five equivalent failures.
            specs = specs[:1]
        for spec in specs:
            attempted += 1
            payload = run_pair(stage, spec, config, run_dir, log)
            references.update(payload.pop("references"))
            for key, value in payload.items():
                if key == "pair_check":
                    combined[key].append(value)
                else:
                    combined[key].extend(value)
            if stage == "E2" and any(row["status"] in ("RESOURCE_LIMIT", "FAILED_CORRECTNESS") for row in payload["cost"]):
                log.emit("e2_gate_stopped", pair_id=spec["pair_id"], reason="first frozen pair failed resource/correctness gate")
                break
    except Exception as exc:
        fatal = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        log.emit("run_failed", **fatal)

    write_csv(results / "pair_checks.csv", combined["pair_check"])
    write_csv(results / "fixture_manifests.csv", combined["manifests"])
    write_csv(results / "structure_metrics.csv", combined["structure"])
    write_csv(results / "sql_validation.csv", combined["sql"])
    write_csv(results / "sql_validation_samples.csv", combined["sql_samples"])
    write_csv(results / "nondegeneracy.csv", combined["nondegenerate"])
    write_csv(results / "lambda_zero_checks.csv", combined["lambda_zero"])
    write_csv(results / "cost_measurements.csv", combined["cost"])
    write_csv(results / "cost_interactions.csv", interaction_rows(combined["cost"]))
    write_csv(results / "shapley_allocations.csv", combined["allocations"])
    write_csv(results / "baseline_status.csv", combined["baselines"])
    write_json(results / "normalization_references.json", references)

    correctness_failures = []
    for key in ("pair_check", "sql", "nondegenerate", "lambda_zero", "cost"):
        correctness_failures.extend(row for row in combined[key] if row.get("status") == "FAILED_CORRECTNESS")
    if stage in ("E1", "E2"):
        correctness_failures.extend(
            row for row in combined["nondegenerate"] if str(row.get("mechanism_eligible")).lower() == "false"
        )
    resource_limits = [row for row in combined["cost"] if row.get("status") == "RESOURCE_LIMIT"]
    status = "FAILED_CORRECTNESS" if correctness_failures or fatal else ("RESOURCE_LIMIT" if resource_limits else "VERIFIED")
    stage_status = {
        "run_id": run_id,
        "stage": stage,
        "status": status,
        "started_pairs": attempted,
        "planned_pairs": sum(len(group["seeds"]) for group in config["stages"][stage]),
        "elapsed_seconds": time.perf_counter() - started,
        "correctness_failures": len(correctness_failures),
        "resource_limits": len(resource_limits),
        "fatal": fatal,
        "note": "E2 deliberately stops after the first frozen pair if the non-enumerative baseline fails its resource/correctness gate.",
    }
    write_json(run_dir / "stage_status.json", stage_status)
    log.emit("run_finished", **stage_status)
    return 0 if fatal is None and not correctness_failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
