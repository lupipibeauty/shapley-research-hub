"""Generate a narrowly scoped Luo R2 adapter fixture from the frozen H3-JV J2 witness.

The official Luo binary only accepts its built-in TPC-H join plan.  This script
therefore embeds each H3 J2 grounding as one isolated TPC-H join chain.  It
tests the RDSV backend on the same grounding-player Boolean games for additive
bag/count statistics; it does not claim to adapt DISTINCT or nonlinear V1/V2.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
PROJECT = ROOT / "aggregate_report_shapley"
sys.path.insert(0, str(PROJECT / "src"))

from aggregate_report_shapley.h3_jv import (  # noqa: E402
    NODES,
    PLAYERS,
    ancestors,
    generate_instance,
    groundings,
    player_index,
)

OUT = ROOT / "tmp" / "researchlab_v2" / "workspace" / "BRBD_v1" / "runs" / "R2_h3_j2_luo"
DATA = OUT / "datasets"

TABLE_HEADERS = {
    "region": ["r_regionkey"],
    "nation": ["n_nationkey", "n_regionkey"],
    "supplier": ["s_suppkey", "s_nationkey"],
    "partsupp": ["ps_partkey", "ps_suppkey"],
    "part": ["p_partkey"],
    "lineitem": ["l_partkey", "l_suppkey", "l_orderkey"],
    "orders": ["o_orderkey", "o_custkey"],
    "customer": ["c_custkey"],
}


def write_fixture(name: str, selected: list[tuple[object, int]], manifest_row: dict) -> None:
    root = DATA / name
    source = root / "data"
    assignment = root / "assignment"
    source.mkdir(parents=True, exist_ok=True)
    assignment.mkdir(parents=True, exist_ok=True)

    rows: dict[str, list[dict[str, int]]] = defaultdict(list)
    owners: dict[str, list[int]] = defaultdict(list)
    idx = 0
    for item, weight in selected:
        for _ in range(weight):
            clause = sorted(item.clause)
            # Use one isolated chain per grounding. Repeating the last owner on
            # auxiliary tables preserves exactly the same owner conjunction.
            chain_owners = (clause + [clause[-1]] * 3)[:3]
            key = 100000 + idx
            values = {
                "region": {"r_regionkey": key},
                "nation": {"n_nationkey": key, "n_regionkey": key},
                "supplier": {"s_suppkey": key, "s_nationkey": key},
                "partsupp": {"ps_partkey": key, "ps_suppkey": key},
                "part": {"p_partkey": key},
                "lineitem": {"l_partkey": key, "l_suppkey": key, "l_orderkey": key},
                "orders": {"o_orderkey": key, "o_custkey": key},
                "customer": {"c_custkey": key},
            }
            for table, row in values.items():
                rows[table].append(row)
            # Region, nation, supplier carry the three clause owners. Remaining
            # tables repeat the third owner, so the joined row has exactly clause.
            table_owner = {
                "region": chain_owners[0],
                "nation": chain_owners[1],
                "supplier": chain_owners[2],
                "partsupp": chain_owners[2],
                "part": chain_owners[2],
                "lineitem": chain_owners[2],
                "orders": chain_owners[2],
                "customer": chain_owners[2],
            }
            for table in values:
                owners[table].append(table_owner[table])
            idx += 1

    for table, header in TABLE_HEADERS.items():
        with (source / f"{table}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows[table])
        row_ids = list(range(len(rows[table])))
        index = {str(i): i for i in row_ids}
        # Store row-wise assignments; the official loader expects the separate
        # *-index.json file to be a list of row IDs.
        owner = {str(i): int(v) for i, v in enumerate(owners[table])}
        (assignment / f"{table}-index.json").write_text(json.dumps(row_ids), encoding="utf-8")
        (assignment / f"{table}-owner.json").write_text(
            json.dumps({"index": index, "owner": owner}, separators=(",", ":")),
            encoding="utf-8",
        )

    manifest_row["dataset_dir"] = str(root)


def exact_additive_shapley(selected: list[tuple[object, int]]) -> list[float]:
    result = [0.0] * len(PLAYERS)
    for item, weight in selected:
        share = float(weight) / len(item.clause)
        for p in item.clause:
            result[p] += share
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    instance = generate_instance(7301)
    items = groundings(instance, "J2")
    manifest: list[dict] = []
    for node in NODES:
        for metric in ("bag_count", "amount_sum", "target_count"):
            selected: list[tuple[object, int]] = []
            for item in items:
                if node not in ancestors(item.leaf):
                    continue
                if metric == "bag_count":
                    weight = 1
                elif metric == "amount_sum":
                    weight = int(item.amount)
                else:
                    if item.category != "C1":
                        continue
                    weight = 1
                selected.append((item, weight))
            name = f"J2_{node}_{metric}"
            row = {
                "dataset": name,
                "join_id": "J2",
                "node": node,
                "metric": metric,
                "groundings": len(selected),
                "weight_sum": sum(w for _, w in selected),
                "player_count": len(PLAYERS),
                "expected_shapley": exact_additive_shapley(selected),
                "clauses": [sorted(item.clause) for item, _ in selected],
            }
            write_fixture(name, selected, row)
            manifest.append(row)
    (OUT / "fixture_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (OUT / "fixture_manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["dataset", "join_id", "node", "metric", "groundings", "weight_sum", "player_count", "dataset_dir"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in manifest:
            writer.writerow({key: row.get(key, "") for key in fields})
    print(f"generated={len(manifest)} datasets at {OUT}")


if __name__ == "__main__":
    main()
