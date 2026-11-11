from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import statistics
import sys
import time
import traceback
import zipfile
from pathlib import Path

import numpy as np


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_lineage(lineage: list[list[str]]) -> list[set[int]]:
    # Deliberately mirrors the author notebook. PYTHONHASHSEED is frozen by the launcher.
    variables: set[str] = set()
    for clause in lineage:
        variables.update(clause)
    mapping = {variable: index for index, variable in enumerate(variables)}
    return [{mapping[fact] for fact in clause} for clause in lineage]


def load_academic(zip_path: Path) -> tuple[list[tuple[str, str, list[list[str]]]], float]:
    started = time.perf_counter()
    lineages: list[tuple[str, str, list[list[str]]]] = []
    with zipfile.ZipFile(zip_path, "r") as archive:
        for file_name in archive.namelist():
            if not file_name.endswith(".json"):
                continue
            with archive.open(file_name) as handle:
                data = json.load(handle)
            for result in data.get("results", []):
                dnf = result.get("dnf", "")
                if len(dnf) < 10000:
                    lineages.append((file_name[:-5], result.get("tuple_id", ""), dnf))
    return lineages, time.perf_counter() - started


def percentile(values: list[float], q: float) -> float | None:
    return float(np.percentile(np.asarray(values, dtype=float), q)) if values else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--algorithm", choices=["LExaBan", "LExaShap"], required=True)
    parser.add_argument("--repeat", type=int, required=True)
    parser.add_argument("--max-instances", type=int)
    parser.add_argument("--include-notebook-outlier", action="store_true")
    parser.add_argument("--variant", default="author_unmodified")
    parser.add_argument("--selection-csv", type=Path)
    parser.add_argument("--selection-status", default="FAILED")
    parser.add_argument("--disable-int-digit-limit", action="store_true")
    parser.add_argument("--full-traceback", action="store_true")
    args = parser.parse_args()

    if args.disable_int_digit_limit:
        sys.set_int_max_str_digits(0)

    repo = args.repo_root.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(repo))
    if args.algorithm == "LExaBan":
        from Algorithms.LExaBan.BanzhafCircuit import DNFCircuit
    else:
        from Algorithms.LExaShap.ShapleyCircuit import DNFCircuit

    zip_path = repo / "Notebooks" / "Example Data" / "Academic.zip"
    lineages, input_build_s = load_academic(zip_path)
    selected = list(enumerate(lineages))
    if not args.include_notebook_outlier:
        selected = [(i, item) for i, item in selected if i != 2430]
    if args.max_instances is not None:
        selected = selected[: args.max_instances]
    if args.selection_csv is not None:
        with args.selection_csv.open(newline="", encoding="utf-8-sig") as handle:
            chosen = {
                int(row["source_index"])
                for row in csv.DictReader(handle)
                if row.get("status") == args.selection_status
            }
        selected = [(i, item) for i, item in selected if i in chosen]

    rows: list[dict[str, object]] = []
    run_started = time.perf_counter()
    for order, (source_index, (query, tuple_id, dnf)) in enumerate(selected):
        variables = set().union(*(set(clause) for clause in dnf)) if dnf else set()
        started = time.perf_counter()
        status = "PASS"
        error_type = ""
        error_message = ""
        result_sha256 = ""
        output_count = 0
        numeric_finite = ""
        numeric_nonfinite_count = ""
        try:
            circuit = DNFCircuit(parse_lineage(dnf), timeout=3600)
            output_count = len(circuit.banzhaf_values)
            result_sha256 = hashlib.sha256(repr(circuit.banzhaf_values).encode("utf-8")).hexdigest()
            arrays = [np.asarray(item[1], dtype=np.longdouble).reshape(-1) for item in circuit.banzhaf_values]
            numeric_nonfinite_count = sum(int(np.size(a) - np.count_nonzero(np.isfinite(a))) for a in arrays)
            numeric_finite = numeric_nonfinite_count == 0
        except Exception as exc:  # author notebook also treats every exception as failure
            status = "FAILED"
            error_type = type(exc).__name__
            error_message = str(exc)[:500]
            if args.full_traceback:
                traceback.print_exc()
            else:
                print(f"FAILED source_index={source_index} {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        elapsed = time.perf_counter() - started
        rows.append(
            {
                "protocol_id": "BRBD_v1",
                "run_kind": "R1_AUTHOR_NOTEBOOK_INPUT",
                "dataset": "Academic_precomputed_lineage",
                "algorithm": args.algorithm,
                "variant": args.variant,
                "repeat": args.repeat,
                "order": order,
                "source_index": source_index,
                "query": query,
                "tuple_id": tuple_id,
                "n_variables": len(variables),
                "n_clauses": len(dnf),
                "input_build_s_shared": input_build_s,
                "algorithm_end_to_end_s": elapsed,
                "output_count": output_count,
                "status": status,
                "error_type": error_type,
                "error_message": error_message,
                "result_sha256": result_sha256,
                "numeric_finite": numeric_finite,
                "numeric_nonfinite_count": numeric_nonfinite_count,
            }
        )
        if order % 1000 == 0:
            print(json.dumps({"processed": order, "source_index": source_index, "algorithm": args.algorithm}), flush=True)

    total_s = time.perf_counter() - run_started
    csv_path = out / f"academic_{args.algorithm.lower()}_{args.variant}_repeat{args.repeat}.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    successful = [float(row["algorithm_end_to_end_s"]) for row in rows if row["status"] == "PASS"]
    summary = {
        "protocol_id": "BRBD_v1",
        "evidence_type": "AUTHOR_CODE_OBSERVED",
        "algorithm": args.algorithm,
        "variant": args.variant,
        "repeat": args.repeat,
        "input_semantics": "official Academic.zip; author notebook len(dnf)<10000; source index 2430 excluded unless explicitly requested",
        "timing_scope": "author constructor only: lifting + d-tree compilation + all-variable reverse gradient; excludes ProvSQL lineage generation",
        "source_repo": str(repo),
        "source_zip": str(zip_path),
        "source_zip_sha256": sha256_file(zip_path),
        "python": sys.version,
        "platform": platform.platform(),
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "input_build_s": input_build_s,
        "instance_count": len(rows),
        "success_count": len(successful),
        "success_rate": len(successful) / len(rows) if rows else None,
        "mean_s": statistics.fmean(successful) if successful else None,
        "p50_s": percentile(successful, 50),
        "p90_s": percentile(successful, 90),
        "p95_s": percentile(successful, 95),
        "p99_s": percentile(successful, 99),
        "max_s": max(successful) if successful else None,
        "batch_algorithm_s": total_s,
        "csv_sha256": sha256_file(csv_path),
        "notebook_outlier_included": args.include_notebook_outlier,
        "max_instances": args.max_instances,
        "selection_csv": str(args.selection_csv.resolve()) if args.selection_csv else None,
        "disable_int_digit_limit": args.disable_int_digit_limit,
        "numeric_finite_success_count": sum(row["numeric_finite"] is True for row in rows),
        "numeric_nonfinite_return_count": sum(row["numeric_finite"] is False for row in rows),
    }
    summary_path = out / f"academic_{args.algorithm.lower()}_{args.variant}_repeat{args.repeat}_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
