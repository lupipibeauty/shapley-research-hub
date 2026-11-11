from __future__ import annotations

import csv
import gc
import hashlib
import json
import math
import statistics
import sys
import time
import tracemalloc
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import duckdb


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main"
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "experiments"), str(OFFICIAL)]

from Algorithms.LExaShap.ShapleyCircuit import DNFCircuit  # noqa: E402
from aggregate_report_shapley.h3_control import (  # noqa: E402
    bag_closed_form,
    evidence_deltas,
    exact_shapley,
    generate_instance,
    joint_values,
    min_fill_width,
    minimal_witnesses,
    old_base_state,
    query_from_evidence,
    query_values,
    reachable_states,
    source_value,
)
from aggregate_report_shapley.h5_shared import (  # noqa: E402
    S4PrefixSuffix,
    S6ReverseMultilinearAD,
    SharedStateLimitExceeded,
    StateGame,
    max_abs_error,
    s0_per_focus_b2,
)
from run_ab_n2_ab_j1_2026_10_31 import run_component  # noqa: E402


OUT = ROOT / "outputs" / "v4_0" / "H3_CONTROL"
DATA = OUT / "data"
SQL_DIR = OUT / "sql"
FAMILIES = ("H", "NH")
SHARING = ("low", "medium", "high")
N_MAIN = (8, 10, 12)
SEEDS = (8201, 8202, 8203, 8204, 8205)
QUERIES = ("BAG", "DISTINCT", "HAVING2", "HAVING3")
CAP = 100_000
TOL = 1e-9

HISTORICAL = tuple(path for path in (
    ROOT / "outputs" / "v4_0" / "H3_JV" / "summary.json",
    ROOT / "reports" / "H3_JV_跨玩家JOIN与非线性整表价值联合计算审计报告_2026-11-01.md",
    ROOT / "outputs" / "v4_0" / "H0" / "literature_theorem_mapping.csv",
    ROOT / "outputs" / "v4_0" / "H5_R_2026_11_01" / "summary.json",
    ROOT / "experiments" / "run_ab_j2_2026_10_31.py",
    OFFICIAL / "Algorithms" / "LExaShap" / "ShapleyCircuit.py",
    OFFICIAL / "Algorithms" / "LExaShap" / "ShapleyEngine.py",
) if path.exists())


DDL = """
CREATE TABLE R(player_index INTEGER, x VARCHAR, region VARCHAR, category VARCHAR, amount INTEGER);
CREATE TABLE S(player_index INTEGER, x VARCHAR, y VARCHAR, region VARCHAR, category VARCHAR, amount INTEGER);
CREATE TABLE T(player_index INTEGER, join_key VARCHAR, region VARCHAR, category VARCHAR, amount INTEGER);
""".strip()


def grounding_sql(family: str) -> str:
    join = "t.join_key=s.x" if family == "H" else "t.join_key=s.y"
    return f"""SELECT 'g' || s.player_index AS grounding_id, s.x AS output_key,
 r.player_index AS r_player, s.player_index AS s_player, t.player_index AS t_player
 FROM R r JOIN S s USING(x) JOIN T t ON {join}"""


def all_coalitions_sql(family: str, n: int) -> str:
    return f"""
WITH masks AS (SELECT range::UBIGINT mask FROM range({1 << n})),
grounding AS ({grounding_sql(family)}),
selected AS (
 SELECT m.mask,g.* FROM masks m JOIN grounding g
 ON ((m.mask>>g.r_player)&1)=1 AND ((m.mask>>g.s_player)&1)=1 AND ((m.mask>>g.t_player)&1)=1
),
per_key AS (SELECT mask,output_key,COUNT(*)::BIGINT cnt FROM selected GROUP BY mask,output_key),
agg AS (
 SELECT mask,SUM(cnt)::BIGINT bag_count,COUNT(*)::BIGINT distinct_count,
 SUM((cnt>=2)::INTEGER)::BIGINT having2_count,
 SUM((cnt>=3)::INTEGER)::BIGINT having3_count
 FROM per_key GROUP BY mask
)
SELECT m.mask,COALESCE(a.bag_count,0),COALESCE(a.distinct_count,0),
 COALESCE(a.having2_count,0),COALESCE(a.having3_count,0)
FROM masks m LEFT JOIN agg a USING(mask) ORDER BY m.mask
""".strip()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields=[]
    for row in rows:
        for key in row:
            if key not in fields: fields.append(key)
    with path.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timed(call: Callable[[], Any]) -> tuple[Any, dict[str, Any]]:
    gc.collect(); tracemalloc.start(); started=time.perf_counter()
    try: result=call()
    finally:
        elapsed=time.perf_counter()-started; _cur,peak=tracemalloc.get_traced_memory(); tracemalloc.stop()
    return result,{"elapsed_seconds":elapsed,"python_peak_bytes":peak}


def create_db(instance):
    con=duckdb.connect(":memory:"); con.execute(DDL)
    con.executemany("INSERT INTO R VALUES (?,?,?,?,?)",[(f.player,f.key1,"N","C",1) for f in instance.r_facts])
    con.executemany("INSERT INTO S VALUES (?,?,?,?,?,?)",[(f.player,f.key1,f.key2,"N","C",1) for f in instance.s_facts])
    con.executemany("INSERT INTO T VALUES (?,?,?,?,?)",[(f.player,f.key1,"N","C",1) for f in instance.t_facts])
    return con


def run_sql(instance):
    con=create_db(instance); started=time.perf_counter()
    rows=con.execute(all_coalitions_sql(instance.family,instance.n)).fetchall()
    seconds=time.perf_counter()-started; con.close()
    values={query:[] for query in QUERIES}
    for _mask,bag,distinct,h2,h3 in rows:
        for query,value in zip(QUERIES,(bag,distinct,h2,h3),strict=True): values[query].append(float(value))
    return values,seconds


def state_game(instance, game_id: str, value: Callable[[tuple[int,...]],float]) -> StateGame:
    deltas=evidence_deltas(instance)
    return StateGame(f"{instance.family}-{instance.n}-{instance.sharing}-{game_id}",
        tuple(f"p{i+1}" for i in range(instance.n)),deltas,value,
        (0,)*instance.n,1,len(instance.groundings))


def run_s0(game):
    mapping,diag=s0_per_focus_b2(game,range(game.n),state_cap=CAP)
    return [mapping[i] for i in range(game.n)],diag


def run_s4(game):
    solver=S4PrefixSuffix(game,state_cap=CAP); result=solver.solve_all(); return result,solver.diagnostics()


def run_s6(game):
    solver=S6ReverseMultilinearAD(game,state_cap=CAP); result=solver.solve_all(); return result,solver.diagnostics()


def count_dtree(node) -> int:
    return 1+sum(count_dtree(child) for child in getattr(node,"children",[]) or [])


def official_components(instance,query):
    components=minimal_witnesses(instance,query)
    payments={f"p{i+1}":0.0 for i in range(instance.n)}
    compile_s=solve_s=0.0; nodes=0; clauses=0; occurrences=0
    for dnf,weight,_key in components:
        canonical=sorted({tuple(sorted(c)) for c in dnf})
        if not canonical: continue
        dnf_sets=[set(c) for c in canonical]
        result,cost=run_component(dnf_sets,weight)
        for player,value in result.items(): payments[player]+=value
        compile_s+=cost["official_dtree_compile_seconds"]; solve_s+=cost["official_backward_solve_seconds"]
        circuit=DNFCircuit(dnf_sets); nodes+=count_dtree(circuit.root)
        clauses+=len(dnf_sets); occurrences+=sum(len(c) for c in dnf_sets)
    return [payments[f"p{i+1}"] for i in range(instance.n)],{
        "official_compile_seconds":compile_s,"official_solve_seconds":solve_s,
        "official_dtree_nodes":nodes,"dnf_clauses":clauses,"variable_occurrences":occurrences,
        "component_count":len(components)}


def minimal_counterexample():
    con=duckdb.connect(":memory:")
    con.execute("CREATE TABLE R(player_index INT,x VARCHAR,region VARCHAR,category VARCHAR,amount INT)")
    con.execute("CREATE TABLE S(player_index INT,x VARCHAR,y VARCHAR,region VARCHAR,category VARCHAR,amount INT)")
    con.execute("CREATE TABLE T(player_index INT,y VARCHAR,region VARCHAR,category VARCHAR,amount INT)")
    con.executemany("INSERT INTO R VALUES (?,?,?,?,?)",[(0,"A","N","C",1),(1,"B","N","C",1)])
    con.execute("INSERT INTO S VALUES (2,'A','Y','N','C',1)"); con.execute("INSERT INTO T VALUES (3,'Y','N','C',1)")
    sql="""SELECT COUNT(*) FROM R r JOIN S s USING(x) JOIN T t USING(y)
      WHERE ((? >> r.player_index)&1)=1 AND ((? >> s.player_index)&1)=1 AND ((? >> t.player_index)&1)=1"""
    rows=[]
    for label,mask in (("S1",13),("S2",14),("S3",5),("S4",6),("S3_plus_p4",13),("S4_plus_p4",14)):
        value=int(con.execute(sql,[mask,mask,mask]).fetchone()[0])
        old=(sum(bool(mask&(1<<p)) for p in (0,1)),int(bool(mask&4)),int(bool(mask&8)))
        rows.append({"coalition":label,"mask":mask,"players":";".join(f"p{i+1}" for i in range(4) if mask&(1<<i)),"old_base_state":json.dumps(old),"join_count":value})
    con.close()
    rows[2]["add_p4_marginal"]=rows[4]["join_count"]-rows[2]["join_count"]
    rows[3]["add_p4_marginal"]=rows[5]["join_count"]-rows[3]["join_count"]
    return rows


def semantic_audit_rows():
    return [
        {"historical_or_current":"H3_JV_HISTORY","query":"q() :- R(x),S(x,y),T(y)","free_variables":"none","existential_variables":"x,y","atom_sets":"x:{R,S}; y:{S,T}","hierarchical":"NO","all_hierarchical":"NOT_APPLICABLE_AS_FREE_VAR_NOTION","fact_player_assumption":"NO: p9-p12 bundle two S facts","judgment":"historical non-hierarchical shape correct, theorem application requires bundle-to-fact reduction"},
        {"historical_or_current":"CALIBRATION","query":"q(x) :- R(x),S(x,y),T(y)","free_variables":"x","existential_variables":"y","atom_sets":"x:{R,S}; y:{S,T}","hierarchical":"NO","all_hierarchical":"NO","fact_player_assumption":"requires one fact per player","judgment":"cannot inherit Boolean q() classification without checking free-variable condition"},
        {"historical_or_current":"CALIBRATION","query":"business-key output x / COUNT DISTINCT x","free_variables":"x","existential_variables":"y","atom_sets":"x:{R,S}; y:{S,T}","hierarchical":"NO","all_hierarchical":"NO","fact_player_assumption":"satisfied in H3-CONTROL","judgment":"distinct OR lineage; bag closed form invalid"},
        {"historical_or_current":"CALIBRATION","query":"COUNT(*) over q()","free_variables":"aggregate only","existential_variables":"x,y","atom_sets":"x:{R,S}; y:{S,T}","hierarchical":"NO","all_hierarchical":"not enough alone","fact_player_assumption":"satisfied in H3-CONTROL","judgment":"linear grounding game has closed form despite query shape"},
        {"historical_or_current":"CALIBRATION","query":"GROUP BY x HAVING COUNT(*)>=h then outer COUNT","free_variables":"outer aggregate","existential_variables":"x,y","atom_sets":"x:{R,S}; y:{S,T}","hierarchical":"nested threshold query","all_hierarchical":"not directly covered by flat CQ label","fact_player_assumption":"satisfied in H3-CONTROL","judgment":"manual minimal-witness compilation; do not claim direct theorem coverage"},
        {"historical_or_current":"H3_CONTROL_H","query":"q_H() :- R(x),S(x,y),T(x)","free_variables":"none","existential_variables":"x,y","atom_sets":"x:{R,S,T}; y:{S}","hierarchical":"YES","all_hierarchical":"YES for q_H(x) nesting","fact_player_assumption":"YES","judgment":"paired tractable-structure control"},
    ]


def unique_structure_seeds(n: int, sharing: str, count: int = 5) -> tuple[int, ...]:
    """Select by input edge-hash only, never by performance or result."""
    chosen=[]; seen=set()
    for seed in range(8201,8400):
        instance=generate_instance("H",n,sharing,seed)
        signature=";".join(f"{f.key1}-{f.key2}" for f in instance.s_facts)
        digest=hashlib.sha256(signature.encode()).hexdigest()
        if digest in seen: continue
        seen.add(digest); chosen.append(seed)
        if len(chosen)==count: return tuple(chosen)
    raise RuntimeError(f"not enough unique structures for n={n}, sharing={sharing}")


def main():
    OUT.mkdir(parents=True,exist_ok=True); DATA.mkdir(parents=True,exist_ok=True); SQL_DIR.mkdir(parents=True,exist_ok=True)
    before={str(p.relative_to(ROOT)):sha256(p) for p in HISTORICAL}
    write_csv(OUT/"theory_semantics_and_history_corrections.csv",semantic_audit_rows())
    counter=minimal_counterexample(); write_csv(OUT/"minimal_old_state_counterexample.csv",counter)
    if counter[0]["old_base_state"]!=counter[1]["old_base_state"] or counter[0]["join_count"]==counter[1]["join_count"]: raise AssertionError("minimal counterexample failed")
    (SQL_DIR/"create_paired_relations.sql").write_text(DDL,encoding="utf-8")
    for family in FAMILIES: (SQL_DIR/f"family_{family.lower()}_all_coalitions.sql").write_text(all_coalitions_sql(family,12),encoding="utf-8")

    match_rows=[]; structure_rows=[]; truth_rows=[]; perf_rows=[]; payment_rows=[]; failure_rows=[]; sample_data=[]
    total_instances=0
    for n in N_MAIN:
      for sharing in SHARING:
       for seed in unique_structure_seeds(n,sharing):
        paired={family:generate_instance(family,n,sharing,seed) for family in FAMILIES}
        # Exact structural matching gate.
        h,nh=paired["H"],paired["NH"]
        edge_signature=";".join(f"{f.key1}-{f.key2}" for f in h.s_facts)
        edge_hash=hashlib.sha256(edge_signature.encode()).hexdigest()
        match_rows.append({"n":n,"sharing":sharing,"seed":seed,"edge_hash":edge_hash,"edge_signature":edge_signature,"h_facts":n,"nh_facts":n,"h_groundings":len(h.groundings),"nh_groundings":len(nh.groundings),"h_keys":len({g.output_key for g in h.groundings}),"nh_keys":len({g.output_key for g in nh.groundings}),"matched_players":True,"matched_facts":True,"matched_groundings":len(h.groundings)==len(nh.groundings),"matched_keys":len({g.output_key for g in h.groundings})==len({g.output_key for g in nh.groundings})})
        for family,instance in paired.items():
            total_instances+=1; print(f"MAIN {family} n={n} {sharing} seed={seed}",flush=True)
            if seed==SEEDS[0]:
                for fact in instance.r_facts+instance.s_facts+instance.t_facts: sample_data.append({"family":family,"n":n,"sharing":sharing,"seed":seed,"player":f"p{fact.player+1}","relation":fact.relation,"key1":fact.key1,"key2":fact.key2})
            sql_values,sql_seconds=run_sql(instance)
            max_source_error=0.0
            truths={}
            for query in QUERIES:
                components=minimal_witnesses(instance,query)
                for mask in range(1<<n):
                    selected={f"p{i+1}" for i in range(n) if mask&(1<<i)}
                    max_source_error=max(max_source_error,abs(source_value(components,selected)-sql_values[query][mask]))
                truths[query]=exact_shapley(sql_values[query],n)
                for player,value in enumerate(truths[query]): truth_rows.append({"family":family,"n":n,"sharing":sharing,"seed":seed,"query":query,"player":f"p{player+1}","exact_shapley":value})
            if max_source_error>TOL: raise AssertionError(max_source_error)
            bag=bag_closed_form(instance); bag_error=max_abs_error(bag,truths["BAG"])
            if bag_error>TOL: raise AssertionError(bag_error)
            base_states,evidence_states=reachable_states(instance)
            # Old state sufficiency audit.
            old_groups=defaultdict(list)
            for mask in range(1<<n): old_groups[old_base_state(instance,mask)].append(mask)
            old_conflicts=sum(len({sql_values["DISTINCT"][m] for m in masks})>1 for masks in old_groups.values())
            components_by_query={q:minimal_witnesses(instance,q) for q in QUERIES}
            dnf={q:sum(len(d) for d,_w,_k in components_by_query[q]) for q in QUERIES}
            occurrences={q:sum(len(c) for d,_w,_k in components_by_query[q] for c in d) for q in QUERIES}
            degrees=[sum(p in g.clause for g in instance.groundings) for p in range(n)]
            structure_rows.append({"family":family,"n":n,"sharing":sharing,"seed":seed,"physical_facts":n,"logical_players":n,"effective_players":sum(d>0 for d in degrees),"groundings":len(instance.groundings),"distinct_keys":len({g.output_key for g in instance.groundings}),"mean_player_grounding_degree":statistics.mean(degrees),"max_player_grounding_degree":max(degrees),"increment_signature_types":len(set(evidence_deltas(instance))),"old_base_states":base_states,"old_state_distinct_conflict_groups":old_conflicts,"reachable_evidence_states":evidence_states,"min_fill_width":min_fill_width(instance),"bag_dnf_clauses":dnf["BAG"],"distinct_dnf_clauses":dnf["DISTINCT"],"having2_dnf_clauses":dnf["HAVING2"],"having3_dnf_clauses":dnf["HAVING3"],"distinct_variable_occurrences":occurrences["DISTINCT"],"sql_all_coalitions_seconds":sql_seconds,"source_max_error":max_source_error,"bag_closed_form_max_error":bag_error})
            perf_rows.append({"family":family,"n":n,"sharing":sharing,"seed":seed,"query":"BAG","method":"B1_GROUNDING_CLOSED_FORM","status":"SUCCESS_EXACT","elapsed_seconds":0.0,"max_error":bag_error,"preprocessing_seconds":0.0,"end_to_end_seconds":0.0})
            # S6 DISTINCT on all independent instances.
            game=state_game(instance,"DISTINCT",lambda state,i=instance:query_from_evidence(i,state,"DISTINCT"))
            try:
                (allocation,diag),cost=timed(lambda g=game:run_s6(g)); error=max_abs_error(allocation,truths["DISTINCT"])
                if error>TOL: raise AssertionError(error)
                perf_rows.append({"family":family,"n":n,"sharing":sharing,"seed":seed,"query":"DISTINCT","method":"B7_S6","status":"SUCCESS_EXACT","max_error":error,"preprocessing_seconds":diag.get("shared_preprocess_seconds",0),"end_to_end_seconds":cost["elapsed_seconds"],"python_peak_bytes":cost["python_peak_bytes"],**diag})
            except SharedStateLimitExceeded as exc:
                failure_rows.append({"family":family,"n":n,"sharing":sharing,"seed":seed,"query":"DISTINCT","method":"B7_S6","reason_category":"RESOURCE_STATE_CAP","detail":str(exc)})
            # Full strong baselines on one seed per config.
            if seed==SEEDS[0]:
                for query in QUERIES:
                    game=state_game(instance,query,lambda state,i=instance,q=query:query_from_evidence(i,state,q))
                    for method,call in (("B4_STATE_DP",lambda g=game:run_s0(g)),("B6_S4",lambda g=game:run_s4(g))):
                        try:
                            (allocation,diag),cost=timed(call); error=max_abs_error(allocation,truths[query])
                            if error>TOL: raise AssertionError(error)
                            perf_rows.append({"family":family,"n":n,"sharing":sharing,"seed":seed,"query":query,"method":method,"status":"SUCCESS_EXACT","max_error":error,"preprocessing_seconds":diag.get("shared_preprocess_seconds",0),"end_to_end_seconds":cost["elapsed_seconds"],"python_peak_bytes":cost["python_peak_bytes"],**diag})
                        except SharedStateLimitExceeded as exc: failure_rows.append({"family":family,"n":n,"sharing":sharing,"seed":seed,"query":query,"method":method,"reason_category":"RESOURCE_STATE_CAP","detail":str(exc)})
                if n==12:
                    for query in QUERIES:
                        (allocation,diag),cost=timed(lambda i=instance,q=query:official_components(i,q)); error=max_abs_error(allocation,truths[query])
                        if error>TOL: raise AssertionError(error)
                        perf_rows.append({"family":family,"n":n,"sharing":sharing,"seed":seed,"query":query,"method":"B2_ABRAMOVICH","status":"SUCCESS_EXACT","max_error":error,"preprocessing_seconds":diag["official_compile_seconds"],"end_to_end_seconds":cost["elapsed_seconds"],"python_peak_bytes":cost["python_peak_bytes"],**diag})
    write_csv(DATA/"paired_instance_sample_facts.csv",sample_data); write_csv(OUT/"pair_matching.csv",match_rows); write_csv(OUT/"structure_and_state_metrics.csv",structure_rows); write_csv(OUT/"exact_shapley_truth.csv",truth_rows); write_csv(OUT/"algorithm_performance_raw.csv",perf_rows)

    # Representative matched n=12 high-sharing G1/G2.
    joint_rows=[]; joint_payments=[]
    for family in FAMILIES:
        instance=generate_instance(family,12,"high",SEEDS[0]); raw,_=run_sql(instance)
        full={q:raw[q][-1] for q in QUERIES}
        for game_id in ("G1","G2"):
            values=[joint_values({q:raw[q][m] for q in QUERIES},full)[game_id] for m in range(1<<12)]
            truth=exact_shapley(values,12)
            game=state_game(instance,game_id,lambda state,i=instance,f=full,g=game_id:joint_values({q:query_from_evidence(i,state,q) for q in QUERIES},f)[g])
            for method,call in (("B0",lambda v=values:(exact_shapley(v,12),{})),("B4_STATE_DP",lambda g=game:run_s0(g)),("B6_S4",lambda g=game:run_s4(g)),("B7_S6",lambda g=game:run_s6(g))):
                for repeat in range(3):
                    (allocation,diag),cost=timed(call); error=max_abs_error(allocation,truth)
                    if error>TOL: raise AssertionError(error)
                    joint_rows.append({"family":family,"n":12,"sharing":"high","seed":SEEDS[0],"game_id":game_id,"method":method,"repeat":repeat,"end_to_end_seconds":cost["elapsed_seconds"],"python_peak_bytes":cost["python_peak_bytes"],"max_error":error,**diag})
                for p,(estimate,expected) in enumerate(zip(allocation,truth,strict=True)): joint_payments.append({"family":family,"game_id":game_id,"method":method,"player":f"p{p+1}","shapley":estimate,"truth":expected,"absolute_error":abs(estimate-expected)})
    write_csv(OUT/"joint_value_performance.csv",joint_rows); write_csv(OUT/"joint_value_shapley.csv",joint_payments)

    # Finite scale n=14/16 representative high-sharing pairs.
    scale_rows=[]
    for n in (14,16):
      for family in FAMILIES:
        instance=generate_instance(family,n,"high",8300+n); print(f"SCALE {family} n={n}",flush=True)
        try:
            raw,sql_s=run_sql(instance); truth=exact_shapley(raw["DISTINCT"],n)
            game=state_game(instance,"DISTINCT",lambda state,i=instance:query_from_evidence(i,state,"DISTINCT"))
            (allocation,diag),cost=timed(lambda g=game:run_s6(g)); error=max_abs_error(allocation,truth)
            status="SUCCESS_EXACT" if error<=TOL else "CORRECTNESS_FAIL"
            scale_rows.append({"family":family,"n":n,"sharing":"high","seed":8300+n,"status":status,"sql_seconds":sql_s,"s6_seconds":cost["elapsed_seconds"],"max_error":error,"reachable_frontier":diag.get("maximum_frontier_states"),"state_transitions":diag.get("state_transitions"),"python_peak_bytes":cost["python_peak_bytes"]})
        except SharedStateLimitExceeded as exc:
            scale_rows.append({"family":family,"n":n,"sharing":"high","seed":8300+n,"status":"STATE_CAP_EXCEEDED","detail":str(exc)})
            failure_rows.append({"family":family,"n":n,"sharing":"high","seed":8300+n,"query":"DISTINCT","method":"B7_S6","reason_category":"RESOURCE_STATE_CAP","detail":str(exc)})
    write_csv(OUT/"scale_results.csv",scale_rows)
    if not failure_rows: failure_rows=[{"family":"ALL","n":"","sharing":"","seed":"","query":"","method":"","reason_category":"NO_RESOURCE_FAILURES","detail":"All planned runs completed"}]
    write_csv(OUT/"failures_and_skips.csv",failure_rows)

    # Static algorithm applicability and theory mapping.
    applicability=[]
    for query in QUERIES:
      applicability.extend([
        {"method":"B0","query":query,"status":"APPLICABLE_EXACT","boundary":"exponential truth only"},
        {"method":"B1_BAG_CLOSED","query":query,"status":"APPLICABLE_EXACT" if query=="BAG" else "NOT_APPLICABLE_OR_AND_THRESHOLD","boundary":"grounding weight split only"},
        {"method":"B2_ABRAMOVICH","query":query,"status":"APPLICABLE_AFTER_MANUAL_DNF","boundary":"official SQL frontend absent; d-tree size instance dependent"},
        {"method":"B3_KNOWLEDGE_COMPILATION","query":query,"status":"SAME_DNF_CIRCUIT_EVIDENCE_AS_B2","boundary":"not separately timed as a different algorithm"},
        {"method":"B4_STATE_DP","query":query,"status":"APPLICABLE_EXACT","boundary":"evidence-state frontier may approach coalitions"},
        {"method":"B5_VARIABLE_ELIMINATION","query":query,"status":"STRUCTURAL_WIDTH_AUDITED_NOT_SEPARATE_SOLVER","boundary":"min-fill width recorded; no claim of optimized implementation"},
        {"method":"B6_S4","query":query,"status":"APPLICABLE_EXACT","boundary":"shared prefix/suffix state"},
        {"method":"B7_S6","query":query,"status":"APPLICABLE_EXACT","boundary":"multilinear expectation circuit"},
      ])
    write_csv(OUT/"algorithm_applicability.csv",applicability)
    after={str(p.relative_to(ROOT)):sha256(p) for p in HISTORICAL}
    if before!=after: raise AssertionError("history changed")
    write_json(OUT/"historical_hashes.json",{"before":before,"after":after,"unchanged":True})
    summary={"status":"H3_CONTROL_COMPLETED_AND_PAUSED","main_instances":total_instances,"main_configs":len(N_MAIN)*len(SHARING)*len(FAMILIES),"instances_per_config":len(SEEDS),"full_truth_n_max":16,"all_source_checks_passed":True,"historical_unchanged":True,"new_algorithm_claimed":False}
    write_json(OUT/"summary.json",summary); print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__": main()
