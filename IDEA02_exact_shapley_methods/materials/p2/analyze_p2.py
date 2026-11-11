from __future__ import annotations

import csv
import json
import math
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

ROOT=Path(__file__).resolve().parent; RESULTS=ROOT/"results"
for folder in (ROOT/"generators",ROOT/"oracles",ROOT/"algorithms",ROOT/"utilities"):
    sys.path.insert(0,str(folder))
from exact_shapley import compile_state_transitions,subset_shapley,transition_shapley
from p2_instances import HIERARCHIES,build_instances
from p2_oracle import lineage,q2_groundings,report
from p2_utilities import utility


def read(name):
    with (RESULTS/name).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))


def write(name,rows):
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with (RESULTS/name).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def timed(fn,repeats=7):
    xs=[];result=None;peak=0
    for _ in range(repeats):
        tracemalloc.start();t=time.perf_counter();result=fn();xs.append(time.perf_counter()-t)
        _,p=tracemalloc.get_traced_memory();tracemalloc.stop();peak=max(peak,p)
    q=statistics.quantiles(xs,n=4,method="inclusive")
    return result,{"state_compile_median_seconds":statistics.median(xs),"state_compile_iqr_seconds":q[2]-q[0],
                   "state_compile_repeats":repeats,"state_compile_python_peak_bytes":peak}


def bench(fn,prefix,repeats=7):
    xs=[];result=None;peak=0
    for _ in range(repeats):
        tracemalloc.start();t=time.perf_counter();result=fn();xs.append(time.perf_counter()-t)
        _,p=tracemalloc.get_traced_memory();tracemalloc.stop();peak=max(peak,p)
    q=statistics.quantiles(xs,n=4,method="inclusive")
    return result,{f"{prefix}_median_seconds":statistics.median(xs),f"{prefix}_iqr_seconds":q[2]-q[0],
                   f"{prefix}_repeats":repeats,f"{prefix}_python_peak_bytes":peak}


def interaction_map(values,n,tol=1e-12):
    out={}
    for i in range(n):
        for j in range(i+1,n):
            bits=(1<<i)|(1<<j)
            for mask in range(1<<n):
                if not mask&bits:
                    d=values[mask|bits]-values[mask|(1<<i)]-values[mask|(1<<j)]+values[mask]
                    if abs(d)>tol:out[(i,j,mask)]=d
    return out


def main():
    instances=build_instances(); sql=read("P2_sql_oracle_audit.csv")
    sql_by={(r["family"],r["hierarchy"]):r for r in sql}
    structural_raw=read("P2_structural_complexity.csv")
    structural_by={}
    for r in structural_raw:
        if r.get("n_players"):structural_by[r["family"]]=r
    compile_by={}; reports_by={}
    for key in sql_by:
        family,h=key;inst=instances[family]
        reports=[report(q2_groundings(inst,m),h) for m in range(1<<inst.n_players)]
        (keys,trans),audit=timed(lambda:compile_state_transitions(reports,inst.n_players))
        compile_by[key]={**audit,"compiled_unique_report_states":len(set(keys)),"compiled_transition_signatures":sum(len(x) for x in trans)}
        reports_by[key]=reports
    # Merge structure/stage costs into A and B tables.
    for filename in ("P2_A1_source_structure.csv","P2_A2_report_hierarchy.csv","P2_B_factorial_8cases.csv"):
        rows=read(filename); enriched=[]
        for r in rows:
            key=(r["family"],r["hierarchy"]); sr=structural_by[r["family"]]; sq=sql_by[key]; cp=compile_by[key]
            add={k:v for k,v in sr.items() if k not in r and k not in ("hierarchy",)}
            add.update(cp)
            for k in ("sql_median_seconds","sql_iqr_seconds","sql_python_peak_bytes","python_report_median_seconds","python_report_iqr_seconds","python_report_python_peak_bytes"):
                add[k]=sq.get(k,"")
            add["end_to_end_measured_median_seconds"]=sum(float(add.get(k,0) or 0) for k in
                ("sql_median_seconds","state_compile_median_seconds"))+float(r.get("state_query_median_seconds",0) or 0)
            enriched.append({**r,**add})
        write(filename,enriched)
    # Clean structural table to one measured F x H row.
    write("P2_structural_complexity.csv",[{**structural_by[r["family"]],**r,**compile_by[(r["family"],r["hierarchy"])]} for r in sql])
    # A3: distinguish source interaction from extra interaction under G.
    inst=instances["F2-PATH-HIGH"]; reports=reports_by[(inst.family,"H2-CROSS")]
    keys,transitions=compile_state_transitions(reports,inst.n_players)
    utilities=("G0-ADD-COMMON","G1-LOCAL-COMMON","G2-JOINT-TASK-FULL")
    maps={g:interaction_map([utility(r,g) for r in reports],inst.n_players) for g in utilities}
    direct_pairs={tuple(sorted((int(p[1:])-1 for p in clause))) for terms in lineage(inst).values() for clause in terms}
    a3=[]
    prior_rows=read("P2_A3_value_structure.csv")
    old={r["utility"]:r for r in prior_rows if r.get("phase")=="A3"}
    if len(old)<3:
        old.update({r["utility"]:r for r in prior_rows})
    base=maps["G0-ADD-COMMON"]
    for g in utilities:
        cur=maps[g];new=set(cur)-set(base);gone=set(base)-set(cur)
        indirect=sum(1 for i,j,m in cur if not any(i in pair and j in pair for pair in direct_pairs))
        values=[utility(r,g) for r in reports]
        _,subset_cost=bench(lambda:subset_shapley(values,inst.n_players),"subset")
        state_values={key:values[m] for m,key in enumerate(keys)}
        _,state_cost=bench(lambda:transition_shapley(transitions,state_values,inst.n_players),"state_query")
        a3.append({**old[g],"phase":"A3","new_nonzero_contexts_vs_G0":len(new),"removed_contexts_vs_G0":len(gone),
                   "increased_abs_contexts_vs_G0":sum(abs(cur.get(k,0))>abs(base.get(k,0))+1e-12 for k in set(cur)|set(base)),
                   "nonzero_contexts_without_shared_direct_witness":indirect,
                   "unique_values":len(set(values)),**subset_cost,**state_cost,**compile_by[(inst.family,"H2-CROSS")],
                   "interpretation":"finite differences include SQL provenance and utility; vs-G0 columns isolate changes under fixed reports"})
    write("P2_A3_value_structure.csv",a3)
    # Add utility-value complexity to descriptive factorial contrasts.
    fac=read("P2_B_factorial_8cases.csv"); interactions=[]
    for outcome in ("unique_report_states","transition_signatures","unique_values","subset_median_seconds","state_query_median_seconds","end_to_end_measured_median_seconds"):
        cell={(r["F"],r["H"],r["G"]):math.log1p(float(r[outcome])) for r in fac}
        for effect in ("F","H","G","F:H","F:G","H:G","F:H:G"):
            dims=effect.split(":");contrast=0.0
            for (f,h,g),v in cell.items():
                signs={"F":1 if f=="high" else -1,"H":1 if h=="cross" else -1,"G":1 if g=="joint" else -1}
                contrast+=math.prod(signs[d] for d in dims)*v/4
            interactions.append({"outcome":outcome,"effect":effect,"log1p_contrast":contrast,"exp_effect_ratio":math.exp(contrast),
                                 "inference":"DESCRIPTIVE_ONLY; one matched structural pair, timing repeats are technical repeats"})
    write("P2_B_interaction_analysis.csv",interactions)
    runtime=[]
    for r in fac:
        runtime.append({k:r.get(k,"") for k in ("case_id","family","hierarchy","utility","sql_median_seconds","python_report_median_seconds",
                                                  "state_compile_median_seconds","subset_median_seconds","state_query_median_seconds","end_to_end_measured_median_seconds",
                                                  "sql_python_peak_bytes","state_compile_python_peak_bytes","subset_python_peak_bytes","state_query_python_peak_bytes")})
    write("P2_runtime_breakdown.csv",runtime)
    manifest=json.loads((RESULTS/"P2_manifest.json").read_text(encoding="utf-8"));manifest["post_analysis_completed"]=True
    manifest["a3_new_g2_contexts_vs_g0"]=len(set(maps["G2-JOINT-TASK-FULL"])-set(base))
    (RESULTS/"P2_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":"POST_ANALYSIS_COMPLETED","compile_cases":len(compile_by),"g2_new_contexts":manifest["a3_new_g2_contexts_vs_g0"]},ensure_ascii=False))


if __name__=="__main__":main()
