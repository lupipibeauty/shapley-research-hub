"""Build the minimal J2 DISTINCT control game for the Luo R2 audit."""
from __future__ import annotations

import csv
import json
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "tmp/researchlab_v2/workspace/BRBD_v1/scripts"))
import generate_h3_j2_luo_r2 as _generator  # noqa: E402
write_fixture = _generator.write_fixture

OUT = ROOT / "tmp" / "researchlab_v2" / "workspace" / "BRBD_v1" / "runs" / "R2_h3_j2_distinct"
DATA = OUT / "relations"
_generator.DATA = OUT / "datasets"
PLAYERS = [0, 1, 4, 8, 9]
CLAUSES = [{0, 4, 8}, {1, 4, 9}]


def exact_or_shapley() -> dict[str, float]:
    n = len(PLAYERS)
    pos = {p: i for i, p in enumerate(PLAYERS)}
    vals = {}
    for mask in range(1 << n):
        coalition = {PLAYERS[i] for i in range(n) if mask & (1 << i)}
        vals[mask] = float(any(c <= coalition for c in CLAUSES))
    result = {str(p): 0.0 for p in PLAYERS}
    import math
    for i, p in enumerate(PLAYERS):
        bit = 1 << i
        for mask in range(1 << n):
            if mask & bit:
                continue
            size = mask.bit_count()
            w = 1.0 / (n * math.comb(n - 1, size))
            result[str(p)] += w * (vals[mask | bit] - vals[mask])
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    relations = {
        "R": [("X1", 0), ("X2", 1)],
        "S": [("X1", "Y1", "K1", 4), ("X2", "Y2", "K1", 4)],
        "T": [("Y1", 8), ("Y2", 9)],
    }
    for name, rows in relations.items():
        with (DATA / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if name == "R":
                w.writerow(["x", "player"])
            elif name == "S":
                w.writerow(["x", "y", "key", "player"])
            else:
                w.writerow(["y", "player"])
            w.writerows(rows)
    with (OUT / "distinct.sql").open("w", encoding="utf-8") as f:
        f.write("""-- J2 DISTINCT control: two grounding paths share business key K1
WITH j AS (
  SELECT r.x, s.y, s.key, r.player AS r_player, s.player AS s_player, t.player AS t_player
  FROM read_csv_auto('R.csv') r
  JOIN read_csv_auto('S.csv') s ON r.x=s.x
  JOIN read_csv_auto('T.csv') t ON s.y=t.y
)
SELECT COUNT(*) AS q1_bag, COUNT(DISTINCT key) AS q2_distinct FROM j;
""")
    expected = exact_or_shapley()
    (OUT / "source_expression.json").write_text(json.dumps({
        "q1_count_star": [sorted(c) for c in CLAUSES],
        "q2_count_distinct": {"K1": [sorted(c) for c in CLAUSES]},
        "players": PLAYERS,
        "full_q1": 2,
        "full_q2": 1,
        "exact_q2_shapley": expected,
    }, indent=2), encoding="utf-8")

    # Reuse the official-plan embedding for Q1. Q2 is intentionally not sent
    # to the official backend because its native frontend has no OR grouping.
    class Item:
        def __init__(self, clause):
            self.clause = frozenset(clause)
    selected = [(Item(c), 1) for c in CLAUSES]
    fixture_manifest = {}
    write_fixture("J2_DISTINCT_Y1_Q1_BAG", selected, fixture_manifest)
    (OUT / "fixture_manifest.json").write_text(json.dumps({
        "dataset_dir": fixture_manifest["dataset_dir"],
        "official_target": "Q1_COUNT_STAR",
        "q2_target": "Q2_COUNT_DISTINCT",
        "q1_full": 2,
        "q2_full": 1,
    }, indent=2), encoding="utf-8")
    print(json.dumps({"q1_full": 2, "q2_full": 1, "exact_q2_shapley": expected}, indent=2))


if __name__ == "__main__":
    main()
