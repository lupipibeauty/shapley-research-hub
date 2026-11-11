#!/usr/bin/env python3
"""Generate Luo et al. TPC-H CSV inputs with DuckDB's official TPC-H extension.

This is an independently written Windows compatibility adapter.  It does not
replace or modify the authors' ``tpch-dbgen.sh`` and must not be reported as an
unmodified R1 data-generation run.  The generated relations implement the same
TPC-H scale-factor semantics and are checked against the row counts frozen in
the authors' ``scripts/config.cfg``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import time
from pathlib import Path

import duckdb


TABLES = [
    "customer",
    "lineitem",
    "nation",
    "orders",
    "part",
    "partsupp",
    "region",
    "supplier",
]

# The author transform script uses three historical spellings that differ from
# DuckDB's conventional TPC-H column names.  Preserve the author-facing schema.
EXPORT_SQL = {
    "customer": "SELECT * FROM customer",
    "lineitem": """
        SELECT l_orderkey, l_partkey, l_suppkey, l_linenumber, l_quantity,
               l_extendedprice, l_discount, l_tax, l_returnflag, l_linestatus,
               l_shipdate, l_commitdate AS l_commitdata,
               l_receiptdate AS l_receiptdata, l_shipinstruct, l_shipmode,
               l_comment
        FROM lineitem
    """,
    "nation": "SELECT * FROM nation",
    "orders": """
        SELECT o_orderkey, o_custkey, o_orderstatus, o_totalprice,
               o_orderdate AS o_orderdata, o_orderpriority, o_clerk,
               o_shippriority, o_comment
        FROM orders
    """,
    "part": "SELECT * FROM part",
    "partsupp": "SELECT * FROM partsupp",
    "region": "SELECT * FROM region",
    "supplier": "SELECT * FROM supplier",
}

SF1_EXPECTED_ROWS = {
    "customer": 150_000,
    "lineitem": 6_001_215,
    "nation": 25,
    "orders": 1_500_000,
    "part": 200_000,
    "partsupp": 800_000,
    "region": 5,
    "supplier": 10_000,
}


def sha256(path: Path, block_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--extension-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.database.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)

    started_wall = time.time()
    started_perf = time.perf_counter()
    con = duckdb.connect(str(args.database))
    con.execute(f"SET extension_directory='{args.extension_dir.as_posix()}'")
    con.execute("LOAD tpch")

    existing = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='main'"
        ).fetchall()
    }
    generated = False
    generation_seconds = 0.0
    if not set(TABLES).issubset(existing):
        t0 = time.perf_counter()
        con.execute("CALL dbgen(sf = ?)", [args.scale])
        generation_seconds = time.perf_counter() - t0
        generated = True

    row_counts: dict[str, int] = {}
    exports: list[dict[str, object]] = []
    export_seconds = 0.0
    for table in TABLES:
        count = int(con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        row_counts[table] = count
        destination = (args.output_dir / f"{table}.csv").resolve()
        t0 = time.perf_counter()
        con.execute(
            f"COPY ({EXPORT_SQL[table]}) TO '{destination.as_posix()}' "
            "(HEADER, DELIMITER ',')"
        )
        elapsed = time.perf_counter() - t0
        export_seconds += elapsed
        exports.append(
            {
                "table": table,
                "rows": count,
                "path": str(destination),
                "bytes": destination.stat().st_size,
                "sha256": sha256(destination),
                "export_seconds": elapsed,
            }
        )

    expected = None
    row_count_match = None
    if args.scale == 1.0:
        expected = SF1_EXPECTED_ROWS
        row_count_match = row_counts == expected
        if not row_count_match:
            raise RuntimeError(
                f"TPC-H SF1 row-count mismatch: observed={row_counts}, expected={expected}"
            )

    con.close()
    manifest = {
        "evidence_type": "OUR_ADAPTER_OBSERVED",
        "adapter_scope": "data_generation_only",
        "author_source_modified": False,
        "generator": "DuckDB TPC-H extension",
        "duckdb_version": duckdb.__version__,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "scale_factor": args.scale,
        "database": str(args.database.resolve()),
        "extension_dir": str(args.extension_dir.resolve()),
        "generated_in_this_run": generated,
        "generation_seconds": generation_seconds,
        "export_seconds": export_seconds,
        "end_to_end_seconds": time.perf_counter() - started_perf,
        "started_unix": started_wall,
        "row_counts": row_counts,
        "sf1_expected_rows": expected,
        "sf1_row_count_match": row_count_match,
        "exports": exports,
        "limitations": [
            "Not the authors' Ubuntu tpch-kit dbgen invocation.",
            "CSV data are TPC-H compatible but byte-level equality with the missing author dataset is not claimed.",
            "Assignment generation and Shapley solving are outside this adapter's timing.",
        ],
    }
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with args.manifest.with_suffix(".csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(exports[0].keys()))
        writer.writeheader()
        writer.writerows(exports)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
