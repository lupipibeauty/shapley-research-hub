from __future__ import annotations

import csv
import hashlib
import json
import platform
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent
P3_0 = ROOT.parent / "P3_0"
sys.path.insert(0, str(ROOT / "src"))
from threshold_lineage import coalition_wins, entity_witnesses, exact_shapley_from_winners, load_fixture, minimal_winning_coalitions, winner_rows  # noqa: E402

OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader(); writer.writerows(rows)


def main() -> None:
    fixture_path = P3_0 / "fixtures" / "anchor_13_players.json"
    truth_path = P3_0 / "results" / "anchor_truth.csv"
    g1_path = P3_0 / "results" / "record_shapley.csv"
    fixture = load_fixture(fixture_path)
    n = 13
    players = {r["player_index"]: r for rows in (fixture["entities"], fixture["links"], fixture["attributes"]) for r in rows}
    player_ids = {i: row["player_id"] for i, row in players.items()}

    # Algorithm input: only the original fixture and direct JOIN-witness construction.
    group_of, witnesses = entity_witnesses(fixture)
    winner_map = {t: minimal_winning_coalitions(group_of, witnesses, t) for t in (1, 2)}
    assert (len(winner_map[1]), len(winner_map[2])) == (9, 4)
    write_csv(OUT / "minimal_winning_coalitions.csv", [r for t in (1, 2) for r in winner_rows(winner_map[t], player_ids, t)])

    shapley = {t: exact_shapley_from_winners(n, winner_map[t]) for t in (1, 2)}
    write_csv(OUT / "threshold_shapley.csv", [
        {"threshold": f"H{t}", "player_index": i, "player_id": player_ids[i],
         "shapley_fraction": str(shapley[t][i]), "shapley_decimal": float(shapley[t][i]), "sum_check": str(sum(shapley[t]))}
        for t in (1, 2) for i in range(n)
    ])

    # Oracle is intentionally opened after the results above are fixed.
    truth_rows = list(csv.DictReader(truth_path.open(encoding="utf-8-sig")))
    oracle_rows = []
    for row in truth_rows:
        mask, qa, qb = int(row["mask"]), int(row["q_A_sql"]), int(row["q_B_sql"])
        h1, h2 = coalition_wins(mask, winner_map[1]), coalition_wins(mask, winner_map[2])
        e1, e2 = int(qa >= 1 and qb >= 1), int(qa >= 2 and qb >= 2)
        matched = h1 == e1 and h2 == e2 and h1 + h2 == int(row["G1"])
        oracle_rows.append({"mask": mask, "q_A": qa, "q_B": qb, "G1_oracle": row["G1"], "H1_witness": h1, "H1_oracle": e1, "H2_witness": h2, "H2_oracle": e2, "sum_H": h1 + h2, "exact_match": matched})
    assert all(r["exact_match"] for r in oracle_rows)
    write_csv(OUT / "oracle_validation.csv", oracle_rows)

    g1 = {int(r["player_index"]): Fraction(r["shapley_fraction"]) for r in csv.DictReader(g1_path.open(encoding="utf-8-sig")) if r["game_id"] == "G1"}
    decomposition = []
    for i in range(n):
        total = shapley[1][i] + shapley[2][i]
        decomposition.append({"player_index": i, "player_id": player_ids[i], "H1_fraction": str(shapley[1][i]), "H2_fraction": str(shapley[2][i]), "H1_plus_H2_fraction": str(total), "P3_0_G1_fraction": str(g1[i]), "absolute_error": str(abs(total - g1[i])), "exact_match": total == g1[i]})
    assert all(r["exact_match"] for r in decomposition)
    assert sum(shapley[1]) + sum(shapley[2]) == Fraction(2)
    write_csv(OUT / "g1_shapley_decomposition.csv", decomposition)

    manifest = {"stage": "P3_1B_PREPARATION_COMPLETED_AND_PAUSED", "new_algorithm_developed": False,
                "method": "fixture JOIN-witness minimal winners + exact subset Shapley", "truth_input_used_for_generation": False, "oracle_used_after_generation": True,
                "n_players": n, "coalitions_for_validation": 1 << n, "minimal_winner_counts": {"H1": 9, "H2": 4}, "oracle_alliance_match": True, "shapley_decomposition_match": True,
                "source_inputs": {"fixture": {"path": str(fixture_path), "sha256": sha256(fixture_path)}, "oracle": {"path": str(truth_path), "sha256": sha256(truth_path)}, "g1": {"path": str(g1_path), "sha256": sha256(g1_path)}},
                "environment": {"python": sys.version, "platform": platform.platform()}, "outputs": {p.name: sha256(p) for p in OUT.glob("*.csv")}}
    (OUT / "P3_1B_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
