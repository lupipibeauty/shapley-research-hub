from __future__ import annotations

import csv
import ctypes
import hashlib
import json
import math
import os
import platform
import shutil
import statistics
import sys
import threading
import time
import zipfile
from fractions import Fraction
from pathlib import Path

import duckdb
import numpy as np

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
P3_0, P3_1B = PROJECT / "P3_0", PROJECT / "P3_1B"
WORKSPACE = PROJECT.parents[1]
AGG = WORKSPACE / "aggregate_report_shapley"
OFFICIAL = AGG / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main"
ARCHIVE = AGG / "external" / "abramovich" / "archive" / "LExaBan-LExaShap-main.zip"
for path in (ROOT / "adapters", P3_0 / "src", str(OFFICIAL)):
    sys.path.insert(0, str(path))

from p3_to_boolean_dnf import build_games, write_games  # noqa: E402
from shapley_output_adapter import scalarize  # noqa: E402
from Algorithms.LExaShap.ShapleyCircuit import DNFCircuit  # noqa: E402
from build_lineage import extract_lineage  # noqa: E402
from native_exact_baseline import LayeredJointDecisionDiagram, shapley_from_conditional  # noqa: E402
from oracle_sql import create_database, load_fixture  # noqa: E402

RESULTS = ROOT / "results"
for sub in ("r1", "r2", "timing", "c2", "audit"):
    (RESULTS / sub).mkdir(parents=True, exist_ok=True)
(ROOT / "logs").mkdir(exist_ok=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


class PMC(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def current_rss() -> int:
    try:
        ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), ctypes.c_ulong]
        ctypes.windll.psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        counters = PMC(); counters.cb = ctypes.sizeof(counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        return int(counters.WorkingSetSize) if ok else 0
    except Exception:
        return 0


def sampled_call(fn):
    stop = threading.Event(); peak = [current_rss()]
    def monitor():
        while not stop.wait(0.001):
            peak[0] = max(peak[0], current_rss())
    thread = threading.Thread(target=monitor, daemon=True); thread.start()
    start = time.perf_counter()
    try:
        result = fn()
    finally:
        elapsed = time.perf_counter() - start
        stop.set(); thread.join(); peak[0] = max(peak[0], current_rss())
    return result, elapsed, peak[0]


def summary_rows(method: str, runs: list[dict]) -> list[dict]:
    rows = []
    for stage in sorted({k for run in runs for k in run["seconds"]}):
        values = [run["seconds"][stage] for run in runs]
        q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive") if len(values) > 1 else (values[0], values[0], values[0])
        rows.append({"method": method, "stage": stage, "repeats": len(values),
                     "median_seconds": statistics.median(values), "iqr_seconds": q3-q1,
                     "min_seconds": min(values), "max_seconds": max(values),
                     "pipeline_sampled_peak_rss_bytes": max(run["peak_rss"] for run in runs)})
    return rows


def exact_boolean_shapley(players: list[str], clauses: list[list[str]]) -> dict[str, Fraction]:
    n = len(players); pos = {p: i for i, p in enumerate(players)}
    clause_masks = [sum(1 << pos[p] for p in clause) for clause in clauses]
    def value(mask): return int(any(mask & c == c for c in clause_masks))
    out = {}
    for player, i in pos.items():
        total = Fraction(); bit = 1 << i
        for mask in range(1 << n):
            if mask & bit: continue
            k = mask.bit_count()
            total += Fraction(math.factorial(k)*math.factorial(n-k-1), math.factorial(n)) * (value(mask|bit)-value(mask))
        out[player] = total
    return out


def count_graph(root, child_attr: str) -> int:
    seen = set(); stack = [root]
    while stack:
        node = stack.pop()
        if id(node) in seen: continue
        seen.add(id(node))
        children = getattr(node, child_attr, ()) or ()
        stack.extend(list(children))
    return len(seen)


def official_run(players: list[str], clauses: list[list[str]]) -> dict:
    circuit = DNFCircuit([set(c) for c in clauses])
    values, raw = scalarize(circuit, players)
    return {"values": values, "raw": raw, "active_variables": len(circuit.var_dict),
            "dtree_nodes": count_graph(circuit.root, "children"),
            "value_graph_nodes": count_graph(circuit.root.value, "_prev")}


def verify_official_snapshot() -> dict:
    with zipfile.ZipFile(ARCHIVE) as zf:
        members = [x for x in zf.infolist() if not x.is_dir()]
        mismatches, missing, cache_mismatches = [], [], []
        prefix = "LExaBan-LExaShap-main/"
        for item in members:
            rel = item.filename[len(prefix):] if item.filename.startswith(prefix) else item.filename
            target = OFFICIAL / Path(rel)
            if not target.exists(): missing.append(rel); continue
            if hashlib.sha256(zf.read(item)).hexdigest() != sha256(target):
                if "__pycache__" in rel or rel.endswith(".pyc"):
                    cache_mismatches.append(rel)
                else:
                    mismatches.append(rel)
    relevant = [OFFICIAL/"README.md", OFFICIAL/"Algorithms/LExaShap/ShapleyEngine.py",
                OFFICIAL/"Algorithms/LExaShap/ShapleyCircuit.py", OFFICIAL/"Advancing_Fact_Attribution_for_Query_Answering.pdf"]
    return {"archive": str(ARCHIVE), "archive_sha256": sha256(ARCHIVE), "archive_file_count": len(members),
            "missing_archive_files": missing, "source_content_mismatches": mismatches,
            "ignored_runtime_cache_mismatches": cache_mismatches,
            "official_source_exact_excluding_runtime_cache": not missing and not mismatches,
            "git_commit": "UNVERIFIED_ZIP_HAS_NO_GIT_METADATA",
            "relevant_hashes": {str(p.relative_to(OFFICIAL)): sha256(p) for p in relevant}}


def run_r1() -> dict:
    cases = {
        "readme_mixed": (["x1","x2","x3"], [["x1","x2"],["x3"]]),
        "single": (["x"], [["x"]]),
        "and3": (["x1","x2","x3"], [["x1","x2","x3"]]),
        "or3": (["x1","x2","x3"], [["x1"],["x2"],["x3"]]),
        "shared_overlap": (["x1","x2","x3"], [["x1","x2"],["x1","x3"]]),
        "dummy_extension": (["x1","dummy"], [["x1"]]),
    }
    records, raw_outputs = [], {}
    for case, (players, clauses) in cases.items():
        result, elapsed, peak = sampled_call(lambda p=players,c=clauses: official_run(p,c))
        oracle = exact_boolean_shapley(players, clauses)
        raw_outputs[case] = {"input": {"players": players, "dnf": clauses}, "official": result,
                             "elapsed_seconds": elapsed, "sampled_peak_rss_bytes": peak}
        for player in players:
            error = abs(result["values"][player] - float(oracle[player]))
            records.append({"case": case, "player": player, "official_scalar": result["values"][player],
                            "independent_oracle_fraction": str(oracle[player]), "absolute_error": error,
                            "exact_within_1e-12": error <= 1e-12, "dtree_nodes": result["dtree_nodes"],
                            "value_graph_nodes": result["value_graph_nodes"], "elapsed_seconds": elapsed,
                            "sampled_peak_rss_bytes": peak})
    write_csv(RESULTS/"r1"/"boolean_case_validation.csv", records)
    (RESULTS/"r1"/"official_raw_outputs.json").write_text(json.dumps(raw_outputs, ensure_ascii=False, indent=2), encoding="utf-8")
    snapshot = verify_official_snapshot()
    status = "R1_REPRODUCED" if all(r["exact_within_1e-12"] for r in records) and snapshot["official_source_exact_excluding_runtime_cache"] else "R1_PARTIAL"
    audit = {"status": status, "author_core_modified": False, "official_output_semantics": "gradient vectors by coalition size",
             "local_adapter": "dot(gradient, leaf probability vector) * 2^n / n!; independently checked, not fitted to P3 oracle",
             "official_readme_has_expected_numeric_output": False, "snapshot": snapshot,
             "python": sys.version, "numpy": np.__version__, "scipy": __import__("scipy").__version__,
             "maximum_absolute_error": max(r["absolute_error"] for r in records)}
    (RESULTS/"r1"/"r1_summary.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


def lexashap_pipeline() -> tuple[dict, dict]:
    seconds = {}; start_all = time.perf_counter()
    start = time.perf_counter(); games = build_games(); seconds["fixture_to_H1_H2_DNF"] = time.perf_counter()-start
    outputs = {}
    for game in ("H1", "H2"):
        start = time.perf_counter(); outputs[game] = official_run(games["players"], games["games"][game]["clauses"])
        seconds[f"{game}_separate_compile_and_all_player_solve"] = time.perf_counter()-start
    start = time.perf_counter(); combined = {p: outputs["H1"]["values"][p]+outputs["H2"]["values"][p] for p in games["players"]}
    seconds["G1_linear_composition"] = time.perf_counter()-start
    seconds["end_to_end"] = time.perf_counter()-start_all
    return {"games": games, "outputs": outputs, "combined": combined}, seconds


def mtbdd_pipeline() -> tuple[dict, dict]:
    seconds = {}; start_all = time.perf_counter()
    fixture = load_fixture(P3_0/"fixtures"/"anchor_13_players.json")
    start = time.perf_counter(); con = create_database(P3_0/"schema"/"complete_schema.sql", fixture); seconds["database_schema_and_load"] = time.perf_counter()-start
    start = time.perf_counter(); lineage = extract_lineage(con); seconds["SQL_JOIN_witness_extraction"] = time.perf_counter()-start
    start = time.perf_counter(); diagram = LayeredJointDecisionDiagram(lineage,13); seconds["MTBDD_build"] = time.perf_counter()-start
    start = time.perf_counter(); distributions = diagram.all_conditional_distributions(); seconds["all_player_conditional_model_counting"] = time.perf_counter()-start
    start = time.perf_counter(); values = shapley_from_conditional(distributions,13,"G1"); seconds["G1_all_player_solve"] = time.perf_counter()-start
    con.close(); seconds["end_to_end"] = time.perf_counter()-start_all
    audit = diagram.audit()
    return {"values": values, "nonterminal_nodes": audit.nonterminal_nodes, "terminal_nodes": audit.terminal_nodes}, seconds


def run_r2_and_timing() -> dict:
    dnf_path = ROOT/"reproduction"/"abramovich_r2"/"p3_h1_h2_dnf.json"
    games = write_games(dnf_path)
    p3b = {r["threshold"]: {} for r in csv.DictReader((P3_1B/"results"/"threshold_shapley.csv").open(encoding="utf-8-sig"))}
    for row in csv.DictReader((P3_1B/"results"/"threshold_shapley.csv").open(encoding="utf-8-sig")):
        p3b[row["threshold"]][row["player_id"]] = Fraction(row["shapley_fraction"])
    g1 = {r["player_id"]: Fraction(r["shapley_fraction"]) for r in csv.DictReader((P3_0/"results"/"record_shapley.csv").open(encoding="utf-8-sig")) if r["game_id"]=="G1"}

    lexa_runs=[]; lexa_result=None
    for _ in range(3):
        holder, elapsed, peak = sampled_call(lexashap_pipeline)
        pipeline, seconds = holder; seconds["sampled_wrapper_elapsed"] = elapsed
        lexa_runs.append({"seconds": seconds, "peak_rss": peak}); lexa_result = pipeline
    mtbdd_runs=[]; mtbdd_result=None
    for _ in range(3):
        holder, elapsed, peak = sampled_call(mtbdd_pipeline)
        pipeline, seconds = holder; seconds["sampled_wrapper_elapsed"] = elapsed
        mtbdd_runs.append({"seconds": seconds, "peak_rss": peak}); mtbdd_result = pipeline
    write_csv(RESULTS/"timing"/"cost_breakdown.csv", summary_rows("LExaShap_H1_plus_H2",lexa_runs)+summary_rows("P3_native_MTBDD",mtbdd_runs))
    (RESULTS/"r2"/"official_raw_h1_h2.json").write_text(json.dumps(lexa_result["outputs"],ensure_ascii=False,indent=2),encoding="utf-8")

    fixture=json.loads((P3_0/"fixtures"/"anchor_13_players.json").read_text(encoding="utf-8")); revenue=Fraction(fixture["revenue_pool"])
    rows=[]
    for player in games["players"]:
        h1,h2=lexa_result["outputs"]["H1"]["values"][player],lexa_result["outputs"]["H2"]["values"][player]
        combined=h1+h2
        rows.append({"player_id":player,"H1_official_adapted":h1,"H1_oracle_fraction":str(p3b["H1"][player]),"H1_absolute_error":abs(h1-float(p3b["H1"][player])),
                     "H2_official_adapted":h2,"H2_oracle_fraction":str(p3b["H2"][player]),"H2_absolute_error":abs(h2-float(p3b["H2"][player])),
                     "G1_combined":combined,"G1_oracle_fraction":str(g1[player]),"G1_absolute_error":abs(combined-float(g1[player])),
                     "revenue_decimal":float(revenue*Fraction(str(combined))/2)})
    write_csv(RESULTS/"r2"/"player_correctness_and_payment.csv",rows)
    owners=[]
    for map_name,mapping in fixture["owner_maps"].items():
        sums={}
        for row in rows: sums[mapping[row["player_id"]]]=sums.get(mapping[row["player_id"]],0.0)+row["revenue_decimal"]
        owners.extend({"owner_map":map_name,"owner_id":owner,"revenue_decimal":value} for owner,value in sorted(sums.items()))
    write_csv(RESULTS/"r2"/"owner_revenue.csv",owners)
    maxerr=max(max(r["H1_absolute_error"],r["H2_absolute_error"],r["G1_absolute_error"]) for r in rows)
    summary={"status":"R2_SAME_TARGET_REPRODUCED" if maxerr<=1e-9 else "R2_FAILED","players":13,"H1_clauses":9,"H2_clauses":4,
             "H1_sum":sum(r["H1_official_adapted"] for r in rows),"H2_sum":sum(r["H2_official_adapted"] for r in rows),
             "G1_sum":sum(r["G1_combined"] for r in rows),"maximum_absolute_error":maxerr,
             "revenue_sum":sum(r["revenue_decimal"] for r in rows),"owner_map_budget_sums":{m:sum(r["revenue_decimal"] for r in owners if r["owner_map"]==m) for m in fixture["owner_maps"]},
             "oracle_used_to_construct_input":False,"H1_H2_compiled_separately":True,"official_cross_game_subexpression_sharing":False,
             "MTBDD_structure":{"nonterminal_nodes":mtbdd_result["nonterminal_nodes"],"terminal_nodes":mtbdd_result["terminal_nodes"]},
             "LExaShap_structure":{g:{"dtree_nodes":lexa_result["outputs"][g]["dtree_nodes"],"value_graph_nodes":lexa_result["outputs"][g]["value_graph_nodes"]} for g in ("H1","H2")}}
    (RESULTS/"r2"/"r2_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    return summary


def run_c2() -> dict:
    con=duckdb.connect(":memory:")
    fixtures=ROOT/"c2_semantics"/"fixtures"
    for table,file in (("hierarchy_occurrences","hierarchy_occurrences.csv"),("city_dimension","city_dimension.csv"),("cross_statistics","cross_statistics.csv")):
        p=str((fixtures/file).resolve()).replace("'","''")
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_csv_auto('{p}',header=true)")
    queries={
      "city":"SELECT d.database_id,d.city_id,d.province_id,COUNT(o.record_id) row_count,COUNT(DISTINCT o.entity_id) entity_count FROM city_dimension d LEFT JOIN hierarchy_occurrences o ON d.database_id=o.database_id AND d.city_id=o.city_id GROUP BY d.database_id,d.city_id,d.province_id ORDER BY d.database_id,d.city_id",
      "province":"SELECT d.database_id,d.province_id,COUNT(o.record_id) row_count,COUNT(DISTINCT o.entity_id) entity_count FROM city_dimension d LEFT JOIN hierarchy_occurrences o ON d.database_id=o.database_id AND d.city_id=o.city_id GROUP BY d.database_id,d.province_id ORDER BY d.database_id",
      "grouping_sets":"SELECT d.database_id,d.province_id,d.city_id,GROUPING(d.province_id) g_province,GROUPING(d.city_id) g_city,COUNT(o.record_id) row_count,COUNT(DISTINCT o.entity_id) entity_count FROM city_dimension d LEFT JOIN hierarchy_occurrences o ON d.database_id=o.database_id AND d.city_id=o.city_id GROUP BY d.database_id,GROUPING SETS ((d.province_id,d.city_id),(d.province_id),()) ORDER BY d.database_id,g_province,g_city,d.city_id",
      "cross":"SELECT database_id,region_id,industry_id,COUNT(DISTINCT entity_id) entity_count FROM cross_statistics GROUP BY database_id,region_id,industry_id ORDER BY database_id,region_id,industry_id",
      "region_margin":"SELECT database_id,region_id,COUNT(DISTINCT entity_id) entity_count FROM cross_statistics GROUP BY database_id,region_id ORDER BY database_id,region_id",
      "industry_margin":"SELECT database_id,industry_id,COUNT(DISTINCT entity_id) entity_count FROM cross_statistics GROUP BY database_id,industry_id ORDER BY database_id,industry_id"}
    all_rows=[]; results={}
    for name,sql in queries.items():
        cursor=con.execute(sql); cols=[x[0] for x in cursor.description]; data=[dict(zip(cols,row)) for row in cursor.fetchall()]
        results[name]=data; all_rows.extend({"query_id":name,**row} for row in data)
    con.close(); write_csv(RESULTS/"c2"/"sql_results.csv",all_rows)
    city={(r["database_id"],r["city_id"]):r for r in results["city"]}; province={r["database_id"]:r for r in results["province"]}
    region_a={(r["region_id"],r["entity_count"]) for r in results["region_margin"] if r["database_id"]=="CROSS_A"}
    region_b={(r["region_id"],r["entity_count"]) for r in results["region_margin"] if r["database_id"]=="CROSS_B"}
    industry_a={(r["industry_id"],r["entity_count"]) for r in results["industry_margin"] if r["database_id"]=="CROSS_A"}
    industry_b={(r["industry_id"],r["entity_count"]) for r in results["industry_margin"] if r["database_id"]=="CROSS_B"}
    cells_a={(r["region_id"],r["industry_id"],r["entity_count"]) for r in results["cross"] if r["database_id"]=="CROSS_A"}
    cells_b={(r["region_id"],r["industry_id"],r["entity_count"]) for r in results["cross"] if r["database_id"]=="CROSS_B"}
    checks={"city_local_counts_equal":all(city[("A",c)]["entity_count"]==city[("B",c)]["entity_count"] for c in ("city_1","city_2","city_empty")),
            "province_distinct_differs":province["A"]["entity_count"]==1 and province["B"]["entity_count"]==2,
            "null_count_star_semantics":province["NULL_CASE"]["row_count"]==1 and province["NULL_CASE"]["entity_count"]==0,
            "empty_group_preserved":city[("A","city_empty")]["row_count"]==0 and city[("A","city_empty")]["entity_count"]==0,
            "grouping_sets_executed":len(results["grouping_sets"])>0,
            "cross_margins_equal_but_cells_differ":region_a==region_b and industry_a==industry_b and cells_a!=cells_b}
    prov={"status":"AVAILABLE" if shutil.which("psql") and shutil.which("docker") else "ENV_BLOCKED",
          "docker_path":shutil.which("docker"),"psql_path":shutil.which("psql"),
          "provsql_executed":False,"note":"DuckDB SQL success is not treated as ProvSQL provenance verification."}
    (ROOT/"c2_semantics"/"provsql"/"environment_check.json").write_text(json.dumps(prov,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={"status":"C2_MINIMAL_SEMANTICS_VERIFIED" if all(checks.values()) else "C2_CHECK_FAILED","checks":checks,"provsql":prov,
             "interpretation":"Leaf DISTINCT counts alone do not recover parent or cross-cell identity; entity identity/source relation is additionally required. This is a semantic counterexample, not a new hardness result."}
    (RESULTS/"c2"/"c2_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    return summary


def main():
    started=time.strftime("%Y-%m-%dT%H:%M:%S%z")
    r1=run_r1()
    r2=run_r2_and_timing()
    c2=run_c2()
    env={"python":sys.version,"platform":platform.platform(),"duckdb":duckdb.__version__,"numpy":np.__version__,"official_source":str(OFFICIAL),"official_source_modified_by_P3_1C":False}
    (ROOT/"config"/"environment_manifest.json").write_text(json.dumps(env,ensure_ascii=False,indent=2),encoding="utf-8")
    luo_path=RESULTS/"audit"/"luo2024_status.json"
    luo=json.loads(luo_path.read_text(encoding="utf-8")) if luo_path.exists() else {"status":"UNVERIFIED"}
    manifest={"stage":"P3_1C_COMPLETED_AND_PAUSED","started_at":started,"completed_at":time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "P3_0_or_P3_1B_modified":False,"R1":r1["status"],"R2":r2["status"],"C2":c2["status"],
              "Luo2024":luo["status"],"ProvSQL":c2["provsql"]["status"],
              "large_scale_experiment_started":False,"new_algorithm_claimed":False,
              "artifact_hashes":{str(p.relative_to(ROOT)):sha256(p) for p in sorted(RESULTS.rglob("*")) if p.is_file()}}
    (ROOT/"P3_1C_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    (ROOT/"logs"/"run.json").write_text(json.dumps({"manifest":manifest,"environment":env},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__=="__main__": main()
