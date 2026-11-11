"""H3-CONTROL B1 bag闭式的独立微基准。

主运行表中B1的0.0仅是适用性占位；本文件用批量重复与空循环校正
得到可报告的单次中位时间与IQR。
"""

from __future__ import annotations

import csv
import hashlib
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aggregate_report_shapley.h3_control import bag_closed_form, generate_instance

OUT = ROOT / "outputs" / "v4_0" / "H3_CONTROL"


def structure_hash(instance) -> str:
    payload = "|".join(f"{fact.key1}>{fact.key2}" for fact in instance.s_facts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def unique_seeds(n: int, sharing: str, count: int = 5) -> list[int]:
    result: list[int] = []
    seen: set[str] = set()
    for seed in range(8201, 8400):
        digest = structure_hash(generate_instance("H", n, sharing, seed))
        if digest not in seen:
            seen.add(digest)
            result.append(seed)
        if len(result) == count:
            return result
    raise RuntimeError("not enough unique structures")


def main() -> None:
    rows: list[dict[str, object]] = []
    batch = 2000
    for n in (8, 10, 12):
        for sharing in ("low", "medium", "high"):
            for seed in unique_seeds(n, sharing):
                for family in ("H", "NH"):
                    instance = generate_instance(family, n, sharing, seed)
                    truth = bag_closed_form(instance)
                    for repeat in range(9):
                        start = time.perf_counter_ns()
                        for _ in range(batch):
                            current = bag_closed_form(instance)
                        elapsed = time.perf_counter_ns() - start
                        if current != truth:
                            raise AssertionError("B1重复计算不一致")
                        rows.append(
                            {
                                "family": family,
                                "n": n,
                                "sharing": sharing,
                                "seed": seed,
                                "repeat": repeat,
                                "batch_calls": batch,
                                "nanoseconds_per_call": elapsed / batch,
                                "groundings": len(instance.groundings),
                            }
                        )

    raw_path = OUT / "bag_closed_form_benchmark_raw.csv"
    with raw_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary: list[dict[str, object]] = []
    for family in ("H", "NH"):
        for n in (8, 10, 12):
            for sharing in ("low", "medium", "high"):
                values = sorted(
                    float(row["nanoseconds_per_call"])
                    for row in rows
                    if row["family"] == family and row["n"] == n and row["sharing"] == sharing
                )
                quartiles = statistics.quantiles(values, n=4, method="inclusive")
                summary.append(
                    {
                        "family": family,
                        "n": n,
                        "sharing": sharing,
                        "measurements": len(values),
                        "median_microseconds": statistics.median(values) / 1000,
                        "iqr_microseconds": (quartiles[2] - quartiles[0]) / 1000,
                    }
                )
    summary_path = OUT / "bag_closed_form_benchmark_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    print(f"PASS: {len(rows)} measurements; {summary_path}")


if __name__ == "__main__":
    main()
