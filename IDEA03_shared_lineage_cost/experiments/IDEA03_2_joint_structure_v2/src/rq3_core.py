from __future__ import annotations

import csv
import ctypes
import hashlib
import json
import math
import os
import platform
import random
import sys
import threading
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import duckdb
import numpy as np


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
AGG_SRC = WORKSPACE_ROOT / "aggregate_report_shapley" / "src"
if str(AGG_SRC) not in sys.path:
    sys.path.insert(0, str(AGG_SRC))

from aggregate_report_shapley.h5_shared import (  # noqa: E402
    S6ReverseMultilinearAD,
    SharedStateLimitExceeded,
    StateGame,
)


NODES = ("NAT", "PA", "PB", "A1", "A2", "B1", "B2")
CITIES = (("A1", "PA"), ("A2", "PA"), ("B1", "PB"), ("B2", "PB"))
METRICS = ("enterprise_count", "site_count", "workers", "mfg_workers", "mfg_share")
WORKER_LEVELS = (8, 13, 21, 34, 55, 89)
VALUE_NAMES = ("local_add", "local_joint", "cross_add", "cross_joint")


@dataclass(frozen=True, slots=True)
class EFact:
    eid: str
    size: int
    player_id: str
    player_index: int


@dataclass(frozen=True, slots=True)
class BFact:
    sid: str
    eid: str
    city: str
    industry: str
    player_id: str
    player_index: int


@dataclass(frozen=True, slots=True)
class HFact:
    sid: str
    year: int
    workers: int
    player_id: str
    player_index: int


@dataclass(frozen=True, slots=True)
class DFact:
    city: str
    province: str


@dataclass(frozen=True, slots=True)
class Witness:
    witness_id: str
    eid: str
    sid: str
    city: str
    province: str
    industry: str
    workers: int
    players: tuple[int, int, int]
    required_mask: int


@dataclass(frozen=True, slots=True)
class Fixture:
    pair_id: str
    structure: str
    seed: int
    n: int
    year: int
    e: tuple[EFact, ...]
    b: tuple[BFact, ...]
    h: tuple[HFact, ...]
    d: tuple[DFact, ...]
    rewiring: tuple[dict[str, Any], ...]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def append_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    new_rows = list(rows)
    if not new_rows:
        return
    old_rows: list[dict[str, Any]] = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            old_rows = list(csv.DictReader(handle))
    write_csv(path, [*old_rows, *new_rows])


def environment_manifest() -> dict[str, Any]:
    try:
        import pandas as pd
        import scipy

        pandas_version = pd.__version__
        scipy_version = scipy.__version__
    except Exception as exc:  # pragma: no cover - advisory only
        pandas_version = scipy_version = f"unavailable:{type(exc).__name__}"
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "duckdb": duckdb.__version__,
        "numpy": np.__version__,
        "pandas": pandas_version,
        "scipy": scipy_version,
        "pid": os.getpid(),
        "historical_h5_shared": str(AGG_SRC / "aggregate_report_shapley" / "h5_shared.py"),
        "historical_h5_shared_sha256": sha256(AGG_SRC / "aggregate_report_shapley" / "h5_shared.py"),
    }


def _balanced_counts(total: int, groups: int) -> list[int]:
    return [total // groups + int(i < total % groups) for i in range(groups)]


def _site_slots(b_count: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    # Balance provinces first and cities second.  A single four-way split gives
    # B=6 the pattern (2, 2, 1, 1), leaving PB without a multi-site enterprise
    # and therefore making the requested cross-province rewiring impossible.
    # The nested split gives (2, 1, 2, 1), while retaining (1,1,1,1) for B=4
    # and (2,2,2,2) for B=8.
    province_counts = _balanced_counts(b_count, 2)
    city_counts = []
    for province_count in province_counts:
        city_counts.extend(_balanced_counts(province_count, 2))
    rows: list[dict[str, Any]] = []
    sid_index = 1
    for city_index, ((city, province), count) in enumerate(zip(CITIES, city_counts, strict=True)):
        for local_index in range(count):
            rows.append(
                {
                    "sid": f"S{sid_index}",
                    "city": city,
                    "province": province,
                    "industry": "manufacturing" if local_index % 2 == 0 else "service",
                    "workers": WORKER_LEVELS[(sid_index - 1 + seed) % len(WORKER_LEVELS)],
                    "city_local_index": local_index,
                    "city_index": city_index,
                }
            )
            sid_index += 1
    # Only the row order is randomized. City/industry/worker marginals remain fixed.
    rng.shuffle(rows)
    return rows


def _assign_low(slots: list[dict[str, Any]], e_count: int, seed: int) -> dict[str, str]:
    if e_count % 2:
        raise ValueError("E count must be even for the paired two-province design")
    rng = random.Random(seed + 17)
    assignment: dict[str, str] = {}
    half = e_count // 2
    for province, eids in (("PA", [f"E{i+1}" for i in range(half)]),
                           ("PB", [f"E{i+1+half}" for i in range(half)])):
        local_slots = [row for row in slots if row["province"] == province]
        degrees = _balanced_counts(len(local_slots), len(eids))
        remaining = dict(zip(eids, degrees, strict=True))
        priority = list(eids)
        rng.shuffle(priority)
        rank = {eid: i for i, eid in enumerate(priority)}
        used_cities_by_eid: dict[str, set[str]] = defaultdict(set)
        # Interleave the two cities so every multi-site enterprise spans cities before duplicates.
        local_slots.sort(key=lambda row: (row["city_local_index"], row["city"], row["sid"]))
        for row in local_slots:
            candidates = [eid for eid in eids if remaining[eid] > 0]
            candidates.sort(
                key=lambda eid: (
                    row["city"] in used_cities_by_eid[eid],
                    -len(used_cities_by_eid[eid]),
                    -remaining[eid],
                    rank[eid],
                )
            )
            chosen = candidates[0]
            assignment[row["sid"]] = chosen
            remaining[chosen] -= 1
            used_cities_by_eid[chosen].add(row["city"])
        if any(remaining.values()):
            raise AssertionError(f"unassigned degree in {province}: {remaining}")
    return assignment


def _sole_city_site(slots: list[dict[str, Any]], assignment: dict[str, str], eid: str) -> list[dict[str, Any]]:
    counts = Counter(row["city"] for row in slots if assignment[row["sid"]] == eid)
    return [row for row in slots if assignment[row["sid"]] == eid and counts[row["city"]] == 1]


def _rewire(
    slots: list[dict[str, Any]], low: dict[str, str], e_count: int, seed: int, structure: str
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    if structure == "low":
        return dict(low), []
    if structure not in {"medium", "high"}:
        raise ValueError(structure)
    rng = random.Random(seed + (31 if structure == "high" else 29))
    degree = Counter(low.values())
    half = e_count // 2
    left = [f"E{i+1}" for i in range(half) if degree[f"E{i+1}"] >= 2]
    right = [f"E{i+1+half}" for i in range(half) if degree[f"E{i+1+half}"] >= 2]
    rng.shuffle(left)
    rng.shuffle(right)
    pairs = list(zip(left, right, strict=False))
    if structure == "medium":
        pairs = pairs[: max(1, math.ceil(len(pairs) / 2))]
    current = dict(low)
    operations: list[dict[str, Any]] = []
    for op_index, (eid_a, eid_b) in enumerate(pairs, start=1):
        candidates_a = _sole_city_site(slots, current, eid_a)
        candidates_b = _sole_city_site(slots, current, eid_b)
        if not candidates_a or not candidates_b:
            continue
        row_a = sorted(candidates_a, key=lambda row: (row["city"], row["sid"]))[0]
        row_b = sorted(candidates_b, key=lambda row: (row["city"], row["sid"]))[0]
        current[row_a["sid"]], current[row_b["sid"]] = eid_b, eid_a
        operations.append(
            {
                "operation": op_index,
                "sid_a": row_a["sid"],
                "city_a": row_a["city"],
                "old_eid_a": eid_a,
                "new_eid_a": eid_b,
                "sid_b": row_b["sid"],
                "city_b": row_b["city"],
                "old_eid_b": eid_b,
                "new_eid_b": eid_a,
            }
        )
    return current, operations


def generate_fixture(
    *, pair_id: str, structure: str, seed: int, e_count: int, b_count: int, h_count: int, year: int
) -> Fixture:
    if b_count != h_count:
        raise ValueError("Every B must have exactly one H in the fixed year")
    if e_count + b_count + h_count <= 0:
        raise ValueError("empty game")
    slots = _site_slots(b_count, seed)
    low = _assign_low(slots, e_count, seed)
    assignment, rewiring = _rewire(slots, low, e_count, seed, structure)
    e_rows = tuple(
        EFact(f"E{i+1}", (i + seed) % 4 + 1, f"E:E{i+1}", i) for i in range(e_count)
    )
    b_rows = tuple(
        BFact(
            row["sid"], assignment[row["sid"]], row["city"], row["industry"],
            f"B:{row['sid']}", e_count + int(row["sid"][1:]) - 1,
        )
        for row in sorted(slots, key=lambda item: int(item["sid"][1:]))
    )
    h_rows = tuple(
        HFact(
            row["sid"], year, row["workers"], f"H:{row['sid']}",
            e_count + b_count + int(row["sid"][1:]) - 1,
        )
        for row in sorted(slots, key=lambda item: int(item["sid"][1:]))
    )
    fixture = Fixture(
        pair_id, structure, seed, e_count + b_count + h_count, year,
        e_rows, b_rows, h_rows, tuple(DFact(*row) for row in CITIES), tuple(rewiring),
    )
    validate_fixture(fixture)
    return fixture


def witnesses(fixture: Fixture) -> tuple[Witness, ...]:
    e_by_id = {row.eid: row for row in fixture.e}
    h_by_sid = {row.sid: row for row in fixture.h}
    d_by_city = {row.city: row.province for row in fixture.d}
    result = []
    for b in fixture.b:
        e = e_by_id[b.eid]
        h = h_by_sid[b.sid]
        players = (e.player_index, b.player_index, h.player_index)
        required = sum(1 << player for player in players)
        result.append(
            Witness(
                f"W:{b.sid}", b.eid, b.sid, b.city, d_by_city[b.city], b.industry,
                h.workers, players, required,
            )
        )
    return tuple(result)


def player_rows(fixture: Fixture) -> list[dict[str, Any]]:
    rows = []
    for row in fixture.e:
        rows.append({"player_index": row.player_index, "player_id": row.player_id, "relation": "E", "physical_key": row.eid})
    for row in fixture.b:
        rows.append({"player_index": row.player_index, "player_id": row.player_id, "relation": "B", "physical_key": row.sid})
    for row in fixture.h:
        rows.append({"player_index": row.player_index, "player_id": row.player_id, "relation": "H", "physical_key": row.sid})
    return sorted(rows, key=lambda row: row["player_index"])


def validate_fixture(fixture: Fixture) -> None:
    if fixture.n != len(fixture.e) + len(fixture.b) + len(fixture.h):
        raise AssertionError("player count mismatch")
    players = player_rows(fixture)
    if [row["player_index"] for row in players] != list(range(fixture.n)):
        raise AssertionError("player indexes are not a complete unique range")
    if len({row["player_id"] for row in players}) != fixture.n:
        raise AssertionError("duplicate player_id")
    if len({row.sid for row in fixture.b}) != len(fixture.b):
        raise AssertionError("duplicate B.sid")
    if {row.sid for row in fixture.b} != {row.sid for row in fixture.h}:
        raise AssertionError("B/H sid mismatch")
    if any(row.year != fixture.year for row in fixture.h):
        raise AssertionError("unexpected H year")
    if any(row.eid not in {e.eid for e in fixture.e} for row in fixture.b):
        raise AssertionError("B references unknown E")


def compare_pair(low: Fixture, high: Fixture) -> dict[str, Any]:
    if low.pair_id != high.pair_id or low.n != high.n:
        raise AssertionError("not a matched pair")
    invariant = {
        "player_rows": player_rows(low) == player_rows(high),
        "e_rows": [asdict(row) for row in low.e] == [asdict(row) for row in high.e],
        "site_keys": [row.sid for row in low.b] == [row.sid for row in high.b],
        "city_industry": [(row.sid, row.city, row.industry) for row in low.b]
        == [(row.sid, row.city, row.industry) for row in high.b],
        "h_rows": [asdict(row) for row in low.h] == [asdict(row) for row in high.h],
        "degree": Counter(row.eid for row in low.b) == Counter(row.eid for row in high.b),
        "witness_count": len(witnesses(low)) == len(witnesses(high)),
    }
    if not all(invariant.values()):
        raise AssertionError(f"pair invariant failed: {invariant}")
    full_low = report_python(low, (1 << low.n) - 1)
    full_high = report_python(high, (1 << high.n) - 1)
    stable_metrics = ("site_count", "workers", "mfg_workers", "mfg_share")
    stable = all(full_low[(node, metric)] == full_high[(node, metric)] for node in NODES for metric in stable_metrics)
    city_enterprise_stable = all(
        full_low[(city, "enterprise_count")] == full_high[(city, "enterprise_count")]
        for city, _province in CITIES
    )
    national_enterprise_stable = full_low[("NAT", "enterprise_count")] == full_high[("NAT", "enterprise_count")]
    if not (stable and city_enterprise_stable and national_enterprise_stable):
        raise AssertionError("paired full-report controls failed")
    return {
        **{f"invariant_{key}": value for key, value in invariant.items()},
        "stable_non_enterprise_metrics": stable,
        "city_enterprise_count_stable": city_enterprise_stable,
        "national_enterprise_count_stable": national_enterprise_stable,
        "PA_enterprise_low": full_low[("PA", "enterprise_count")],
        "PA_enterprise_high": full_high[("PA", "enterprise_count")],
        "PB_enterprise_low": full_low[("PB", "enterprise_count")],
        "PB_enterprise_high": full_high[("PB", "enterprise_count")],
        "province_enterprise_changed": (
            full_low[("PA", "enterprise_count")], full_low[("PB", "enterprise_count")]
        ) != (
            full_high[("PA", "enterprise_count")], full_high[("PB", "enterprise_count")]
        ),
    }


def _ancestors(witness: Witness) -> tuple[str, str, str]:
    return ("NAT", witness.province, witness.city)


def active_witnesses(fixture: Fixture, mask: int) -> tuple[Witness, ...]:
    return tuple(witness for witness in witnesses(fixture) if mask & witness.required_mask == witness.required_mask)


def report_from_active(active: Iterable[Witness]) -> dict[tuple[str, str], int | float | None]:
    active_by_node: dict[str, list[Witness]] = {node: [] for node in NODES}
    for witness in active:
        for node in _ancestors(witness):
            active_by_node[node].append(witness)
    report: dict[tuple[str, str], int | float | None] = {}
    for node in NODES:
        rows = active_by_node[node]
        enterprise = len({row.eid for row in rows})
        site = len({row.sid for row in rows})
        worker = sum(row.workers for row in rows)
        mfg = sum(row.workers for row in rows if row.industry == "manufacturing")
        report[(node, "enterprise_count")] = enterprise
        report[(node, "site_count")] = site
        report[(node, "workers")] = worker
        report[(node, "mfg_workers")] = mfg
        report[(node, "mfg_share")] = None if worker == 0 else mfg / worker
    return report


def report_python(fixture: Fixture, mask: int) -> dict[tuple[str, str], int | float | None]:
    return report_from_active(active_witnesses(fixture, mask))


def coordinate_source_sets(fixture: Fixture) -> dict[tuple[str, str], set[int]]:
    result: dict[tuple[str, str], set[int]] = {}
    ws = witnesses(fixture)
    for node in NODES:
        local = [w for w in ws if node in _ancestors(w)]
        for metric in METRICS:
            eligible = local if metric != "mfg_workers" else [w for w in local if w.industry == "manufacturing"]
            variables = {player for witness in eligible for player in witness.players}
            result[(node, metric)] = variables
    return result


def structure_metrics(fixture: Fixture) -> dict[str, Any]:
    ws = witnesses(fixture)
    eid_provinces: dict[str, set[str]] = defaultdict(set)
    eid_cities: dict[str, set[str]] = defaultdict(set)
    eid_witnesses = Counter()
    for witness in ws:
        eid_provinces[witness.eid].add(witness.province)
        eid_cities[witness.eid].add(witness.city)
        eid_witnesses[witness.eid] += 1
    multi = [eid for eid, count in eid_witnesses.items() if count > 1]
    sources = coordinate_source_sets(fixture)
    overlap_rows = []
    coordinates = list(sources)
    for i, left in enumerate(coordinates):
        for right in coordinates[i + 1 :]:
            intersection = len(sources[left] & sources[right])
            union = len(sources[left] | sources[right])
            overlap_rows.append(intersection / union if union else 0.0)
    per_player_coordinates = Counter()
    for variables in sources.values():
        for player in variables:
            per_player_coordinates[player] += 1
    local_left = sources[("PA", "enterprise_count")]
    local_right = sources[("PA", "mfg_workers")]
    cross_left = sources[("PA", "enterprise_count")]
    cross_right = sources[("PB", "enterprise_count")]
    return {
        "pair_id": fixture.pair_id,
        "structure": fixture.structure,
        "seed": fixture.seed,
        "n": fixture.n,
        "e_count": len(fixture.e),
        "b_count": len(fixture.b),
        "h_count": len(fixture.h),
        "join_witnesses": len(ws),
        "source_variable_occurrences": sum(len(w.players) for w in ws),
        "cross_province_eid_rate": sum(len(eid_provinces[eid]) > 1 for eid in multi) / len(multi) if multi else 0.0,
        "cross_city_eid_rate": sum(len(eid_cities[eid]) > 1 for eid in multi) / len(multi) if multi else 0.0,
        "multi_site_enterprises": len(multi),
        "max_enterprise_regions": max((len(value) for value in eid_provinces.values()), default=0),
        "mean_player_coordinate_count": sum(per_player_coordinates.values()) / fixture.n,
        "max_player_coordinate_count": max(per_player_coordinates.values(), default=0),
        "provenance_overlap_mean_jaccard": sum(overlap_rows) / len(overlap_rows),
        "provenance_overlap_max_jaccard": max(overlap_rows, default=0.0),
        "local_pair_overlap_variables": len(local_left & local_right),
        "cross_pair_overlap_variables": len(cross_left & cross_right),
        "cross_pair_overlap_jaccard": len(cross_left & cross_right) / len(cross_left | cross_right),
        "rewiring_operations": len(fixture.rewiring),
    }


def save_fixture(fixture: Fixture, root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    write_csv(root / "E.csv", [asdict(row) for row in fixture.e])
    write_csv(root / "B.csv", [asdict(row) for row in fixture.b])
    write_csv(root / "H.csv", [asdict(row) for row in fixture.h])
    write_csv(root / "D.csv", [asdict(row) for row in fixture.d])
    write_csv(root / "players.csv", player_rows(fixture))
    write_csv(root / "rewiring_log.csv", fixture.rewiring, [
        "operation", "sid_a", "city_a", "old_eid_a", "new_eid_a",
        "sid_b", "city_b", "old_eid_b", "new_eid_b",
    ])
    files = ["E.csv", "B.csv", "H.csv", "D.csv", "players.csv", "rewiring_log.csv"]
    manifest = {
        "pair_id": fixture.pair_id,
        "structure": fixture.structure,
        "seed": fixture.seed,
        "n": fixture.n,
        "year": fixture.year,
        "player_definition": "one physical E/B/H row per player; D exogenous",
        "sql_semantics": "full E-B-H join",
        "hashes": {name: sha256(root / name) for name in files},
        "structure_metrics": structure_metrics(fixture),
    }
    write_json(root / "manifest.json", manifest)
    return manifest


def _create_sql_database(fixture: Fixture) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE E(eid VARCHAR,size INTEGER,player_id VARCHAR,player_index INTEGER)")
    con.execute("CREATE TABLE B(sid VARCHAR,eid VARCHAR,city VARCHAR,industry VARCHAR,player_id VARCHAR,player_index INTEGER)")
    con.execute("CREATE TABLE H(sid VARCHAR,year INTEGER,workers INTEGER,player_id VARCHAR,player_index INTEGER)")
    con.execute("CREATE TABLE D(city VARCHAR,province VARCHAR)")
    con.executemany("INSERT INTO E VALUES (?,?,?,?)", [(r.eid, r.size, r.player_id, r.player_index) for r in fixture.e])
    con.executemany("INSERT INTO B VALUES (?,?,?,?,?,?)", [(r.sid, r.eid, r.city, r.industry, r.player_id, r.player_index) for r in fixture.b])
    con.executemany("INSERT INTO H VALUES (?,?,?,?,?)", [(r.sid, r.year, r.workers, r.player_id, r.player_index) for r in fixture.h])
    con.executemany("INSERT INTO D VALUES (?,?)", [(r.city, r.province) for r in fixture.d])
    return con


def validate_sql_all_coalitions(fixture: Fixture, sql_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    con = _create_sql_database(fixture)
    query = sql_path.read_text(encoding="utf-8")
    start = time.perf_counter()
    cursor = con.execute(query, {"coalition_count": 1 << fixture.n, "year": fixture.year})
    sql_seconds = time.perf_counter() - start
    checked = 0
    mismatches = 0
    max_numeric_error = 0.0
    sample_masks = {0, (1 << fixture.n) - 1, *[1 << i for i in range(fixture.n)]}
    sample_masks.update({fixture.seed % (1 << fixture.n), (fixture.seed * 17) % (1 << fixture.n)})
    samples: list[dict[str, Any]] = []
    current_mask = -1
    expected: dict[tuple[str, str], int | float | None] = {}
    while True:
        batch = cursor.fetchmany(8192)
        if not batch:
            break
        for mask, node, enterprise, site, workers_value, mfg, share in batch:
            mask = int(mask)
            if mask != current_mask:
                current_mask = mask
                expected = report_python(fixture, mask)
            observed = {
                "enterprise_count": int(enterprise),
                "site_count": int(site),
                "workers": int(workers_value),
                "mfg_workers": int(mfg),
                "mfg_share": None if share is None else float(share),
            }
            for metric, value in observed.items():
                target = expected[(node, metric)]
                if value is None or target is None:
                    equal = value is None and target is None
                    error = 0.0 if equal else math.inf
                else:
                    error = abs(float(value) - float(target))
                    equal = error <= 1e-12
                max_numeric_error = max(max_numeric_error, error)
                mismatches += int(not equal)
                checked += 1
            if mask in sample_masks:
                samples.append({"mask": mask, "node": node, **observed})
    con.close()
    return {
        "pair_id": fixture.pair_id,
        "structure": fixture.structure,
        "n": fixture.n,
        "coalitions": 1 << fixture.n,
        "sql_rows": (1 << fixture.n) * len(NODES),
        "coordinates_checked": checked,
        "mismatches": mismatches,
        "max_numeric_error": max_numeric_error,
        "sql_seconds": sql_seconds,
        "status": "VERIFIED" if mismatches == 0 else "FAILED_CORRECTNESS",
    }, samples


def validate_sql_sample(
    fixture: Fixture, sql_path: Path, masks: list[int]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Validate a frozen, deterministic mask sample without materializing 2^N SQL rows."""
    unique_masks = sorted({int(mask) for mask in masks})
    upper = 1 << fixture.n
    if not unique_masks or any(mask < 0 or mask >= upper for mask in unique_masks):
        raise ValueError("sample mask outside coalition range")
    con = _create_sql_database(fixture)
    con.execute("CREATE TABLE ValidationMasks(mask UBIGINT)")
    con.executemany("INSERT INTO ValidationMasks VALUES (?)", [(mask,) for mask in unique_masks])
    query = sql_path.read_text(encoding="utf-8")
    original = "SELECT range::UBIGINT AS mask FROM range($coalition_count)"
    replacement = "SELECT mask FROM ValidationMasks"
    if original not in query:
        raise AssertionError("SQL mask CTE changed; sampled validator replacement is no longer safe")
    query = query.replace(original, replacement, 1)
    start = time.perf_counter()
    rows = con.execute(query, {"year": fixture.year}).fetchall()
    sql_seconds = time.perf_counter() - start
    checked = 0
    mismatches = 0
    max_numeric_error = 0.0
    samples: list[dict[str, Any]] = []
    expected_by_mask = {mask: report_python(fixture, mask) for mask in unique_masks}
    for mask, node, enterprise, site, workers_value, mfg, share in rows:
        mask = int(mask)
        expected = expected_by_mask[mask]
        observed = {
            "enterprise_count": int(enterprise),
            "site_count": int(site),
            "workers": int(workers_value),
            "mfg_workers": int(mfg),
            "mfg_share": None if share is None else float(share),
        }
        for metric, value in observed.items():
            target = expected[(node, metric)]
            if value is None or target is None:
                equal = value is None and target is None
                error = 0.0 if equal else math.inf
            else:
                error = abs(float(value) - float(target))
                equal = error <= 1e-12
            max_numeric_error = max(max_numeric_error, error)
            mismatches += int(not equal)
            checked += 1
        samples.append({"mask": mask, "node": node, **observed})
    con.close()
    return {
        "pair_id": fixture.pair_id,
        "structure": fixture.structure,
        "n": fixture.n,
        "coalitions": len(unique_masks),
        "sql_rows": len(rows),
        "coordinates_checked": checked,
        "mismatches": mismatches,
        "max_numeric_error": max_numeric_error,
        "sql_seconds": sql_seconds,
        "status": "VERIFIED" if mismatches == 0 else "FAILED_CORRECTNESS",
        "validation_mode": "DETERMINISTIC_MASK_SAMPLE",
    }, samples


def metric_arrays(fixture: Fixture) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    start = time.perf_counter()
    ws = witnesses(fixture)
    source_seconds = time.perf_counter() - start
    start = time.perf_counter()
    masks = np.arange(1 << fixture.n, dtype=np.uint64)
    active = [(masks & np.uint64(w.required_mask)) == np.uint64(w.required_mask) for w in ws]
    arrays: dict[str, np.ndarray] = {}
    for province in ("PA", "PB"):
        enterprise = np.zeros(len(masks), dtype=np.int16)
        for eid in sorted({w.eid for w in ws if w.province == province}):
            present = np.zeros(len(masks), dtype=np.bool_)
            for index, witness in enumerate(ws):
                if witness.province == province and witness.eid == eid:
                    present |= active[index]
            enterprise += present
        arrays[f"{province}.enterprise_count"] = enterprise
    pa_mfg = np.zeros(len(masks), dtype=np.int32)
    for index, witness in enumerate(ws):
        if witness.province == "PA" and witness.industry == "manufacturing":
            pa_mfg += active[index].astype(np.int32) * witness.workers
    arrays["PA.mfg_workers"] = pa_mfg
    transform_seconds = time.perf_counter() - start
    return arrays, {"source_seconds": source_seconds, "transform_seconds": transform_seconds}


def metric_arrays_witness_states(fixture: Fixture) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    """Enumerate exact reachable report states, not player coalitions.

    Each witness has a unique B row and a unique H row.  Therefore every subset
    of witnesses is reachable by selecting the union of its E/B/H players, and
    no omitted witness is accidentally activated (its unique B/H are absent).
    Report values consequently have an exact 2^|B| representation even when the
    player game has 2^N coalitions.
    """
    start = time.perf_counter()
    ws = witnesses(fixture)
    source_seconds = time.perf_counter() - start
    start = time.perf_counter()
    masks = np.arange(1 << len(ws), dtype=np.uint64)
    active = [(masks & np.uint64(1 << index)) != 0 for index in range(len(ws))]
    arrays: dict[str, np.ndarray] = {}
    for province in ("PA", "PB"):
        enterprise = np.zeros(len(masks), dtype=np.int16)
        for eid in sorted({w.eid for w in ws if w.province == province}):
            present = np.zeros(len(masks), dtype=np.bool_)
            for index, witness in enumerate(ws):
                if witness.province == province and witness.eid == eid:
                    present |= active[index]
            enterprise += present
        arrays[f"{province}.enterprise_count"] = enterprise
    pa_mfg = np.zeros(len(masks), dtype=np.int64)
    for index, witness in enumerate(ws):
        if witness.province == "PA" and witness.industry == "manufacturing":
            pa_mfg += active[index].astype(np.int64) * witness.workers
    arrays["PA.mfg_workers"] = pa_mfg
    transform_seconds = time.perf_counter() - start
    return arrays, {
        "source_seconds": source_seconds,
        "transform_seconds": transform_seconds,
        "state_representation": "EXACT_WITNESS_SUBSETS",
        "report_states_enumerated": len(masks),
        "player_coalitions_enumerated": 0,
    }


def paired_references(low: dict[str, np.ndarray], high: dict[str, np.ndarray]) -> dict[str, float]:
    references = {}
    for key in low:
        references[key] = float(max(low[key][-1], high[key][-1]))
        if references[key] <= 0:
            raise AssertionError(f"non-positive full reference for {key}")
    return references


def value_arrays(
    arrays: dict[str, np.ndarray], references: dict[str, float], revenue: float, lam: float
) -> dict[str, np.ndarray]:
    pa_e = arrays["PA.enterprise_count"].astype(np.float64) / references["PA.enterprise_count"]
    pb_e = arrays["PB.enterprise_count"].astype(np.float64) / references["PB.enterprise_count"]
    pa_mfg = arrays["PA.mfg_workers"].astype(np.float64) / references["PA.mfg_workers"]
    local_add = revenue * (pa_e + pa_mfg) / 2.0
    cross_add = revenue * (pa_e + pb_e) / 2.0
    local_joint = revenue * ((1.0 - lam) * (pa_e + pa_mfg) / 2.0 + lam * pa_e * pa_mfg)
    cross_joint = revenue * ((1.0 - lam) * (pa_e + pb_e) / 2.0 + lam * pa_e * pb_e)
    return {
        "local_add": local_add,
        "local_joint": local_joint,
        "cross_add": cross_add,
        "cross_joint": cross_joint,
    }


def nondegeneracy_rows(
    fixture: Fixture, arrays: dict[str, np.ndarray], values: dict[str, np.ndarray], references: dict[str, float]
) -> list[dict[str, Any]]:
    sources = coordinate_source_sets(fixture)
    rows = []
    for scope, key1, key2 in (
        ("local", "PA.enterprise_count", "PA.mfg_workers"),
        ("cross", "PA.enterprise_count", "PB.enterprise_count"),
    ):
        f1 = arrays[key1].astype(np.float64) / references[key1]
        f2 = arrays[key2].astype(np.float64) / references[key2]
        residual = values[f"{scope}_joint"] - values[f"{scope}_add"]
        pairs = np.unique(np.stack((f1, f2), axis=1), axis=0)
        overlap = len(sources[(key1.split(".")[0], key1.split(".")[1])] & sources[(key2.split(".")[0], key2.split(".")[1])])
        eligible = (
            len(np.unique(f1)) > 1
            and len(np.unique(f2)) > 1
            and len(np.unique(np.round(residual, 12))) > 1
            and len(pairs) > max(len(np.unique(f1)), len(np.unique(f2)))
        )
        rows.append(
            {
                "pair_id": fixture.pair_id,
                "structure": fixture.structure,
                "n": fixture.n,
                "scope": scope,
                "f1": key1,
                "f2": key2,
                "f1_unique": len(np.unique(f1)),
                "f2_unique": len(np.unique(f2)),
                "reachable_pairs": len(pairs),
                "interaction_residual_unique": len(np.unique(np.round(residual, 12))),
                "interaction_residual_range": float(np.ptp(residual)),
                "source_overlap_variables": overlap,
                "both_inputs_vary": len(np.unique(f1)) > 1 and len(np.unique(f2)) > 1,
                "nonadditive_effect": len(np.unique(np.round(residual, 12))) > 1,
                "not_single_metric": len(pairs) > max(len(np.unique(f1)), len(np.unique(f2))),
                # The status reports whether the diagnostic was successfully
                # evaluated.  Eligibility is a property of the fixture, not a
                # software-correctness verdict.  In particular N=10 is a semantic
                # smoke test and may legitimately be too small for mechanism use.
                "mechanism_eligible": eligible,
                "status": "VERIFIED",
                "eligibility_status": "VERIFIED" if eligible else "INPUT_UNSUPPORTED",
            }
        )
    return rows


def popcounts(n: int) -> np.ndarray:
    return np.fromiter((mask.bit_count() for mask in range(1 << n)), dtype=np.uint8, count=1 << n)


def exact_shapley(values: np.ndarray, n: int, counts: np.ndarray | None = None) -> np.ndarray:
    if counts is None:
        counts = popcounts(n)
    weights = np.array([1.0 / (n * math.comb(n - 1, size)) for size in range(n)], dtype=np.float64)
    all_masks = np.arange(1 << n, dtype=np.uint64)
    result = np.zeros(n, dtype=np.float64)
    for player in range(n):
        bit = np.uint64(1 << player)
        base = all_masks[(all_masks & bit) == 0]
        marginal = values[base | bit] - values[base]
        result[player] = np.sum(marginal * weights[counts[base]])
    return result


def value_from_state(
    fixture: Fixture,
    state: tuple[int, ...],
    value_name: str,
    references: dict[str, float],
    revenue: float,
    lam: float,
) -> float:
    active = [w for w, selected in zip(witnesses(fixture), state, strict=True) if selected == len(w.players)]
    pa_e = len({w.eid for w in active if w.province == "PA"}) / references["PA.enterprise_count"]
    pb_e = len({w.eid for w in active if w.province == "PB"}) / references["PB.enterprise_count"]
    pa_mfg = sum(w.workers for w in active if w.province == "PA" and w.industry == "manufacturing") / references["PA.mfg_workers"]
    if value_name == "local_add":
        return revenue * (pa_e + pa_mfg) / 2.0
    if value_name == "local_joint":
        return revenue * ((1 - lam) * (pa_e + pa_mfg) / 2.0 + lam * pa_e * pa_mfg)
    if value_name == "cross_add":
        return revenue * (pa_e + pb_e) / 2.0
    if value_name == "cross_joint":
        return revenue * ((1 - lam) * (pa_e + pb_e) / 2.0 + lam * pa_e * pb_e)
    if value_name == "local_f1":
        return revenue * pa_e
    if value_name == "local_f2":
        return revenue * pa_mfg
    if value_name == "cross_f1":
        return revenue * pa_e
    if value_name == "cross_f2":
        return revenue * pb_e
    raise KeyError(value_name)


def evidence_deltas(fixture: Fixture) -> tuple[tuple[int, ...], ...]:
    ws = witnesses(fixture)
    return tuple(tuple(int(player in witness.players) for witness in ws) for player in range(fixture.n))


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def current_rss() -> int | None:
    if os.name != "nt":
        return None
    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    get_memory = kernel32.K32GetProcessMemoryInfo
    get_memory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    get_memory.restype = ctypes.c_int
    handle = kernel32.GetCurrentProcess()
    ok = get_memory(handle, ctypes.byref(counters), counters.cb)
    return int(counters.WorkingSetSize) if ok else None


class PeakRSS:
    def __init__(self, interval: float = 0.01):
        self.interval = interval
        self.peak = current_rss()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        while not self._stop.wait(self.interval):
            value = current_rss()
            if value is not None:
                self.peak = value if self.peak is None else max(self.peak, value)

    def __enter__(self) -> "PeakRSS":
        self._thread.start()
        return self

    def __exit__(self, *_args: Any) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)
        value = current_rss()
        if value is not None:
            self.peak = value if self.peak is None else max(self.peak, value)


def run_s6_baseline(
    fixture: Fixture,
    value_name: str,
    references: dict[str, float],
    revenue: float,
    lam: float,
    state_cap: int,
    oracle: np.ndarray | None,
    source_seconds: float,
    order: str = "E_then_B_then_H",
) -> tuple[dict[str, Any], np.ndarray | None]:
    started = time.perf_counter()
    deltas = evidence_deltas(fixture)
    transform_seconds = time.perf_counter() - started
    base_order = list(range(fixture.n))
    if order == "low_degree_first":
        base_order.sort(key=lambda player: (sum(deltas[player]), player))
    elif order == "high_degree_first":
        base_order.sort(key=lambda player: (-sum(deltas[player]), player))
    elif order != "E_then_B_then_H":
        raise ValueError(order)
    ordered_deltas = tuple(deltas[player] for player in base_order)
    players = player_rows(fixture)
    ordered_ids = tuple(players[player]["player_id"] for player in base_order)
    game = StateGame(
        f"{fixture.pair_id}-{fixture.structure}-{value_name}-{order}",
        ordered_ids,
        ordered_deltas,
        lambda state: value_from_state(fixture, state, value_name, references, revenue, lam),
        tuple(0 for _ in range(fixture.n)),
        len(witnesses(fixture)),
        1,
    )
    peak_python = None
    with PeakRSS() as rss:
        try:
            compile_started = time.perf_counter()
            solver = S6ReverseMultilinearAD(game, state_cap=state_cap)
            compile_seconds = time.perf_counter() - compile_started
            solve_started = time.perf_counter()
            ordered_allocation = np.asarray(solver.solve_all(), dtype=np.float64)
            solve_seconds = time.perf_counter() - solve_started
            allocation = np.empty(fixture.n, dtype=np.float64)
            for ordered_index, original_player in enumerate(base_order):
                allocation[original_player] = ordered_allocation[ordered_index]
            diagnostics = solver.diagnostics()
            terminal_value_states = len({round(value, 12) for value in solver.terminal_values.values()})
            error = float(np.max(np.abs(allocation - oracle))) if oracle is not None else None
            efficiency = abs(float(np.sum(allocation)) - (
                value_from_state(fixture, tuple(sum(delta[i] for delta in deltas) for i in range(len(witnesses(fixture)))), value_name, references, revenue, lam)
                - value_from_state(fixture, (0,) * len(witnesses(fixture)), value_name, references, revenue, lam)
            ))
            status = "VERIFIED" if (oracle is None or error <= 1e-9) and efficiency <= 1e-8 else "FAILED_CORRECTNESS"
            detail = ""
        except SharedStateLimitExceeded as exc:
            compile_seconds = time.perf_counter() - compile_started
            solve_seconds = 0.0
            allocation = None
            diagnostics = {}
            terminal_value_states = None
            error = efficiency = None
            status = "RESOURCE_LIMIT"
            detail = str(exc)
    row = {
        "pair_id": fixture.pair_id,
        "seed": fixture.seed,
        "n": fixture.n,
        "structure": fixture.structure,
        "value_name": value_name,
        "method": "H3_S6_EVIDENCE_STATE",
        "player_order": order,
        "status": status,
        "source_seconds": source_seconds,
        "transform_seconds": transform_seconds,
        "compile_seconds": compile_seconds,
        "solve_seconds": solve_seconds,
        "total_cold_seconds": source_seconds + transform_seconds + compile_seconds + solve_seconds,
        "total_reuse_seconds": compile_seconds + solve_seconds,
        "peak_rss_bytes": rss.peak,
        "python_peak_bytes": peak_python,
        "max_abs_error": error,
        "efficiency_error": efficiency,
        "state_cap": state_cap,
        "terminal_value_states": terminal_value_states,
        "detail": detail,
        **diagnostics,
    }
    return row, allocation


def b0_cost_row(
    fixture: Fixture,
    value_name: str,
    values: np.ndarray,
    counts: np.ndarray,
    source_seconds: float,
    transform_seconds: float,
) -> tuple[dict[str, Any], np.ndarray]:
    peak_python = None
    with PeakRSS() as rss:
        started = time.perf_counter()
        allocation = exact_shapley(values, fixture.n, counts)
        solve_seconds = time.perf_counter() - started
    efficiency = abs(float(np.sum(allocation)) - float(values[-1] - values[0]))
    row = {
        "pair_id": fixture.pair_id,
        "seed": fixture.seed,
        "n": fixture.n,
        "structure": fixture.structure,
        "value_name": value_name,
        "method": "B0_FULL_COALITION_NUMPY",
        "player_order": "E_then_B_then_H",
        "status": "VERIFIED" if efficiency <= 1e-8 else "FAILED_CORRECTNESS",
        "source_seconds": source_seconds,
        "transform_seconds": transform_seconds,
        "compile_seconds": 0.0,
        "solve_seconds": solve_seconds,
        "total_cold_seconds": source_seconds + transform_seconds + solve_seconds,
        "total_reuse_seconds": solve_seconds,
        "peak_rss_bytes": rss.peak,
        "python_peak_bytes": peak_python,
        "max_abs_error": 0.0,
        "efficiency_error": efficiency,
        "coalitions": len(values),
        "detail": "vectorized exact subset Shapley over full value table",
    }
    return row, allocation


def interaction_rows(cost_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {(row["pair_id"], row["method"], row["player_order"], row["structure"], row["value_name"]): row for row in cost_rows if row["status"] == "VERIFIED"}
    output = []
    phases = ("source_seconds", "transform_seconds", "compile_seconds", "solve_seconds", "total_cold_seconds", "total_reuse_seconds")
    pairs = sorted({row["pair_id"] for row in cost_rows})
    methods = sorted({(row["method"], row["player_order"]) for row in cost_rows})
    for pair_id in pairs:
        for method, order in methods:
            for scope in ("local", "cross"):
                names = {
                    "A": ("low", f"{scope}_add"),
                    "B": ("high", f"{scope}_add"),
                    "C": ("low", f"{scope}_joint"),
                    "D": ("high", f"{scope}_joint"),
                }
                cells = {cell: by_key.get((pair_id, method, order, structure, value)) for cell, (structure, value) in names.items()}
                if not all(cells.values()):
                    continue
                for phase in phases:
                    times = {cell: float(row[phase]) for cell, row in cells.items()}
                    delta = (times["D"] - times["C"]) - (times["B"] - times["A"])
                    ratio_available = all(value > 0 for value in times.values())
                    k = (times["D"] / times["C"]) / (times["B"] / times["A"]) if ratio_available else None
                    output.append(
                        {
                            "pair_id": pair_id,
                            "n": cells["A"]["n"],
                            "method": method,
                            "player_order": order,
                            "scope": scope,
                            "phase": phase,
                            "T_A": times["A"],
                            "T_B": times["B"],
                            "T_C": times["C"],
                            "T_D": times["D"],
                            "delta_T": delta,
                            "K_T": k,
                            "I_T_log_K": math.log(k) if k is not None and k > 0 else None,
                            "ratio_status": "MEASURED" if ratio_available else "NOT_COMPUTABLE_ZERO_OR_MISSING_STAGE",
                        }
                    )
    return output

