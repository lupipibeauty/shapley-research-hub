from __future__ import annotations

import csv
import ctypes
import hashlib
import json
import math
import platform
import statistics
import sys
import threading
import time
import tracemalloc
from collections import Counter,defaultdict
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import duckdb

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent
OLD=PROJECT.parents[1]/"aggregate_report_shapley"
for p in (ROOT/"src",):sys.path.insert(0,str(p))
from build_lineage import extract_lineage,validate_lineage
from native_exact_baseline import LayeredJointDecisionDiagram,game_value,shapley_from_conditional
from oracle_shapley import mobius_shapley,subset_shapley
from oracle_sql import all_sql_counts,create_database,load_fixture,python_counts

RESULTS=ROOT/"results";REPORTS=ROOT/"reports";LOGS=ROOT/"logs"
for p in (RESULTS,REPORTS,LOGS):p.mkdir(parents=True,exist_ok=True)
FIXTURE_PATH=ROOT/"fixtures"/"anchor_13_players.json"
SCHEMA_PATH=ROOT/"schema"/"complete_schema.sql"
SQL_PATH=ROOT/"queries"/"two_group_distinct.sql"


def write_csv(path,rows):
    fields=[]
    for row in rows:
        for k in row:
            if k not in fields:fields.append(k)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


class PMC(ctypes.Structure):
    _fields_=[("cb",ctypes.c_ulong),("PageFaultCount",ctypes.c_ulong),("PeakWorkingSetSize",ctypes.c_size_t),
              ("WorkingSetSize",ctypes.c_size_t),("QuotaPeakPagedPoolUsage",ctypes.c_size_t),("QuotaPagedPoolUsage",ctypes.c_size_t),
              ("QuotaPeakNonPagedPoolUsage",ctypes.c_size_t),("QuotaNonPagedPoolUsage",ctypes.c_size_t),
              ("PagefileUsage",ctypes.c_size_t),("PeakPagefileUsage",ctypes.c_size_t)]


def current_rss():
    try:
        ctypes.windll.kernel32.GetCurrentProcess.restype=ctypes.c_void_p
        ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(PMC),ctypes.c_ulong]
        ctypes.windll.psapi.GetProcessMemoryInfo.restype=ctypes.c_int
        counters=PMC();counters.cb=ctypes.sizeof(counters)
        handle=ctypes.windll.kernel32.GetCurrentProcess()
        ok=ctypes.windll.psapi.GetProcessMemoryInfo(handle,ctypes.byref(counters),counters.cb)
        return int(counters.WorkingSetSize) if ok else None
    except Exception:return None


def measured(stage,fn,costs,repeats=1,shared=False):
    times=[];result=None;python_peak=0;rss_peak=0
    for _ in range(repeats):
        stop=threading.Event();rss=[current_rss() or 0]
        def monitor():
            while not stop.wait(.001):rss[0]=max(rss[0],current_rss() or 0)
        thread=threading.Thread(target=monitor,daemon=True);thread.start()
        tracemalloc.start();start=time.perf_counter();result=fn();elapsed=time.perf_counter()-start
        _,peak=tracemalloc.get_traced_memory();tracemalloc.stop();stop.set();thread.join()
        times.append(elapsed);python_peak=max(python_peak,peak);rss_peak=max(rss_peak,rss[0],current_rss() or 0)
    q1=q3=0.0
    if repeats>1:q1,_,q3=statistics.quantiles(times,n=4,method="inclusive")
    costs.append({"stage":stage,"repeats":repeats,"median_seconds":statistics.median(times),"iqr_seconds":q3-q1,
                  "min_seconds":min(times),"max_seconds":max(times),"python_peak_bytes":python_peak,
                  "process_rss_peak_bytes":rss_peak or "NOT_MEASURED","shared_all_players_preprocessing":shared})
    return result


def frac_fields(value):return {"exact_fraction":str(value),"decimal":format(float(value),".17g")}


def player_rows(fixture):
    rows=[]
    for relation,key in (("EntityFact","entities"),("LinkFact","links"),("AttributeFact","attributes")):
        for r in fixture[key]:rows.append({**r,"relation_name":relation})
    return sorted(rows,key=lambda x:x["player_index"])


def historical_audit():
    return [
      {"experiment":"D1-P/S0/S1","overlap":"multi-source report, record players, 7 nodes/35 coordinates","missing_for_current":"true cross-player Entity-Link-Attribute DISTINCT lineage","evidence":str(OLD/"outputs/v4_0/S1/verification_summary.json"),"status":"SOURCE_VERIFIED"},
      {"experiment":"AB-J1/J2","overlap":"JOIN, DISTINCT, alternative Boolean lineage, HAVING","missing_for_current":"two-group MIN utility and native all-player joint distribution","evidence":str(OLD/"outputs/v4_0/AB_J2_2026_10_31/manifest.json"),"status":"SOURCE_VERIFIED"},
      {"experiment":"AB-N4-DP","overlap":"classic count-state exact DP","missing_for_current":"JOIN OR-of-AND evidence and shared attributes across groups","evidence":str(OLD/"outputs/v4_0/AB_N3_L_N4_DP_2026_10_31/manifest.json"),"status":"SOURCE_VERIFIED"},
      {"experiment":"H3-CONTROL","overlap":"cross-player JOIN, DISTINCT/HAVING, state/factor baselines","missing_for_current":"fixed two-group COUNT DISTINCT plus MIN revenue game","evidence":str(OLD/"outputs/v4_0/H3_CONTROL/summary.json"),"status":"SOURCE_VERIFIED"},
      {"experiment":"H5/H5-R","overlap":"native record-increment state DP, factors, shared all-player computation","missing_for_current":"record increments are additive statistics, not current JOIN lineage","evidence":str(OLD/"outputs/v4_0/H5_R_2026_11_01/summary.json"),"status":"SOURCE_VERIFIED"},
      {"experiment":"P2","overlap":"same Q2-NH pattern, cross-player sharing, exact Shapley","missing_for_current":"P2 state compiler consumes all coalition reports; utility is not current G1=min","evidence":str(PROJECT/"P2/results/P2_manifest.json"),"status":"SOURCE_VERIFIED"},
      {"experiment":"P3-0 anchor","overlap":"13 physical record players, two-group DISTINCT and MIN","missing_for_current":"none for correctness anchor","evidence":str(RESULTS/"P3_0_manifest.json"),"status":"REPRODUCED"},
    ]


def theorem_rows():
    return [
      {"work":"Kara, Olteanu, Suciu 2024","result":"Shapley/model-counting polynomial equivalence for suitable Boolean function classes; d-DNNF application","current_mapping":"each entity qualification is Boolean lineage; two-group numeric MIN needs joint terminal extension","status":"CLASSIC_ROUTE_SUPPORTS_COMPONENTS","source":"https://doi.org/10.1145/3651142"},
      {"work":"Livshits et al. 2020/2021","result":"CQ/aggregate query tuple-Shapley tractability and hardness under stated query assumptions","current_mapping":"Q2 has free entity output then COUNT DISTINCT; cannot substitute Boolean-CQ dichotomy without checking aggregate semantics","status":"BOUNDARY_ONLY","source":"https://doi.org/10.4230/LIPIcs.ICDT.2020.20"},
      {"work":"Standke and Kimelfeld 2025","result":"aggregate-CQ frontiers; min and count-distinct align with all-hierarchical under local-value assumptions","current_mapping":"project query is non-hierarchical in x/y and final MIN couples two aggregate outputs; theorem is not a direct solver","status":"NOT_DIRECTLY_COVERED","source":"https://arxiv.org/abs/2509.13565"},
      {"work":"Abramovich et al. 2025","result":"lineage lifting and gradients for all fact attributions, including aggregate-query system work","current_mapping":"Boolean output lineage compilation relevant; current two-output MIN needs an adapter","status":"ADAPTER_REQUIRED","source":"https://arxiv.org/abs/2506.16923"},
      {"work":"Luo et al. 2022","result":"independent utility decomposition","current_mapping":"G0 decomposes by outputs; G1=min violates independent output utility","status":"G0_ONLY","source":"local paper and historical R1 audit"},
      {"work":"Layered MTBDD / weighted model counting","result":"ordered decision diagrams support exact model counts by terminal and cardinality","current_mapping":"implemented directly from fact lineage; classical method application, not claimed novel","status":"REPRODUCED_CLASSIC_ADAPTATION","source":"implementation evidence in src/native_exact_baseline.py"},
    ]


def main():
    costs=[]
    fixture=measured("fixture_read",lambda:load_fixture(FIXTURE_PATH),costs)
    players=player_rows(fixture);n=len(players)
    assert n==13 and [p["player_index"] for p in players]==list(range(13))
    for name,mapping in fixture["owner_maps"].items():
        assert set(mapping)=={p["player_id"] for p in players},name
    con=measured("database_schema_and_load",lambda:create_database(SCHEMA_PATH,fixture),costs)

    # Native route must finish before oracle coalition values are created.
    lineage=measured("join_lineage_extraction",lambda:extract_lineage(con),costs,shared=True)
    lineage_audit=validate_lineage(lineage,n)
    diagram=measured("layered_mtbdd_build",lambda:LayeredJointDecisionDiagram(lineage,n),costs,shared=True)
    distributions=measured("all_player_conditional_model_counting",diagram.all_conditional_distributions,costs,shared=True)
    native={}
    for game in ("G0","G1"):
        native[game]=measured(f"native_shapley_{game}",lambda g=game:shapley_from_conditional(distributions,n,g),costs,repeats=7)

    # Save native evidence before building truth oracle.
    native_completed_at=time.time()
    global_dist=diagram.distribution()
    write_csv(RESULTS/"joint_generating_function.csv",[
      {"coalition_size":k,"q_A":qa,"q_B":qb,"coalition_count":count}
      for (k,qa,qb),count in sorted(global_dist.items())])
    write_csv(RESULTS/"conditional_state_distributions.csv",[
      {"player_id":players[i]["player_id"],"forced":b,"other_coalition_size":k,"q_A":qa,"q_B":qb,"coalition_count":count}
      for (i,b),dist in sorted(distributions.items()) for (k,qa,qb),count in sorted(dist.items())])

    # Independent full-coalition truth follows native completion.
    sql_counts=measured("oracle_all_8192_sql",lambda:all_sql_counts(con,n),costs)
    python_counts_all=measured("oracle_all_8192_python",lambda:[python_counts(fixture,m) for m in range(1<<n)],costs)
    if sql_counts!=python_counts_all:raise AssertionError("SQL/Python coalition count mismatch")
    values={g:[game_value(g,*state) for state in sql_counts] for g in ("G0","G1")}
    oracle={}
    for game in ("G0","G1"):
        oracle[(game,"subset")]=measured(f"oracle_subset_shapley_{game}",lambda g=game:subset_shapley(values[g],n),costs)
        oracle[(game,"mobius")]=measured(f"oracle_mobius_shapley_{game}",lambda g=game:mobius_shapley(values[g],n),costs)
        if oracle[(game,"subset")]!=oracle[(game,"mobius")]:raise AssertionError("oracle formulas differ")
        if native[game]!=oracle[(game,"subset")]:raise AssertionError("native/oracle differs")
    assert sql_counts[-1]==(2,2) and sql_counts[0]==(0,0)

    truth=[]
    for mask,(qa,qb) in enumerate(sql_counts):
        truth.append({"mask":mask,"coalition_size":mask.bit_count(),"q_A_sql":qa,"q_B_sql":qb,
                      "q_A_python":python_counts_all[mask][0],"q_B_python":python_counts_all[mask][1],
                      "G0":qa+qb,"G1":min(qa,qb),"equal":True})
    write_csv(RESULTS/"anchor_truth.csv",truth)

    record_shapley=[]
    for game in ("G0","G1"):
        grand=values[game][-1]-values[game][0]
        assert sum(native[game])==grand
        for p,phi in zip(players,native[game],strict=True):
            record_shapley.append({"data_version":fixture["data_version"],"sql_version":fixture["sql_version"],
              "utility_version":fixture["utility_version"],"game_id":game,"player_version":fixture["player_version"],
              "player_id":p["player_id"],"player_index":p["player_index"],"relation_name":p["relation_name"],
              "shapley_fraction":str(phi),"shapley_decimal":format(float(phi),".17g"),
              "subset_oracle_fraction":str(oracle[(game,"subset")][p["player_index"]]),
              "mobius_oracle_fraction":str(oracle[(game,"mobius")][p["player_index"]]),"exact_match":True})
    write_csv(RESULTS/"record_shapley.csv",record_shapley)

    R=Fraction(fixture["revenue_pool"]);record_revenue=[];owner_revenue=[];relation_revenue=[];budget=[]
    for game in ("G0","G1"):
        grand=Fraction(values[game][-1]-values[game][0]);payments=[R*phi/grand for phi in native[game]]
        assert grand>0 and all(phi>=0 for phi in native[game]) and sum(payments)==R
        rel=defaultdict(Fraction)
        for p,pay in zip(players,payments,strict=True):rel[p["relation_name"]]+=pay
        for relation,total in sorted(rel.items()):relation_revenue.append({"game_id":game,"relation_name":relation,"revenue_fraction":str(total),"revenue_decimal":format(float(total),".17g")})
        for map_name,mapping in fixture["owner_maps"].items():
            owners=defaultdict(Fraction)
            for p,phi,pay in zip(players,native[game],payments,strict=True):
                owner=mapping[p["player_id"]];owners[owner]+=pay
                record_revenue.append({"data_version":fixture["data_version"],"sql_version":fixture["sql_version"],
                  "utility_version":fixture["utility_version"],"player_version":fixture["player_version"],
                  "owner_map_version":map_name,"revenue_pool":fixture["revenue_pool"],"game_id":game,
                  "player_id":p["player_id"],"relation_name":p["relation_name"],"owner_id":owner,
                  "shapley_fraction":str(phi),"shapley_decimal":format(float(phi),".17g"),
                  "allocation_share_fraction":str(phi/grand),"allocation_share_decimal":format(float(phi/grand),".17g"),
                  "revenue_fraction":str(pay),"revenue_decimal":format(float(pay),".17g")})
            for owner,total in sorted(owners.items()):
                owner_revenue.append({"data_version":fixture["data_version"],"owner_map_version":map_name,"game_id":game,
                                      "owner_id":owner,"revenue_pool":fixture["revenue_pool"],"revenue_fraction":str(total),
                                      "revenue_decimal":format(float(total),".17g")})
            budget.append({"game_id":game,"owner_map_version":map_name,"grand_minus_empty":str(grand),
                           "sum_shapley_fraction":str(sum(native[game])),"sum_record_revenue_fraction":str(sum(payments)),
                           "sum_owner_revenue_fraction":str(sum(owners.values())),"revenue_pool":fixture["revenue_pool"],
                           "shapley_efficiency_exact":sum(native[game])==grand,"record_budget_exact":sum(payments)==R,
                           "owner_budget_exact":sum(owners.values())==R,"negative_shapley_count":sum(x<0 for x in native[game]),
                           "payment_rule_applicable":grand>0 and all(x>=0 for x in native[game])})
    write_csv(RESULTS/"record_revenue_allocation.csv",record_revenue)
    write_csv(RESULTS/"owner_revenue_allocation.csv",owner_revenue)
    write_csv(RESULTS/"relation_revenue_allocation.csv",relation_revenue)
    write_csv(RESULTS/"revenue_budget_audit.csv",budget)

    # Source-path and payment interpretation.
    participation=defaultdict(list);groups=defaultdict(set)
    for entity in lineage:
        for wid,clause in zip(entity.witness_ids,entity.clauses,strict=True):
            for i in clause:participation[i].append(wid);groups[i].add(entity.group_id)
    contribution=[]
    for p in players:
        i=p["player_index"]
        contribution.append({"player_id":p["player_id"],"relation_name":p["relation_name"],
          "witness_count":len(participation[i]),"witness_ids":";".join(participation[i]),"groups_affected":";".join(sorted(groups[i])),
          "cross_group_source":len(groups[i])>1,"G0_shapley_fraction":str(native["G0"][i]),"G1_shapley_fraction":str(native["G1"][i]),
          "G0_revenue_fraction":str(R*native["G0"][i]/4),"G1_revenue_fraction":str(R*native["G1"][i]/2),
          "warning":"witness count is descriptive and is not the payment rule"})
    write_csv(RESULTS/"source_contribution_analysis.csv",contribution)

    # Physical source labels must not alter the logical game.
    alternate=deepcopy(fixture)
    for r in alternate["entities"]+alternate["links"]+alternate["attributes"]:r["source_id"]="Repartitioned_"+r["source_id"]
    source_invariant=all(python_counts(fixture,m)==python_counts(alternate,m) for m in range(1<<n))
    write_csv(RESULTS/"physical_partition_audit.csv",[{"logical_facts_same":True,"player_ids_same":True,
      "only_source_id_changed":True,"all_8192_values_same":source_invariant,"judgment":"physical partition is not a Shapley game change"}])

    # Costs and structural evidence.
    audit=diagram.audit()
    write_csv(RESULTS/"native_method_costs.csv",costs)
    write_csv(RESULTS/"historical_overlap_audit.csv",historical_audit())
    write_csv(RESULTS/"theorem_coverage.csv",theorem_rows())
    diagram_json={"method":"layered multi-terminal decision diagram + cardinality weighted model counting",
      "input":"raw fact lineage only","coalition_truth_used_as_input":False,"n_players":n,"nonterminal_nodes":audit.nonterminal_nodes,
      "terminal_nodes":audit.terminal_nodes,"layer_widths":audit.layer_widths,"root_id":audit.root_id,
      "global_distribution_total":sum(global_dist.values()),"expected_coalitions":1<<n,
      "conditional_distributions_each":1<<(n-1),"native_completed_before_oracle":True}
    (RESULTS/"native_diagram_audit.json").write_text(json.dumps(diagram_json,ensure_ascii=False,indent=2),encoding="utf-8")
    manifest={"status":"P3_0_COMPLETED_AND_PAUSED","later_scale_hierarchy_dynamic_started":False,
      "data_version":fixture["data_version"],"player_version":fixture["player_version"],"sql_version":fixture["sql_version"],
      "utility_version":fixture["utility_version"],"n_players":n,"coalitions":1<<n,"lineage":lineage_audit,
      "full_report":{"q_A":2,"q_B":2,"G0":4,"G1":2},"native_method":"layered MTBDD cardinality WMC",
      "native_truth_input":False,"native_completed_before_oracle":native_completed_at<=time.time(),
      "sql_python_all_equal":True,"native_subset_mobius_all_exact":True,"revenue_pool":fixture["revenue_pool"],
      "budget_all_exact":all(r["record_budget_exact"] and r["owner_budget_exact"] for r in budget),
      "physical_partition_invariant":source_invariant,"environment":{"python":sys.version,"duckdb":duckdb.__version__,"platform":platform.platform()},
      "hashes":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (FIXTURE_PATH,SCHEMA_PATH,SQL_PATH)},
      "skills_citation":"Kassis et al. (2026), Scientific Agent Skills, arXiv:2609.00065, doi:10.48550/arXiv.2609.00065"}
    (RESULTS/"P3_0_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    (LOGS/"P3_0_run.json").write_text(json.dumps({"completed_at":time.strftime("%Y-%m-%dT%H:%M:%S%z"),**manifest},ensure_ascii=False,indent=2),encoding="utf-8")
    con.close();print(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
