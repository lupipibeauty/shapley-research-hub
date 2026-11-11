from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "v4_0" / "AB_N2_AB_J1_2026_10_31"


def load(relative: str):
    return json.loads((OUT / relative).read_text(encoding="utf-8"))


def csv_rows(relative: str) -> int:
    with (OUT / relative).open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def main() -> None:
    manifest = load("manifest.json")
    n1 = load("AB_N1_SUPPLEMENT/audit.json")
    n2 = load("AB_N2/result.json")
    j1 = load("AB_J1/result.json")
    n4 = load("AB_N4_STRUCTURE_AUDIT/audit.json")
    checks = {
        "manifest_scope": manifest["status"] == "COMPLETED_AB_N2_AND_AB_J1_ONLY",
        "historical_n1_unchanged": manifest["historical_ab_n1_hashes_before"] == manifest["historical_ab_n1_hashes_after"],
        "n1_sql_rows_4096": n1["sql_rows_returned"] == 4096,
        "n1_raw_null_count_1024": n1["raw_sum_null_count"] == 1024,
        "n1_value_errors_zero": n1["maximum_count_error"] == 0 and n1["maximum_normalized_sum_error"] == 0,
        "n2_components_84": n2["component_count_total"] == 84,
        "n2_component_breakdown": n2["component_counts"] == {
            "record_count": 36,
            "attribute_present_count": 30,
            "category_a_target_count": 18,
        },
        "n2_errors_zero": n2["maximum_coalition_value_error"] == 0 and n2["maximum_payment_error"] == 0,
        "n2_grounding_rows_36": csv_rows("AB_N2/grounding.csv") == 36,
        "n2_alliance_validation_rows_86016": csv_rows("AB_N2/alliance_node_validation.csv") == 86016,
        "n2_shapley_rows_252": csv_rows("AB_N2/shapley_comparison.csv") == 252,
        "j1_bag_distinct_activated": j1["full_coalition_values"] == {
            "COUNT_STAR": 2,
            "COUNT_DISTINCT_KEY": 1,
            "BOOLEAN_TUPLE": 1,
        },
        "j1_payment_error_zero": j1["maximum_payment_error"] == 0,
        "j1_alliance_rows_8": csv_rows("AB_J1/alliance_validation.csv") == 8,
        "j1_shapley_rows_9": csv_rows("AB_J1/shapley_comparison.csv") == 9,
        "n4_identity_exact": n4["maximum_exact_identity_error"] == "0/1",
        "n4_no_full_adaptation": n4["full_n4_adaptation_executed"] is False,
        "n4_max_states_49": n4["maximum_reachable_count_states"] == 49,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise AssertionError(f"验证失败: {failed}")
    result = {"status": "ALL_CHECKS_PASSED", "checks": checks, "check_count": len(checks)}
    (OUT / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
