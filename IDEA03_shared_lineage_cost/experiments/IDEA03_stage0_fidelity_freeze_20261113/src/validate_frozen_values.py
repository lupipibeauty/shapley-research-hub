from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path


HUB = Path(__file__).resolve().parents[4]
PRIOR = (
    HUB
    / "IDEA03_shared_lineage_cost"
    / "experiments"
    / "IDEA03_2_shared_compilation_tpch_v1"
)
sys.path.insert(0, str(PRIOR / "src"))

from study import (  # noqa: E402
    build_threshold2_game,
    mobius_from_values,
    player_region_support,
    shapley_from_values,
)
from joint_game import METRICS, NODES, report_python  # noqa: E402


OUT = Path(__file__).resolve().parents[1] / "results"
CONFIG = Path(__file__).resolve().parents[1] / "config" / "frozen_value_function.json"

LEVELS = {
    "national": ("NAT",),
    "province": ("PA", "PB"),
    "city": ("A1", "A2", "B1", "B2"),
}
FAMILIES = {
    "counts": ("enterprise_count", "site_count"),
    "sums": ("workers", "mfg_workers"),
    "ratio": ("mfg_share",),
}


def frac(text: str | int) -> Fraction:
    return Fraction(text)


def coordinate_weights(level_weights: dict[str, str], family_weights: dict[str, str]):
    result: dict[tuple[str, str], Fraction] = {}
    for level, nodes in LEVELS.items():
        for family, metrics in FAMILIES.items():
            weight = frac(level_weights[level]) / len(nodes) * frac(family_weights[family]) / len(metrics)
            for node in nodes:
                for metric in metrics:
                    result[(node, metric)] = weight
    assert sum(result.values(), Fraction(0)) == 1
    return result


def coordinate_scale(metric: str, target) -> Fraction:
    if metric == "mfg_share":
        return Fraction(1)
    assert target is not None
    return max(Fraction(1), abs(Fraction(target)))


def coordinate_loss(candidate, target, scale: Fraction) -> Fraction:
    if candidate is None and target is None:
        return Fraction(0)
    if candidate is None or target is None:
        return Fraction(1)
    return abs(Fraction(candidate) - Fraction(target)) / scale


def fidelity_values(reports, weights, target):
    empty = reports[0]
    baseline = sum(
        weights[c] * coordinate_loss(empty[c], target[c], coordinate_scale(c[1], target[c]))
        for c in weights
    )
    values = []
    for report in reports:
        loss = sum(
            weights[c] * coordinate_loss(report[c], target[c], coordinate_scale(c[1], target[c]))
            for c in weights
        )
        values.append(baseline - loss)
    return values, baseline


def gap_values(reports, target):
    target_a = target[("PA", "mfg_share")]
    target_b = target[("PB", "mfg_share")]
    if target_a is None or target_b is None:
        raise ValueError("The frozen joint benchmark requires both target province shares.")
    target_gap = Fraction(target_a) - Fraction(target_b)

    def loss(report):
        a = report[("PA", "mfg_share")]
        b = report[("PB", "mfg_share")]
        if a is None or b is None:
            return Fraction(1)
        return abs((Fraction(a) - Fraction(b)) - target_gap) / 2

    baseline = loss(reports[0])
    return [baseline - loss(report) for report in reports], baseline, target_gap


def negative_marginals(values, n):
    count = 0
    for player in range(n):
        bit = 1 << player
        count += sum(values[mask | bit] < values[mask] for mask in range(1 << n) if not mask & bit)
    return count


def cross_mixed_differences(game, values):
    support = player_region_support(game)
    pa = [i for i, regions in support.items() if regions == {"PA"}]
    pb = [i for i, regions in support.items() if regions == {"PB"}]
    nonzero = 0
    magnitudes = Counter()
    for i in pa:
        for j in pb:
            bits = (1 << i) | (1 << j)
            for mask in range(1 << game.n):
                if mask & bits:
                    continue
                delta = values[mask | bits] - values[mask | (1 << i)] - values[mask | (1 << j)] + values[mask]
                if delta:
                    nonzero += 1
                    magnitudes[str(delta)] += 1
    return nonzero, magnitudes


def coordinate_decomposition_check(reports, weights, target, overall_values, n):
    empty = reports[0]
    reconstructed = [Fraction(0) for _ in reports]
    coordinate_phi = [Fraction(0) for _ in range(n)]
    rows = []
    for coordinate, weight in weights.items():
        scale = coordinate_scale(coordinate[1], target[coordinate])
        baseline = coordinate_loss(empty[coordinate], target[coordinate], scale)
        component = [
            weight * (baseline - coordinate_loss(report[coordinate], target[coordinate], scale))
            for report in reports
        ]
        reconstructed = [left + right for left, right in zip(reconstructed, component)]
        phi = shapley_from_values(component, n)
        coordinate_phi = [left + right for left, right in zip(coordinate_phi, phi)]
        rows.append(
            {
                "node": coordinate[0],
                "metric": coordinate[1],
                "weight": str(weight),
                "scale": str(scale),
                "empty_loss": str(baseline),
                "component_full_value": str(component[-1]),
            }
        )
    overall_phi = shapley_from_values(overall_values, n)
    assert reconstructed == overall_values
    assert coordinate_phi == overall_phi
    return rows, overall_phi


def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def value_summary(name, values, allocation, game):
    mobius = mobius_from_values(values, game.n)
    cross_count, _ = cross_mixed_differences(game, values)
    return {
        "value": name,
        "v_empty": str(values[0]),
        "v_full": str(values[-1]),
        "distinct_values": len(set(values)),
        "nonzero_coalitions": sum(value != 0 for value in values),
        "full_only_nonzero": sum(value != 0 for value in values) == 1,
        "negative_marginals": negative_marginals(values, game.n),
        "negative_shapley_players": sum(value < 0 for value in allocation),
        "cross_region_nonzero_mixed_differences": cross_count,
        "harsanyi_terms": len(mobius),
        "maximum_harsanyi_degree": max((mask.bit_count() for mask in mobius), default=0),
        "efficiency_error": str(sum(allocation, Fraction(0)) - values[-1]),
    }


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    game = build_threshold2_game()
    reports = [report_python(game, mask) for mask in range(1 << game.n)]
    target = reports[-1]

    weight_sets = {
        "v_fid_main": coordinate_weights(
            config["main_value"]["hierarchy_weights"],
            config["main_value"]["family_weights"],
        ),
        **{
            name: coordinate_weights(spec["hierarchy_weights"], spec["family_weights"])
            for name, spec in config["sensitivity_values"].items()
        },
    }

    summaries = []
    allocation_rows = []
    coordinate_rows = []
    for name, weights in weight_sets.items():
        values, baseline_loss = fidelity_values(reports, weights, target)
        if name == "v_fid_main":
            rows, allocation = coordinate_decomposition_check(reports, weights, target, values, game.n)
            coordinate_rows = rows
        else:
            allocation = shapley_from_values(values, game.n)
        summary = value_summary(name, values, allocation, game)
        summary["empty_to_target_loss"] = str(baseline_loss)
        summaries.append(summary)
        for player, phi in zip(game.players, allocation):
            allocation_rows.append(
                {
                    "value": name,
                    "player_index": player.index,
                    "player_id": player.player_id,
                    "relation": player.relation,
                    "shapley_fraction": str(phi),
                    "shapley": float(phi),
                    "revenue_R1000": float(phi * 1000 / values[-1]),
                }
            )

    gap, gap_baseline, target_gap = gap_values(reports, target)
    gap_phi = shapley_from_values(gap, game.n)
    gap_summary = value_summary("v_gap_PA_PB_mfg_share", gap, gap_phi, game)
    gap_summary["empty_to_target_loss"] = str(gap_baseline)
    gap_summary["target_gap"] = str(target_gap)
    summaries.append(gap_summary)
    for player, phi in zip(game.players, gap_phi):
        allocation_rows.append(
            {
                "value": "v_gap_PA_PB_mfg_share",
                "player_index": player.index,
                "player_id": player.player_id,
                "relation": player.relation,
                "shapley_fraction": str(phi),
                "shapley": float(phi),
                "revenue_R1000": float(phi * 1000 / gap[-1]),
            }
        )

    full_report_rows = []
    for node in NODES:
        for metric in METRICS:
            value = target[(node, metric)]
            full_report_rows.append(
                {
                    "node": node,
                    "metric": metric,
                    "full_value": "NULL" if value is None else str(value),
                    "main_weight": str(weight_sets["v_fid_main"][(node, metric)]),
                    "scale": str(coordinate_scale(metric, value)),
                }
            )

    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "value_validity_summary.csv", summaries)
    write_csv(OUT / "shapley_allocations.csv", allocation_rows)
    write_csv(OUT / "coordinate_decomposition.csv", coordinate_rows)
    write_csv(OUT / "full_report_and_scales.csv", full_report_rows)
    write_csv(
        OUT / "player_mapping.csv",
        [
            {
                "player_index": p.index,
                "player_id": p.player_id,
                "relation": p.relation,
                "key": p.key,
            }
            for p in game.players
        ],
    )

    artifact_paths = [
        CONFIG,
        Path(__file__).resolve(),
        OUT / "value_validity_summary.csv",
        OUT / "shapley_allocations.csv",
        OUT / "coordinate_decomposition.csv",
        OUT / "full_report_and_scales.csv",
        OUT / "player_mapping.csv",
    ]

    manifest = {
        "status": "VERIFIED_STAGE0",
        "game_id": "FID_F0_N12",
        "source_fixture": game.game_id,
        "query_version": game.query_version,
        "players": game.n,
        "coalitions": 1 << game.n,
        "structured_solver_read_truth_table": False,
        "purpose": "Stage-0 mathematical validity oracle only; no performance claim.",
        "python": sys.version,
        "platform": platform.platform(),
        "config_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
        "source_module": str((PRIOR / "src" / "study.py").relative_to(HUB)),
        "report_module": str(
            (PRIOR.parent / "IDEA03_2_joint_value_deepening_v1" / "src" / "joint_game.py").relative_to(HUB)
        ),
        "artifacts_sha256": {
            str(path.relative_to(Path(__file__).resolve().parents[1])): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in artifact_paths
        },
        "summaries": summaries,
    }
    (OUT / "validation_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
