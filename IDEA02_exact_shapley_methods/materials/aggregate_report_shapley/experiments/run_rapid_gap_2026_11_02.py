from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
import tracemalloc
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aggregate_report_shapley.rapid_gap import (  # noqa: E402
    coalition_values,
    exact_shapley,
    exact_treewidth,
    local_factors,
    make_instance,
    min_fill_order,
    primal_graph,
    shapley_variable_elimination,
)

OUT = ROOT / "outputs" / "v4_0" / "RAPID_GAP"
OUT.mkdir(parents=True, exist_ok=True)


def write_csv(name: str, rows: list[dict]) -> None:
    with (OUT / name).open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sql_counts(instance):
    con = duckdb.connect()
    con.execute("CREATE TABLE fact(player INTEGER, source_group INTEGER, value_group INTEGER, weight DOUBLE)")
    src = {p: g for g, scope in enumerate(instance.source_scopes) for p in scope}
    val = {p: g for g, scope in enumerate(instance.value_scopes) for p in scope}
    con.executemany("INSERT INTO fact VALUES (?,?,?,?)", [(p, src[p], val[p], 1.0) for p in range(instance.n)])
    query = f"""
    WITH masks AS (SELECT range AS mask FROM range({1 << instance.n})),
    expanded AS (
      SELECT mask, source_group, value_group,
             CASE WHEN (mask & (CAST(1 AS BIGINT) << player)) <> 0 THEN 1 ELSE 0 END AS chosen
      FROM masks CROSS JOIN fact
    )
    SELECT mask, 'source' AS kind, source_group AS factor_id, SUM(chosen)::INTEGER AS selected
    FROM expanded GROUP BY mask, source_group
    UNION ALL
    SELECT mask, 'value', value_group, SUM(chosen)::INTEGER
    FROM expanded GROUP BY mask, value_group
    ORDER BY mask, kind, factor_id
    """
    start = time.perf_counter(); rows = con.execute(query).fetchall(); elapsed = time.perf_counter() - start
    con.close()
    return rows, elapsed, query


def main() -> None:
    protected = [
        ROOT / "outputs" / "v4_0" / "H3_CONTROL" / "summary.json",
        ROOT / "outputs" / "v4_0" / "H3_CONTROL" / "structure_and_state_metrics.csv",
        ROOT / "src" / "aggregate_report_shapley" / "h3_control.py",
    ]
    before = {str(path.relative_to(ROOT)): hash_file(path) for path in protected}
    structure=[]; truth=[]; performance=[]; sql_manifest=[]
    for n in (12, 16):
        for design in ("ALIGNED", "CROSSED"):
            instance = make_instance(design, n)
            sql_rows, sql_time, query = sql_counts(instance)
            value_start=time.perf_counter(); values = coalition_values(instance); value_build_time=time.perf_counter()-value_start
            value_bytes=sys.getsizeof(values)+sum(sys.getsizeof(value) for value in values)
            # SQL count audit against direct masks.
            sql_error = 0
            for mask, kind, factor_id, selected in sql_rows:
                scope = instance.source_scopes[factor_id] if kind == "source" else instance.value_scopes[factor_id]
                direct = sum(bool(mask & (1 << p)) for p in scope)
                sql_error = max(sql_error, abs(selected - direct))
            tracemalloc.start(); start=time.perf_counter(); exact=exact_shapley(values,n); b0_time=time.perf_counter()-start
            _,b0_peak=tracemalloc.get_traced_memory(); tracemalloc.stop()
            start=time.perf_counter(); base_factors=local_factors(instance); compile_time=time.perf_counter()-start
            tracemalloc.start(); start=time.perf_counter(); ve,metrics=shapley_variable_elimination(instance,base_factors); ve_time=time.perf_counter()-start
            _,peak=tracemalloc.get_traced_memory(); tracemalloc.stop()
            max_error=max(abs(a-b) for a,b in zip(exact,ve,strict=True))
            efficiency=abs(sum(exact)-(values[-1]-values[0]))
            gq=primal_graph(n,instance.source_scopes); gg=primal_graph(n,instance.value_scopes)
            gj=primal_graph(n,instance.source_scopes+instance.value_scopes)
            wq,_=min_fill_order(gq); wg,_=min_fill_order(gg); wj,_=min_fill_order(gj)
            tw_start=time.perf_counter(); wq_exact=exact_treewidth(gq); wg_exact=exact_treewidth(gg); wj_exact=exact_treewidth(gj); tw_seconds=time.perf_counter()-tw_start
            structure.append({
                "design":design,"n":n,"players":n,"physical_facts":n,
                "source_factors":len(instance.source_scopes),"value_factors":len(instance.value_scopes),
                "grounding_memberships":sum(map(len,instance.source_scopes)),
                "value_memberships":sum(map(len,instance.value_scopes)),
                "Wq":wq_exact,"Wq_min_fill_upper":wq,"Wq_status":"EXACT_SUBSET_DP","Wg":wg_exact,"Wg_min_fill_upper":wg,"Wg_status":"EXACT_SUBSET_DP",
                "Wjoint":wj_exact,"Wjoint_min_fill_upper":wj,"Wjoint_status":"EXACT_SUBSET_DP",
                "treewidth_exact_seconds":tw_seconds,"factor_table_entries":sum(2**len(s) for s in instance.source_scopes+instance.value_scopes),
                "sql_count_error":sql_error,
            })
            for player,(a,b) in enumerate(zip(exact,ve,strict=True)):
                truth.append({"design":design,"n":n,"player":player+1,"exact_shapley":a,"ve_shapley":b,"absolute_error":abs(a-b)})
            performance += [
                {"design":design,"n":n,"method":"B0_FULL_ENUMERATION","sql_seconds":sql_time,"value_build_seconds":value_build_time,"compile_seconds":0.0,"solve_seconds":b0_time,"end_to_end_seconds":sql_time+value_build_time+b0_time,"peak_bytes":value_bytes+b0_peak,"peak_scope":"VALUE_OBJECT_SIZE_PLUS_SOLVER_TRACEMALLOC","max_intermediate_entries":1<<n,"factor_entry_writes":0,"max_error":0.0},
                {"design":design,"n":n,"method":"CLASSIC_VARIABLE_ELIMINATION","sql_seconds":sql_time,"value_build_seconds":0.0,"compile_seconds":compile_time,"solve_seconds":ve_time,"end_to_end_seconds":sql_time+compile_time+ve_time,"peak_bytes":peak,"peak_scope":"SOLVER_TRACEMALLOC_EXCLUDES_DUCKDB_AND_BASE_FACTOR_INPUT","max_intermediate_entries":metrics['max_intermediate_entries'],"factor_entry_writes":metrics['factor_entry_writes'],"max_error":max_error},
            ]
            sql_manifest.append({"design":design,"n":n,"rows_returned":len(sql_rows),"sql_seconds":sql_time,"query_sha256":hashlib.sha256(query.encode()).hexdigest(),"efficiency_error":efficiency})
            (OUT/f"query_{design.lower()}_n{n}.sql").write_text(query,encoding="utf-8")
            print(design,n,"widths",wq,wg,wj,"error",max_error,flush=True)
    write_csv("structure_widths.csv",structure); write_csv("record_shapley_truth.csv",truth)
    write_csv("strong_baseline_performance.csv",performance); write_csv("sql_execution_manifest.csv",sql_manifest)
    after = {str(path.relative_to(ROOT)): hash_file(path) for path in protected}
    (OUT/"historical_hashes.json").write_text(json.dumps({"before":before,"after":after,"unchanged":before==after},ensure_ascii=False,indent=2),encoding="utf-8")
    summary={
        "status":"RAPID_GAP_STATIC_EXPERIMENT_COMPLETED_AND_PAUSED",
        "instances":4,"n_values":[12,16],"expanded_to_n20":False,
        "all_sql_checks_passed":all(row['sql_count_error']==0 for row in structure),
        "max_shapley_error":max(row['max_error'] for row in performance),
        "historical_unchanged":before==after,"new_algorithm_claimed":False,
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")


if __name__ == "__main__":
    main()
