from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import statistics
import sys
import time
import tracemalloc
from collections import Counter, defaultdict
from pathlib import Path

import duckdb

ROOT=Path(__file__).resolve().parent
P1=ROOT.parent
for folder in (ROOT/"generators",ROOT/"oracles",ROOT/"algorithms",ROOT/"utilities"):
    sys.path.insert(0,str(folder))

from exact_shapley import (compile_state_transitions,mobius_shapley,pair_interactions,state_key,
                           subset_shapley,transition_shapley)
from p2_instances import GROUP_CLOSURE,HIERARCHIES,P2Instance,build_instances
from p2_oracle import lineage,q2_groundings,report
from p2_utilities import semantic_stats,utility

RESULTS=ROOT/"results"; LOGS=ROOT/"logs"
RESULTS.mkdir(exist_ok=True); LOGS.mkdir(exist_ok=True)
CONFIG=json.loads((ROOT/"config"/"p2_config.json").read_text(encoding="utf-8"))
TOL=CONFIG["floating_tolerance"]


def write_csv(name,rows):
    fields=[]
    for row in rows:
        for key in row:
            if key not in fields: fields.append(key)
    with (RESULTS/name).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)


def timed(fn,repeats=7):
    times=[]; result=None; peak=0
    for _ in range(repeats):
        tracemalloc.start(); t=time.perf_counter(); result=fn(); times.append(time.perf_counter()-t)
        _,p=tracemalloc.get_traced_memory(); tracemalloc.stop(); peak=max(peak,p)
    q1,q3=statistics.quantiles(times,n=4,method="inclusive")[0::2]
    return result,{"median_seconds":statistics.median(times),"iqr_seconds":q3-q1,"min_seconds":min(times),
                   "max_seconds":max(times),"repeats":repeats,"python_peak_bytes":peak}


def min_fill_width(clauses):
    graph=defaultdict(set)
    for clause in clauses:
        for a in clause:
            for b in clause:
                if a!=b: graph[a].add(b)
    width=0; order=[]
    while graph:
        def score(v):
            ns=list(graph[v]); missing=sum(1 for i,a in enumerate(ns) for b in ns[i+1:] if b not in graph[a])
            return missing,len(ns),v
        v=min(graph,key=score); ns=list(graph[v]); width=max(width,len(ns)); order.append(v)
        for i,a in enumerate(ns):
            for b in ns[i+1:]: graph[a].add(b); graph[b].add(a)
        for a in ns: graph[a].discard(v)
        del graph[v]
    return width,order


def structure_metrics(instance):
    lin=lineage(instance); clauses=[c for terms in lin.values() for c in terms]
    occ=Counter(p for clause in clauses for p in clause); width,order=min_fill_width(clauses)
    # Hash-consed circuit: variable nodes + unique AND clauses + OR nodes for outputs with alternatives.
    vars_=set(occ); ands=set(clauses); ors=sum(1 for terms in lin.values() if len(terms)>1)
    return {"family":instance.family,"n_players":instance.n_players,"entity_facts":len(instance.entities),
            "link_facts":len(instance.links),"attribute_facts":len(instance.attributes),
            "groundings":len(clauses),"distinct_outputs":len(lin),"alternative_path_outputs":sum(len(v)>1 for v in lin.values()),
            "max_witnesses_per_output":max(map(len,lin.values()),default=0),"mean_player_witness_occurrence":sum(occ.values())/len(occ),
            "max_player_witness_occurrence":max(occ.values()),"dependency_components":components(clauses),
            "min_fill_width_upper":width,"min_fill_order":"|".join(order),"dnf_clauses":len(clauses),
            "dnf_variable_occurrences":sum(map(len,clauses)),"hashcons_circuit_nodes":len(vars_)+len(ands)+ors,
            "structural_role":instance.structural_role}


def components(clauses):
    g=defaultdict(set)
    for c in clauses:
        for a in c:
            for b in c:
                if a!=b:g[a].add(b)
    seen=set(); n=0
    for start in g:
        if start in seen:continue
        n+=1; stack=[start]; seen.add(start)
        while stack:
            for nxt in g[stack.pop()]:
                if nxt not in seen:seen.add(nxt);stack.append(nxt)
    return n


def create_db(instance):
    con=duckdb.connect(); con.execute((ROOT/"schema"/"relations.sql").read_text(encoding="utf-8"))
    con.execute("CREATE TABLE Skeleton(hierarchy VARCHAR,report_node VARCHAR,category VARCHAR)")
    for row in instance.entities:
        con.execute("INSERT INTO Entity VALUES (?,?,?,?,?,?,?)",[row[k] for k in ("player_index","player_id","owner_id","entity_rec_id","entity_id","group_id","amount")])
    for row in instance.links:
        con.execute("INSERT INTO Link VALUES (?,?,?,?,?,?,?,?)",[row[k] for k in ("player_index","player_id","owner_id","link_rec_id","entity_id","attribute_id","link_value","category")])
    for row in instance.attributes:
        con.execute("INSERT INTO Attribute VALUES (?,?,?,?,?,?,?)",[row[k] for k in ("player_index","player_id","owner_id","attribute_rec_id","attribute_id","value","category")])
    con.executemany("INSERT INTO GroupClosure VALUES (?,?)",GROUP_CLOSURE)
    con.executemany("INSERT INTO Skeleton VALUES (?,?,?)",[(h,n,c) for h,coords in HIERARCHIES.items() for n,c in coords])
    return con


def sql_all_reports(instance,hierarchy):
    con=create_db(instance); n=instance.n_players
    sql=f"""
    WITH masks AS (SELECT range::BIGINT AS mask FROM range({1<<n})),
    qualified AS (
      SELECT m.mask,e.entity_id,e.group_id AS leaf_group,a.category,a.value,
             e.entity_rec_id||':'||l.link_rec_id||':'||a.attribute_rec_id AS witness_id
      FROM masks m JOIN Entity e ON ((m.mask>>e.player_index)&1)=1
      JOIN Link l ON e.entity_id=l.entity_id AND ((m.mask>>l.player_index)&1)=1
      JOIN Attribute a ON l.attribute_id=a.attribute_id AND ((m.mask>>a.player_index)&1)=1
    )
    SELECT m.mask,s.report_node,s.category,COUNT(q.witness_id)::INTEGER,
           COUNT(DISTINCT q.entity_id)::INTEGER,SUM(q.value),COALESCE(SUM(q.value),0)::DOUBLE
    FROM masks m CROSS JOIN Skeleton s JOIN GroupClosure c ON c.report_node=s.report_node
    LEFT JOIN qualified q ON q.mask=m.mask AND q.leaf_group=c.leaf_group
      AND (s.category='ALL' OR q.category=s.category)
    WHERE s.hierarchy=? GROUP BY m.mask,s.report_node,s.category ORDER BY m.mask,s.report_node,s.category
    """
    try: rows=con.execute(sql,[hierarchy]).fetchall()
    finally: con.close()
    out=defaultdict(dict)
    for mask,node,cat,bag,distinct,raw,norm in rows:
        out[mask][(node,cat)]={"bag_count":bag,"distinct_entity_count":distinct,"raw_sum":raw,"value_sum_coalesced":norm}
    return [out[m] for m in range(1<<n)]


def python_reports(instance,hierarchy):
    return [report(q2_groundings(instance,mask),hierarchy) for mask in range(1<<instance.n_players)]


def compare_reports(sql_reports,py_reports):
    mismatches=0; maxdiff=0.0
    for a,b in zip(sql_reports,py_reports,strict=True):
        if a.keys()!=b.keys(): mismatches+=1; continue
        for coord in a:
            for metric in ("bag_count","distinct_entity_count","raw_sum","value_sum_coalesced"):
                x,y=a[coord][metric],b[coord][metric]
                ok=(x is None and y is None) or (x is not None and y is not None and abs(float(x)-float(y))<=TOL)
                if not ok:mismatches+=1
                if x is not None and y is not None:maxdiff=max(maxdiff,abs(float(x)-float(y)))
    return mismatches,maxdiff


def shapley_case(instance,hierarchy,utility_id,reports,transitions=None,keys=None):
    values=[utility(r,utility_id) for r in reports]; n=instance.n_players
    phi,t_subset=timed(lambda:subset_shapley(values,n))
    phi2,t_mobius=timed(lambda:mobius_shapley(values,n))
    if max(abs(a-b) for a,b in zip(phi,phi2,strict=True))>TOL: raise AssertionError("independent Shapley oracles differ")
    if abs(sum(phi)-(values[-1]-values[0]))>TOL: raise AssertionError("efficiency failed")
    if transitions is None: keys,transitions=compile_state_transitions(reports,n)
    state_values={key:values[mask] for mask,key in enumerate(keys)}
    phi3,t_state=timed(lambda:transition_shapley(transitions,state_values,n))
    if max(abs(a-b) for a,b in zip(phi,phi3,strict=True))>TOL: raise AssertionError("state exact differs")
    return values,phi,{**{f"subset_{k}":v for k,v in t_subset.items()},
                       **{f"mobius_{k}":v for k,v in t_mobius.items()},
                       **{f"state_query_{k}":v for k,v in t_state.items()},
                       "unique_values":len(set(values)),"unique_report_states":len(set(keys)),
                       "transition_signatures":sum(len(c) for c in transitions),
                       "efficiency_error":abs(sum(phi)-(values[-1]-values[0])),
                       "oracle_max_error":max(abs(a-b) for a,b in zip(phi,phi2,strict=True)),
                       "state_max_error":max(abs(a-b) for a,b in zip(phi,phi3,strict=True))}


def linear_decomposition(instance,reports,utility_id):
    n=instance.n_players
    if utility_id == "G0-ADD-NATURAL":
        result=[0.0]*n
        for coord in sorted(reports[0]):
            for metric,weight in (("bag_count",.5),("distinct_entity_count",1.5),("value_sum_coalesced",.25)):
                part=subset_shapley([weight*float(r[coord][metric]) for r in reports],n)
                result=[a+b for a,b in zip(result,part,strict=True)]
        return result
    if utility_id not in ("G0-ADD-COMMON","G1-LOCAL-COMMON"): return None
    stats=[semantic_stats(r) for r in reports]
    if utility_id=="G0-ADD-COMMON":
        comps=(("root_distinct",lambda x:1.5*x),("root_value",lambda x:.25*x))
    else:
        comps=(("a_bag",lambda x:.5*min(x,2)),("b_distinct",lambda x:1.5*min(x,1)),("root_value",lambda x:.25*min(x,6)))
    result=[0.0]*n
    for name,fn in comps:
        part=subset_shapley([fn(s[name]) for s in stats],n)
        result=[a+b for a,b in zip(result,part,strict=True)]
    return result


def query_c_cases():
    # Structural-class controls. Q1 and Q2 share 12 players, 4+4+4 facts and 4 full groundings,
    # but intentionally have different business predicates.
    return [
        {"query":"Q0","n_players":3,"facts":"P1 Q0_F0","groundings":3,"hierarchical":True,"same_business_semantics":False,"status":"HISTORICAL_REPRODUCED_NOT_RERUN","evidence":"P1_small_truth.csv"},
        {"query":"Q1-H","n_players":8,"facts":"P1 Q1_F1_STAR","groundings":4,"hierarchical":True,"same_business_semantics":False,"status":"HISTORICAL_REPRODUCED_NOT_RERUN","evidence":"P1_small_truth.csv"},
        {"query":"Q2-NH","n_players":12,"facts":"P2 4 Entity+4 Link+4 Attribute","groundings":4,"hierarchical":False,"same_business_semantics":False,"status":"P2_MEASURED_MAIN","evidence":"P2_A1/P2_exact_shapley"},
    ]


def main():
    instances=build_instances(); structural=[structure_metrics(x) for x in instances.values()]
    report_cache={}; sql_rows=[]; cost_rows=[]; exact_rows=[]; value_rows=[]
    combos=set()
    for family in instances: combos.add((family,"H1-TREE"))
    for h in ("H0-ONE","H2-CROSS","H2-MATCH7"):combos.add(("F2-PATH-HIGH",h))
    combos.add(("F5-OUTPUT-MATCHED-LOW","H2-CROSS"))
    for family,hierarchy in sorted(combos):
        inst=instances[family]
        py,t_py=timed(lambda:python_reports(inst,hierarchy))
        sql,t_sql=timed(lambda:sql_all_reports(inst,hierarchy),repeats=3)
        mismatch,maxdiff=compare_reports(sql,py)
        if mismatch: raise AssertionError((family,hierarchy,mismatch,maxdiff))
        keys,transitions=compile_state_transitions(py,inst.n_players)
        report_cache[(family,hierarchy)]=(py,keys,transitions)
        sql_rows.append({"family":family,"hierarchy":hierarchy,"coalitions":1<<inst.n_players,"coordinates":len(HIERARCHIES[hierarchy]),
                         "sql_oracle_mismatches":mismatch,"sql_oracle_max_diff":maxdiff,
                         **{f"sql_{k}":v for k,v in t_sql.items()},**{f"python_report_{k}":v for k,v in t_py.items()}})
    # A1 source: fixed H1/G0; A2 hierarchy: fixed F2/G0; A3 value: fixed F2/H2.
    planned=[]
    planned += [("A1",f,"H1-TREE","G0-ADD-COMMON") for f in instances]
    planned += [("A2-COMMON","F2-PATH-HIGH",h,"G0-ADD-COMMON") for h in ("H0-ONE","H1-TREE","H2-CROSS","H2-MATCH7")]
    planned += [("A2-NATURAL","F2-PATH-HIGH",h,"G0-ADD-NATURAL") for h in ("H0-ONE","H1-TREE","H2-CROSS","H2-MATCH7")]
    planned += [("A3","F2-PATH-HIGH","H2-CROSS",g) for g in ("G0-ADD-COMMON","G1-LOCAL-COMMON","G2-JOINT-TASK-FULL")]
    # B: required 2x2x2 common-coordinate mapping.
    factorial=[]
    for fi,f in enumerate(("F5-OUTPUT-MATCHED-LOW","F2-PATH-HIGH")):
        for hi,h in enumerate(("H1-TREE","H2-CROSS")):
            for gi,g in enumerate(("G0-ADD-COMMON","G2-JOINT-TASK-COMMON")):
                cid=f"B{1+fi*4+hi*2+gi:02d}"; factorial.append((cid,f,h,g)); planned.append((cid,f,h,g))
    seen=set()
    case_results={}
    for phase,f,h,g in planned:
        key=(f,h,g)
        if key not in case_results:
            reports,keys,transitions=report_cache[(f,h)]
            values,phi,audit=shapley_case(instances[f],h,g,reports,transitions,keys)
            lin=linear_decomposition(instances[f],reports,g)
            linerr=None if lin is None else max(abs(a-b) for a,b in zip(phi,lin,strict=True))
            interactions=pair_interactions(values,instances[f].n_players)
            case_results[key]=(values,phi,{**audit,**interactions,"linear_decomposition_max_error":linerr})
        values,phi,audit=case_results[key]
        row={"phase":phase,"family":f,"hierarchy":h,"utility":g,"n_players":instances[f].n_players,
             "coordinates":len(HIERARCHIES[h]),"grand_utility":values[-1],"empty_utility":values[0],**audit}
        cost_rows.append(row)
        for i,payment in enumerate(phi):
            exact_rows.append({"phase":phase,"family":f,"hierarchy":h,"utility":g,"player_id":f"p{i+1}","shapley":payment,
                               "efficiency_error":audit["efficiency_error"],"oracle_max_error":audit["oracle_max_error"],"state_max_error":audit["state_max_error"]})
        value_rows.append({"phase":phase,"family":f,"hierarchy":h,"utility":g,
                           "nonzero_pair_contexts":audit["nonzero_pair_contexts"],"max_abs_second_difference":audit["max_abs_second_difference"],
                           "l1_second_differences":audit["l1_second_differences"],"g2_active":g.startswith("G2") and audit["nonzero_pair_contexts"]>0,
                           "mapping":"full frozen G2" if g.endswith("FULL") else ("frozen action A1 common-coordinate control" if "G2" in g else "not applicable")})
    # Validate exact full report match for the B low/high pair.
    full_match={}
    for h in ("H1-TREE","H2-CROSS"):
        a=report_cache[("F5-OUTPUT-MATCHED-LOW",h)][0][-1]; b=report_cache[("F2-PATH-HIGH",h)][0][-1]
        full_match[h]=a==b
        if not full_match[h]: raise AssertionError(("F5/F2 full report not matched",h,a,b))
    # Factorial rows and descriptive contrasts; no inferential p-values from timing repeats.
    factorial_rows=[]
    for cid,f,h,g in factorial:
        audit=case_results[(f,h,g)][2]
        factorial_rows.append({"case_id":cid,"F":"high" if f=="F2-PATH-HIGH" else "low","H":"cross" if h=="H2-CROSS" else "tree",
                               "G":"joint" if "G2" in g else "add","family":f,"hierarchy":h,"utility":g,
                               "full_report_matched":full_match[h],**audit})
    interaction_rows=[]
    for outcome in ("unique_report_states","transition_signatures","subset_median_seconds","state_query_median_seconds"):
        cell={(r["F"],r["H"],r["G"]):math.log1p(float(r[outcome])) for r in factorial_rows}
        for effect in ("F","H","G","F:H","F:G","H:G","F:H:G"):
            dims=effect.split(":"); contrast=0.0
            for (f,h,g),value in cell.items():
                signs={"F":1 if f=="high" else -1,"H":1 if h=="cross" else -1,"G":1 if g=="joint" else -1}
                contrast+=math.prod(signs[d] for d in dims)*value/4.0
            interaction_rows.append({"outcome":outcome,"effect":effect,"log1p_contrast":contrast,"exp_effect_ratio":math.exp(contrast),
                                     "inference":"DESCRIPTIVE_ONLY; timing repeats are not independent instance replicates"})
    # Required tables.
    by_phase=lambda prefix:[r for r in cost_rows if r["phase"].startswith(prefix)]
    write_csv("P2_A1_source_structure.csv",by_phase("A1")); write_csv("P2_A2_report_hierarchy.csv",by_phase("A2"))
    write_csv("P2_A3_value_structure.csv",[r for r in value_rows if r["phase"]=="A3"]); write_csv("P2_B_factorial_8cases.csv",factorial_rows)
    write_csv("P2_B_interaction_analysis.csv",interaction_rows); write_csv("P2_C_query_structure.csv",query_c_cases())
    write_csv("P2_exact_shapley.csv",exact_rows)
    structural_by={r["family"]:r for r in structural}
    write_csv("P2_structural_complexity.csv",[{**structural_by[r["family"]],**r} for r in sql_rows])
    methods=[
      {"method":"full coalition + subset formula","scope":"all P2 small games","status":"MEASURED_EXACT","boundary":"exponential oracle"},
      {"method":"Möbius/Harsanyi independent oracle","scope":"all P2 small games","status":"MEASURED_EXACT","boundary":"exponential independent check"},
      {"method":"coordinate linearity","scope":"G0 and G1","status":"MEASURED_EXACT","boundary":"not valid for max-coupled G2"},
      {"method":"compiled sufficient-state transitions","scope":"all P2 small games","status":"MEASURED_EXACT_AFTER_COALITION_COMPILATION","boundary":"current compiler enumerates coalitions; not a native scaling result"},
      {"method":"AB-N4-DP/H5 state methods","scope":"low-dimensional count or frozen V2 states","status":"ADAPTER_REQUIRED","boundary":"P2 JOIN evidence state differs"},
      {"method":"classical variable elimination/model counting","scope":"bounded source/value factor width","status":"STRUCTURALLY_APPLICABLE_NOT_MEASURED","boundary":"requires native joint factor adapter"},
      {"method":"Abramovich/LExaShap","scope":"Boolean output provenance after d-tree compilation","status":"ADAPTER_REQUIRED","boundary":"not direct arbitrary G2 report utility interface"},
      {"method":"Livshits/Standke-Kimelfeld","scope":"matching CQ/aggregate theorem classes","status":"THEORETICAL_BOUNDARY_ONLY","boundary":"query output, fact-player and localized-value assumptions must match"},
      {"method":"Luo independent utility","scope":"additive independent output utility","status":"APPLICABLE_TO_RESTRICTED_G0","boundary":"G2 violates independent utility"},
    ]
    write_csv("P2_existing_method_coverage.csv",methods)
    write_csv("P2_sql_oracle_audit.csv",sql_rows)
    manifest={"status":"P2_COMPLETED","p3_started":False,"families":list(instances),"full_report_pair_match":full_match,
              "sql_oracle_all_pass":all(r["sql_oracle_mismatches"]==0 for r in sql_rows),
              "max_shapley_oracle_error":max(r["oracle_max_error"] for r in cost_rows),
              "max_efficiency_error":max(r["efficiency_error"] for r in cost_rows),
              "factorial_cases":len(factorial_rows),"environment":{"python":sys.version,"duckdb":duckdb.__version__,"platform":platform.platform()},
              "skills_citation":"Kassis et al. (2026), Scientific Agent Skills, arXiv:2609.00065, doi:10.48550/arXiv.2609.00065",
              "input_hashes":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/"config"/"p2_config.json",ROOT/"schema"/"relations.sql",ROOT/"queries"/"q2_nh.sql"]}}
    (RESULTS/"P2_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    (LOGS/"P2_run.json").write_text(json.dumps({"completed_at":time.strftime("%Y-%m-%dT%H:%M:%S%z"),**manifest},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
