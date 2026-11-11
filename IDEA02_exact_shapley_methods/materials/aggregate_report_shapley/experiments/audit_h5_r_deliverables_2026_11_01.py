from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from aggregate_report_shapley.h5_shared import exact_b0  # noqa: E402
from run_h5_r_shared_all_players_2026_11_01 import (  # noqa: E402
    build_games,
    v1_coordinate_decomposition,
)


OUT = ROOT / "outputs" / "v4_0" / "H5_R_2026_11_01"


def read_csv(name: str) -> list[dict[str, str]]:
    with (OUT / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    payments = read_csv("record_shapley_validation.csv")
    if not any(row["method"] == "V1_COORDINATE_DECOMPOSITION" for row in payments):
        games, spec, suite = build_games()
        game = next(item for item in games if item.game_id == "D1P_V1")
        truth, _ = exact_b0(game)
        allocation, _ = v1_coordinate_decomposition(spec, suite)
        for player, (estimate, expected) in enumerate(zip(allocation, truth, strict=True)):
            payments.append(
                {
                    "game_id": "D1P_V1",
                    "method": "V1_COORDINATE_DECOMPOSITION",
                    "player": game.player_ids[player],
                    "shapley": repr(estimate),
                    "B0_truth": repr(expected),
                    "absolute_error": repr(abs(estimate - expected)),
                }
            )
        with (OUT / "record_shapley_validation.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(payments[0]))
            writer.writeheader()
            writer.writerows(payments)

    correctness = read_csv("correctness_audit.csv")
    predecessor = read_csv("predecessor_weight_audit.csv")
    summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    expected_files = (
        "raw_performance.csv",
        "performance_summary.csv",
        "resource_tier_attempts.csv",
        "record_shapley_validation.csv",
        "input_preprocessing_summary.csv",
        "method_boundary_records.csv",
        "historical_hashes.json",
    )
    figures = list((OUT / "figures").glob("*.png")) + list((OUT / "figures").glob("*.svg"))
    audit = {
        "status": "PASS",
        "correctness_rows": len(correctness),
        "all_correctness_passed": len(correctness) == 29
        and all(row["passes_1e_9"].lower() == "true" for row in correctness),
        "record_payment_rows": len(payments),
        "expected_record_payment_rows": 376,
        "predecessor_audit_rows": len(predecessor),
        "all_predecessor_audits_passed": len(predecessor) == 52
        and all(row["passes"].lower() == "true" for row in predecessor),
        "summary_completed": summary["status"] == "H5_R_COMPLETED_AND_PAUSED",
        "historical_files_unchanged": summary["historical_files_unchanged"],
        "expected_files_present": all((OUT / name).is_file() for name in expected_files),
        "figure_files": len(figures),
    }
    if not all(
        (
            audit["all_correctness_passed"],
            audit["record_payment_rows"] == audit["expected_record_payment_rows"],
            audit["all_predecessor_audits_passed"],
            audit["summary_completed"],
            audit["historical_files_unchanged"],
            audit["expected_files_present"],
            audit["figure_files"] == 6,
        )
    ):
        audit["status"] = "FAIL"
        raise AssertionError(audit)
    (OUT / "deliverable_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
