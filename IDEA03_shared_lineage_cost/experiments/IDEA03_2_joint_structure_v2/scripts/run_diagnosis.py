from __future__ import annotations

import csv
import json
import random
import sys
import time
import traceback
from collections import defaultdict
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rq3_core import (  # noqa: E402
    environment_manifest,
    generate_fixture,
    player_rows,
    write_csv,
    write_json,
)
from rq3_diagnosis import (  # noqa: E402
    component_value,
    evidence_layer_profile,
    lexashap_component_allocation,
    lineage_structure_row,
    micro_control_rows,
    normalized_dnf_key,
    official_source_manifest,
    paired_full_references,
    poly_value,
    proof_profile_rows,
    sparse_harsanyi_allocation,
    value_components,
    value_from_report,
    value_polynomials,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class EventLog:
    def __init__(self, path: Path):
        self.path = path

    def emit(self, event: str, **payload: Any) -> None:
        row = {"timestamp": datetime.now().astimezone().isoformat(), "event": event, **payload}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps(row, ensure_ascii=False), flush=True)


def load_oracle() -> dict[tuple[str, str, str, str], float]:
    paths = [
        ROOT / "runs" / "E0_20261113_033545" / "results" / "shapley_allocations.csv",
        ROOT / "runs" / "E1_20261113_033650" / "results" / "shapley_allocations.csv",
    ]
    oracle: dict[tuple[str, str, str, str], float] = {}
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["method"] != "B0_FULL_COALITION_NUMPY" or row["reference_mode"] != "paired_common":
                    continue
                oracle[(row["pair_id"], row["structure"], row["value_name"], row["player_id"])] = float(row["shapley"])
    return oracle


def oracle_error(oracle, fixture, value_name: str, allocation: np.ndarray) -> float | None:
    expected = []
    for player in player_rows(fixture):
        key = (fixture.pair_id, fixture.structure, value_name, player["player_id"])
        if key not in oracle:
            return None
        expected.append(oracle[key])
    return float(np.max(np.abs(allocation - np.asarray(expected))))


def validation_masks(n: int, seed: int, random_count: int) -> list[int]:
    if n <= 10:
        return list(range(1 << n))
    masks = {0, (1 << n) - 1}
    masks.update(1 << player for player in range(n))
    rng = random.Random(seed + 701)
    while len(masks) < random_count:
        masks.add(rng.randrange(1 << n))
    return sorted(masks)


def aggregate_proof_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cross_shared_enterprises": sum(bool(row["cross_province"]) for row in rows),
        "local_or_terms": sum(row["local_or_terms_PA"] + row["local_or_terms_PB"] for row in rows),
        "same_entity_cross_product_terms": sum(row["same_entity_cross_product_terms"] for row in rows),
        "conserved_degree_total": sum(row["degree_identity_total"] for row in rows),
        "degree_identity_pass": all(row["degree_identity_total"] == row["degree_identity_expected"] for row in rows),
        "alternative_proof_pairs": sum(row["alternative_proof_pairs_PA"] + row["alternative_proof_pairs_PB"] for row in rows),
    }


def main() -> int:
    config = load_json(ROOT / "configs" / "diagnosis_v1.json")
    run_id = f"DIAG_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = ROOT / "runs" / run_id
    results_dir = run_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=False)
    log = EventLog(run_dir / "run_events.jsonl")
    write_json(run_dir / "config_snapshot.json", config)
    manifest = environment_manifest()
    manifest.update(official_source_manifest())
    write_json(run_dir / "environment_manifest.json", manifest)
    oracle = load_oracle()
    started = time.perf_counter()
    log.emit("diagnosis_started", run_id=run_id)

    structure_rows: list[dict[str, Any]] = []
    proof_rows: list[dict[str, Any]] = []
    proof_summary: list[dict[str, Any]] = []
    decomposition_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    baseline_rows: list[dict[str, Any]] = []
    allocation_rows: list[dict[str, Any]] = []
    layer_rows: list[dict[str, Any]] = []
    pair_invariance_rows: list[dict[str, Any]] = []
    fatal = None

    try:
        for spec in config["scales"]:
            fixtures = {
                structure: generate_fixture(
                    pair_id=spec["pair_id"], structure=structure, seed=spec["seed"],
                    e_count=spec["e"], b_count=spec["b"], h_count=spec["h"], year=config["year"],
                )
                for structure in ("low", "high")
            }
            references = paired_full_references(fixtures["low"], fixtures["high"])
            per_structure_proof = {}
            per_structure_graph = {}
            per_structure_layers = {}

            for structure, fixture in fixtures.items():
                graph = lineage_structure_row(fixture)
                structure_rows.append(graph)
                per_structure_graph[structure] = graph
                local_proofs = proof_profile_rows(fixture)
                proof_rows.extend(local_proofs)
                summary = {
                    "pair_id": fixture.pair_id,
                    "structure": structure,
                    "n": fixture.n,
                    **aggregate_proof_rows(local_proofs),
                }
                proof_summary.append(summary)
                per_structure_proof[structure] = summary

                compile_started = time.perf_counter()
                polynomials, polynomial_diagnostics = value_polynomials(
                    fixture, references, Fraction(int(config["revenue"])), Fraction(str(config["lambda"])),
                )
                polynomial_compile_seconds = time.perf_counter() - compile_started
                component_started = time.perf_counter()
                components = value_components(
                    fixture, references, Fraction(int(config["revenue"])), Fraction(str(config["lambda"])),
                )
                component_build_seconds = time.perf_counter() - component_started
                masks = validation_masks(fixture.n, fixture.seed, config["random_value_masks"])

                for diagnostic in polynomial_diagnostics:
                    value_name = diagnostic["value_name"]
                    dnf_rows = components[value_name]
                    unique_dnfs = {normalized_dnf_key(dnf) for _coefficient, dnf, _label in dnf_rows}
                    decomposition_rows.append(
                        {
                            "pair_id": fixture.pair_id,
                            "structure": structure,
                            "n": fixture.n,
                            **diagnostic,
                            "raw_boolean_components": len(dnf_rows),
                            "unique_boolean_components": len(unique_dnfs),
                            "raw_component_clauses": sum(len(dnf) for _coefficient, dnf, _label in dnf_rows),
                            "polynomial_compile_seconds_shared": polynomial_compile_seconds,
                            "component_build_seconds_shared": component_build_seconds,
                        }
                    )
                    poly_max_error = Fraction(0)
                    component_max_error = Fraction(0)
                    for mask in masks:
                        expected = value_from_report(
                            fixture, mask, value_name, references,
                            Fraction(int(config["revenue"])), Fraction(str(config["lambda"])),
                        )
                        poly_max_error = max(poly_max_error, abs(poly_value(polynomials[value_name], mask) - expected))
                        component_max_error = max(component_max_error, abs(component_value(dnf_rows, mask) - expected))
                    validation_rows.append(
                        {
                            "pair_id": fixture.pair_id,
                            "structure": structure,
                            "n": fixture.n,
                            "value_name": value_name,
                            "masks_checked": len(masks),
                            "polynomial_value_max_error": float(poly_max_error),
                            "boolean_component_value_max_error": float(component_max_error),
                            "status": "VERIFIED" if not poly_max_error and not component_max_error else "FAILED_CORRECTNESS",
                        }
                    )

                    sparse_allocation, sparse_metrics = sparse_harsanyi_allocation(fixture, polynomials[value_name])
                    lex_allocation, lex_metrics = lexashap_component_allocation(fixture, dnf_rows)
                    method_difference = float(np.max(np.abs(sparse_allocation - lex_allocation)))
                    for allocation, metrics in ((sparse_allocation, sparse_metrics), (lex_allocation, lex_metrics)):
                        error = oracle_error(oracle, fixture, value_name, allocation)
                        efficiency = abs(float(np.sum(allocation)) - float(poly_value(polynomials[value_name], (1 << fixture.n) - 1)))
                        status = "VERIFIED" if (error is None or error <= config["tolerance"]) and efficiency <= config["tolerance"] else "FAILED_CORRECTNESS"
                        baseline_rows.append(
                            {
                                "pair_id": fixture.pair_id,
                                "structure": structure,
                                "n": fixture.n,
                                "value_name": value_name,
                                "oracle_available": error is not None,
                                "oracle_max_abs_error": error,
                                "efficiency_error": efficiency,
                                "cross_method_max_abs_difference": method_difference,
                                "source_polynomial_compile_seconds": polynomial_compile_seconds,
                                "source_component_build_seconds": component_build_seconds,
                                **metrics,
                                "status": status,
                            }
                        )
                        for player, shapley in zip(player_rows(fixture), allocation, strict=True):
                            allocation_rows.append(
                                {
                                    "pair_id": fixture.pair_id,
                                    "structure": structure,
                                    "n": fixture.n,
                                    "value_name": value_name,
                                    "method": metrics["method"],
                                    "player_id": player["player_id"],
                                    "relation": player["relation"],
                                    "shapley": float(shapley),
                                }
                            )
                    log.emit(
                        "baseline_verified",
                        pair_id=fixture.pair_id,
                        structure=structure,
                        value_name=value_name,
                        sparse_terms=len(polynomials[value_name]),
                        boolean_components=len(unique_dnfs),
                        method_difference=method_difference,
                    )

                if fixture.pair_id in config["h3_profiles"]:
                    profile = evidence_layer_profile(fixture, config["h3_state_cap"])
                    layer_rows.extend(profile)
                    per_structure_layers[structure] = [row["states"] for row in profile]

            pair_invariance_rows.append(
                {
                    "pair_id": spec["pair_id"],
                    "n": spec["n"],
                    "degree_signature_equal": per_structure_graph["low"]["enterprise_degree_signature"] == per_structure_graph["high"]["enterprise_degree_signature"],
                    "incidence_treewidth_equal": per_structure_graph["low"]["incidence_treewidth_exact"] == per_structure_graph["high"]["incidence_treewidth_exact"],
                    "primal_treewidth_equal": per_structure_graph["low"]["primal_treewidth_exact"] == per_structure_graph["high"]["primal_treewidth_exact"],
                    "conserved_degree_total_equal": per_structure_proof["low"]["conserved_degree_total"] == per_structure_proof["high"]["conserved_degree_total"],
                    "h3_layer_sizes_equal": (
                        per_structure_layers.get("low") == per_structure_layers.get("high")
                        if per_structure_layers else None
                    ),
                    "low_local_or_terms": per_structure_proof["low"]["local_or_terms"],
                    "high_local_or_terms": per_structure_proof["high"]["local_or_terms"],
                    "low_cross_same_entity_terms": per_structure_proof["low"]["same_entity_cross_product_terms"],
                    "high_cross_same_entity_terms": per_structure_proof["high"]["same_entity_cross_product_terms"],
                    "low_cross_shared_enterprises": per_structure_proof["low"]["cross_shared_enterprises"],
                    "high_cross_shared_enterprises": per_structure_proof["high"]["cross_shared_enterprises"],
                }
            )
            log.emit("pair_complete", pair_id=spec["pair_id"], n=spec["n"])
    except Exception as exc:
        fatal = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        log.emit("diagnosis_failed", **fatal)

    write_csv(results_dir / "lineage_structure.csv", structure_rows)
    write_csv(results_dir / "proof_profiles.csv", proof_rows)
    write_csv(results_dir / "proof_profile_summary.csv", proof_summary)
    write_csv(results_dir / "pair_structure_invariance.csv", pair_invariance_rows)
    write_csv(results_dir / "value_decomposition.csv", decomposition_rows)
    write_csv(results_dir / "value_validation.csv", validation_rows)
    write_csv(results_dir / "exact_baseline_results.csv", baseline_rows)
    write_csv(results_dir / "exact_allocations.csv", allocation_rows)
    write_csv(results_dir / "h3_layer_growth.csv", layer_rows)
    write_csv(results_dir / "micro_structure_controls.csv", micro_control_rows())

    failed = [row for row in validation_rows if row["status"] != "VERIFIED"]
    failed.extend(row for row in baseline_rows if row["status"] != "VERIFIED")
    status = "FAILED_CORRECTNESS" if fatal or failed else "VERIFIED"
    summary = {
        "run_id": run_id,
        "status": status,
        "scales": len(config["scales"]),
        "fixtures": len(structure_rows),
        "value_validations": len(validation_rows),
        "baseline_cells": len(baseline_rows),
        "correctness_failures": len(failed),
        "fatal": fatal,
        "elapsed_seconds": time.perf_counter() - started,
        "material_passport": {
            "artifact_id": "IDEA03-2-PREVIOUS-EXPLORATION-DIAGNOSIS-V1",
            "artifact_type": "structural diagnosis and exact baseline experiment",
            "origin_mode": "academic-research-suite/experiment-agent run+validate",
            "evidence_scope": "local frozen fixtures and local official LExaShap source",
        },
    }
    write_json(run_dir / "diagnosis_status.json", summary)
    log.emit("diagnosis_finished", **summary)
    return 0 if status == "VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
