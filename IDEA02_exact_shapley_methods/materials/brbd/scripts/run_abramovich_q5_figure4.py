from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pickle
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--repeat", type=int, required=True)
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(repo))
    from Algorithms.Max_LExaBan.ArithmeticCircuit import ArithmeticCircuit

    source = repo / "Notebooks" / "Example Data" / "q5_runs.pkl"
    input_started = time.perf_counter()
    with source.open("rb") as handle:
        runs = pickle.load(handle)
    input_build_s = time.perf_counter() - input_started

    rows = []
    batch_started = time.perf_counter()
    for source_index, item in enumerate(runs):
        scale_parameter, semimodule, author_tag = item
        if scale_parameter <= 0:  # exact author Notebook condition
            continue
        variables = {v for clause, _ in semimodule for v in clause}
        started = time.perf_counter()
        status, error = "PASS", ""
        result_hash = ""
        try:
            circuit = ArithmeticCircuit(semimodule)
            result_hash = hashlib.sha256(repr(circuit.banzhaf_values).encode()).hexdigest()
        except Exception as exc:
            status, error = "FAILED", f"{type(exc).__name__}: {exc}"
        elapsed = time.perf_counter() - started
        rows.append({
            "protocol_id": "BRBD_v1",
            "run_kind": "R1_AUTHOR_FIGURE4_INPUT",
            "algorithm": "Max_LExaBan",
            "repeat": args.repeat,
            "source_index": source_index,
            "scale_parameter": scale_parameter,
            "lineitem_facts_author_formula": 6000000 / (scale_parameter + 1),
            "author_tag": author_tag,
            "semimodule_terms": len(semimodule),
            "n_variables": len(variables),
            "algorithm_end_to_end_s": elapsed,
            "status": status,
            "error": error,
            "result_sha256": result_hash,
        })
        if source_index % 25 == 0:
            print(json.dumps({"processed_source_index": source_index}), flush=True)
    batch_s = time.perf_counter() - batch_started

    csv_path = out / f"figure4_q5_repeat{args.repeat}.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)

    groups = defaultdict(list)
    for row in rows:
        if row["status"] == "PASS":
            groups[int(row["scale_parameter"])].append(float(row["algorithm_end_to_end_s"]))
    group_rows = [{
        "scale_parameter": k,
        "lineitem_facts_author_formula": 6000000 / (k + 1),
        "replicate_count": len(v),
        "mean_s": statistics.fmean(v),
        "median_s": statistics.median(v),
        "min_s": min(v),
        "max_s": max(v),
    } for k, v in sorted(groups.items())]
    group_csv = out / f"figure4_q5_groups_repeat{args.repeat}.csv"
    with group_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(group_rows[0])); writer.writeheader(); writer.writerows(group_rows)

    summary = {
        "protocol_id": "BRBD_v1",
        "evidence_type": "AUTHOR_CODE_OBSERVED",
        "paper_target": "Figure 4, physical PDF page 23",
        "algorithm": "Max_LExaBan",
        "repeat": args.repeat,
        "input_sha256": file_hash(source),
        "input_build_s": input_build_s,
        "run_count": len(rows),
        "success_count": sum(r["status"] == "PASS" for r in rows),
        "group_count": len(group_rows),
        "batch_algorithm_s": batch_s,
        "raw_csv_sha256": file_hash(csv_path),
        "group_csv_sha256": file_hash(group_csv),
        "timing_scope": "ArithmeticCircuit constructor only; uses released precomputed semimodule inputs; excludes SQL and ProvSQL",
        "missing_baseline": "paper naive/no-optimization implementation is not exposed by the released Notebook",
    }
    (out / f"figure4_q5_repeat{args.repeat}_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
