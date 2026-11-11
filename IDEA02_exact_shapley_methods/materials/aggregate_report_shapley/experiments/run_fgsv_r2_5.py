from __future__ import annotations

import csv, hashlib, json, math, platform, sys, time
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy.stats import t

ROOT=Path(__file__).resolve().parents[1]
OFFICIAL=ROOT/"external/fgsv/source/Faithful_GSV-main/exp1_benchmark"
sys.path[:0]=[str(ROOT/"src"),str(ROOT),str(OFFICIAL)]

from aggregate_report_shapley.d1p import all_incremental_states, load_d1p_spec, state_for_mask
from aggregate_report_shapley.d1p_values import D1PValueSuite
from aggregate_report_shapley.fgsv_paper_formula import paper_formula_fgsv_budget_capped
from experiments.run_fgsv_r2_d1p import evaluate_state_float, even_group_budgets, mask_from_selection
from utils import U_sou, generate_sou_game, sv_sou_true

OUT=ROOT/"outputs/v4_0/R2_5"; OUT.mkdir(parents=True,exist_ok=True)
CONFIG=json.loads((ROOT/"config/fgsv_r2_5_control.json").read_text(encoding="utf-8"))
N=12; BUDGETS=tuple(CONFIG["effective_total_budgets"]); SEEDS=tuple(CONFIG["algorithm_seeds"]); THRESHOLD=10
FGSV="FGSV_PAPER_INTERNAL"; MC="COMPLETE_PERMUTATION_MC"

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def write_csv(path,rows):
    if not rows: raise ValueError(path)
    with Path(path).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def exact_shapley_float(values,n):
    out=np.zeros(n)
    for i in range(n):
        bit=1<<i
        for mask in range(1<<n):
            if mask&bit: continue
            s=mask.bit_count(); out[i]+=(values[mask|bit]-values[mask])/(n*math.comb(n-1,s))
    return out

@dataclass
class TrackingUtility:
    n:int; evaluator:object; calls:int=0; compute_seconds:float=0.0
    def __post_init__(self): self.mask_counts=Counter(); self.size_counts=Counter()
    def __call__(self,selection,*_ignored):
        mask,size=mask_from_selection(selection,self.n); tick=time.perf_counter(); value=self.evaluator(mask)
        self.compute_seconds+=time.perf_counter()-tick; self.calls+=1; self.mask_counts[mask]+=1; self.size_counts[size]+=1
        return float(value)

def maps_from_config():
    common={m:{o:list(xs) for o,xs in owners.items()} for m,owners in CONFIG["common_owner_maps"].items()}
    mod4={"SOU-original-mod4":{o:list(xs) for o,xs in CONFIG["sou_original_mod4_separate"].items()}}
    return common,mod4

def property_rows(games):
    marginal_rows=[]; interaction_rows=[]; summary=[]
    for name,g in games.items():
        v=g["values"]; marg=[]; inter=[]
        for i in range(N):
            bit=1<<i
            for mask in range(1<<N):
                if mask&bit: continue
                x=v[mask|bit]-v[mask]; marg.append(x)
                marginal_rows.append({"game":name,"player":i,"coalition_mask":mask,"coalition_size":mask.bit_count(),"marginal":x,"normalized_marginal":x/g["span"]})
        for i in range(N):
            for j in range(i+1,N):
                bits=(1<<i)|(1<<j)
                for mask in range(1<<N):
                    if mask&bits: continue
                    x=v[mask|bits]-v[mask|(1<<i)]-v[mask|(1<<j)]+v[mask]; inter.append(x)
                    interaction_rows.append({"game":name,"player_i":i,"player_j":j,"coalition_mask":mask,"coalition_size":mask.bit_count(),"interaction":x,"normalized_interaction":x/g["span"]})
        m=np.asarray(marg); z=np.asarray(inter); truth=np.asarray(g["truth"])
        summary.append({"game":name,"environment":g["environment"],"players":N,"coalitions":1<<N,"utility_empty":v[0],"utility_full":v[-1],"utility_span":g["span"],
          "truth_min":truth.min(),"truth_max":truth.max(),"truth_sd":truth.std(ddof=0),"marginal_count":len(m),"marginal_mean":m.mean(),"marginal_sd":m.std(ddof=0),"marginal_min":m.min(),"marginal_q05":np.quantile(m,.05),"marginal_median":np.median(m),"marginal_q95":np.quantile(m,.95),"marginal_max":m.max(),"marginal_negative_fraction":np.mean(m<-1e-12),"marginal_zero_fraction":np.mean(np.abs(m)<=1e-12),
          "interaction_count":len(z),"interaction_mean":z.mean(),"interaction_sd":z.std(ddof=0),"interaction_min":z.min(),"interaction_q05":np.quantile(z,.05),"interaction_median":np.median(z),"interaction_q95":np.quantile(z,.95),"interaction_max":z.max(),"interaction_negative_fraction":np.mean(z<-1e-12),"interaction_zero_fraction":np.mean(np.abs(z)<=1e-12),"interaction_positive_fraction":np.mean(z>1e-12)})
    return marginal_rows,interaction_rows,summary

def formula_rows(games, map_sets):
    conditional=[]; per_s=[]; totals=[]
    for game_name,g in games.items():
      for map_name,mapping in map_sets[game_name].items():
       comparison_scope="original_mod4_separate" if map_name=="SOU-original-mod4" else "common_three_owner"
       for owner,group in mapping.items():
        s0=len(group); linear=s0/N*(g["values"][-1]-g["values"][0]); sum8=linear; sum9=linear; hybrid=linear
        for s in range(1,N):
            strata=defaultdict(list)
            for mask,value in enumerate(g["values"]):
                if mask.bit_count()==s: strata[sum((mask>>i)&1 for i in group)].append(value)
            means={s1:float(np.mean(vals)) for s1,vals in strata.items()}; t8=0.0
            for s1,mean in sorted(means.items()):
                p=math.comb(s0,s1)*math.comb(N-s0,s-s1)/math.comb(N,s)
                coeff=p*N/(s*(N-s))*(s1-s*s0/N); contribution=coeff*mean; t8+=contribution
                conditional.append({"game":game_name,"comparison_scope":comparison_scope,"owner_map":map_name,"owner":owner,"owner_size":s0,"s":s,"s1":s1,"coalition_count":len(strata[s1]),"hypergeom_weight":p,"conditional_mean":mean,"conditional_mean_normalized":mean/g["span"],"eq8_contribution":contribution})
            k=math.floor(s*s0/N); delta=means[k+1]-means[k]; alpha=s0/N; t9=N/(N-1)*alpha*(1-alpha)*delta
            sum8+=t8; sum9+=t9; hybrid+=t8 if s<THRESHOLD else t9
            per_s.append({"game":game_name,"comparison_scope":comparison_scope,"owner_map":map_name,"owner":owner,"owner_size":s0,"s":s,"k_floor":k,"T8_exact":t8,"T9_approx":t9,"T9_minus_T8":t9-t8,"normalized_abs_error":abs(t9-t8)/g["span"]})
        target=float(sum(g["truth"][i] for i in group)); residual=sum8-target
        if abs(residual)>1e-10: raise AssertionError(f"Eq8 identity {game_name}/{map_name}/{owner}: {residual}")
        totals.append({"game":game_name,"comparison_scope":comparison_scope,"owner_map":map_name,"owner":owner,"owner_size":s0,"truth":target,"utility_span":g["span"],"eq8_total":sum8,"eq8_residual":residual,"eq9_all_s_error":sum9-target,"hybrid_error":hybrid-target,"normalized_hybrid_abs_error":abs(hybrid-target)/g["span"]})
    return conditional,per_s,totals

def permutation_mc(utility,groups,budget,rng):
    if budget%(N+1): raise ValueError(budget)
    reps=budget//(N+1); acc=np.zeros(N)
    for _ in range(reps):
        order=rng.permutation(N); prev=utility(np.array([],dtype=int))
        for pos in range(N):
            cur=utility(order[:pos+1]); acc[order[pos]]+=cur-prev; prev=cur
    individual=acc/reps
    return {"estimates":{o:float(individual[xs].sum()) for o,xs in groups.items()},"individual":individual,"permutations":reps}

def run_fgsv(g,evaluator,groups,budget,seed):
    allocations=even_group_budgets(budget,len(groups)); rng=np.random.RandomState(seed); details={}; estimates={}; utilities=[]; tick_all=time.perf_counter()
    for (owner,indexes),b in zip(groups.items(),allocations):
        u=TrackingUtility(N,evaluator); tick=time.perf_counter(); d=paper_formula_fgsv_budget_capped(u,N,indexes,b,rng,THRESHOLD); wall=time.perf_counter()-tick
        estimates[owner]=d["estimate"]; details[owner]={**d,"calls":u.calls,"unique":len(u.mask_counts),"repeated":u.calls-len(u.mask_counts),"wall":wall,"compute":u.compute_seconds,"counter":u.mask_counts}; utilities.append(u)
    aggregate=Counter()
    for u in utilities: aggregate.update(u.mask_counts)
    return estimates,details,{"wall":time.perf_counter()-tick_all,"compute":sum(u.compute_seconds for u in utilities),"calls":sum(u.calls for u in utilities),"useful":sum(details[o]["useful_calls"] for o in groups),"padding":sum(details[o]["padding_calls"] for o in groups),"unique":len(aggregate),"repeated":sum(u.calls for u in utilities)-len(aggregate),"group_budgets":dict(zip(groups,allocations))}

def run_mc(evaluator,groups,budget,seed):
    u=TrackingUtility(N,evaluator); tick=time.perf_counter(); d=permutation_mc(u,groups,budget,np.random.RandomState(seed)); wall=time.perf_counter()-tick
    stats={"wall":wall,"compute":u.compute_seconds,"calls":u.calls,"useful":u.calls,"padding":0,"unique":len(u.mask_counts),"repeated":u.calls-len(u.mask_counts),"group_budgets":None}
    return d["estimates"],d,stats

def summarize(owner_frame):
    keys=["method","game","environment","comparison_scope","owner_map","budget","owner","owner_size"]
    rows=[]
    for key,g in owner_frame.groupby(keys,sort=True):
        e=g.signed_error.to_numpy(float); ae=np.abs(e); ne=g.normalized_absolute_error.to_numpy(float); n=len(e); crit=float(t.ppf(.975,n-1)); sd=float(e.std(ddof=1)); nsd=float((e/g.utility_span).std(ddof=1)); bias=float(e.mean()); mae=float(ae.mean()); nesd=float(ne.std(ddof=1))
        rows.append({**dict(zip(keys,key)),"repetitions":n,"truth":g.truth.iloc[0],"utility_span":g.utility_span.iloc[0],"estimate_mean":g.estimate.mean(),"bias":bias,"bias_ci95_low":bias-crit*sd/math.sqrt(n),"bias_ci95_high":bias+crit*sd/math.sqrt(n),"random_sd":sd,"mae":mae,"rmse":float(np.sqrt(np.mean(e**2))),"normalized_abs_error_mean":ne.mean(),"normalized_abs_error_ci95_low":max(0,ne.mean()-crit*nesd/math.sqrt(n)),"normalized_abs_error_ci95_high":ne.mean()+crit*nesd/math.sqrt(n),"normalized_bias":float((e/g.utility_span).mean()),"normalized_random_sd":nsd,"single_owner_calls_mean":g.single_owner_calls.mean(),"single_owner_unique_mean":g.single_owner_unique.mean(),"single_owner_runtime_mean":g.single_owner_runtime.mean(),"all_owner_calls_mean":g.all_owner_calls.mean(),"all_owner_unique_mean":g.all_owner_unique.mean(),"all_owner_runtime_mean":g.all_owner_runtime.mean()})
    return rows

def main():
    started=time.perf_counter(); common,mod4=maps_from_config()
    historical=[ROOT/"outputs/v4_0/R2/sou_partial/summary.json",ROOT/"outputs/v4_0/R2_3/exact_targets.json",ROOT/"outputs/v4_0/R2_4/audit.json"]
    before={str(p.relative_to(ROOT)):sha256(p) for p in historical}
    # Official SOU generator, unchanged.
    d=N*N; S_list,alpha=generate_sou_game(N,d,seed=42); selections=[np.asarray([i for i in range(N) if mask>>i&1],dtype=int) for mask in range(1<<N)]
    sou_values=np.asarray([U_sou(sel,S_list,alpha,d) for sel in selections]); sou_analytic=sv_sou_true(N,S_list,alpha); sou_enum=exact_shapley_float(sou_values,N)
    if max(abs(sou_analytic-sou_enum))>1e-12 or abs(sou_analytic.sum()-(sou_values[-1]-sou_values[0]))>1e-12: raise AssertionError("SOU n=12 truth gate failed")
    if len(S_list)!=144 or any(not 1<=len(x)<=11 for x in S_list) or any(not x.issubset(set(range(N))) for x in S_list): raise AssertionError("SOU generator gate failed")
    spec=load_d1p_spec(ROOT/"config/d1p_design.yaml"); states=all_incremental_states(spec); suite=D1PValueSuite(spec,states[-1],ROOT/"config/value_spec_v3_2.yaml"); all_values=suite.all_values(states)
    exact_payload=json.loads((ROOT/"outputs/v4_0/R2_3/exact_targets.json").read_text(encoding="utf-8"))
    games={
      "SOU_n12_seed42":{"environment":"SOU","scope":"common_three_owner","values":sou_values,"truth":sou_analytic,"span":float(sou_values[-1]-sou_values[0]),"evaluator":lambda mask:U_sou(selections[mask],S_list,alpha,d)},
      "D1P_V1":{"environment":"D1-P","scope":"common_three_owner","values":np.asarray([float(x) for x in all_values["V1"]]),"truth":np.asarray([float(Fraction(x)) if "/" in x else float(x) for x in exact_payload["record_shapley"]["V1"]]),"span":1000.0,"evaluator":lambda mask:evaluate_state_float(suite,state_for_mask(mask,spec),"V1")},
      "D1P_V2":{"environment":"D1-P","scope":"common_three_owner","values":np.asarray([float(x) for x in all_values["V2_lambda_0_5"]]),"truth":np.asarray([float(x) for x in exact_payload["record_shapley"]["V2_lambda_0_5"]]),"span":1000.0,"evaluator":lambda mask:evaluate_state_float(suite,state_for_mask(mask,spec),"V2_lambda_0_5")}}
    # Verify online evaluators against frozen/exhaustive tables before any random run.
    for name,g in games.items():
        err=max(abs(g["evaluator"](mask)-g["values"][mask]) for mask in range(1<<N))
        if err>1e-10: raise AssertionError(f"online/table mismatch {name}: {err}")
        g["online_table_max_error"]=err
    map_sets={name:{**common} for name in games}; map_sets["SOU_n12_seed42"]={**common,**mod4}
    marg,inter,prop=property_rows(games); write_csv(OUT/"marginal_contributions.csv",marg); write_csv(OUT/"second_order_interactions.csv",inter); write_csv(OUT/"game_property_summary.csv",prop)
    cond,per_s,formula_totals=formula_rows(games,map_sets); write_csv(OUT/"conditional_means_by_s_s1.csv",cond); write_csv(OUT/"eq9_error_by_s.csv",per_s); write_csv(OUT/"formula_error_totals.csv",formula_totals)
    truth_payload={"sou_generator_validation":{"supports_n12":True,"generator_modified":False,"d":d,"seed":42,"unanimity_terms":len(S_list),"alpha_min":float(alpha.min()),"alpha_max":float(alpha.max()),"analytic_vs_enumeration_max_abs":float(max(abs(sou_analytic-sou_enum))),"efficiency_gap":float(sou_analytic.sum()-(sou_values[-1]-sou_values[0]))},"games":{name:{"span":g["span"],"record_truth":g["truth"].tolist(),"online_table_max_error":g["online_table_max_error"]} for name,g in games.items()}}
    (OUT/"exact_truths.json").write_text(json.dumps(truth_payload,ensure_ascii=False,indent=2),encoding="utf-8")
    matrix=[]
    for game_name,g in games.items():
      for map_name,groups in map_sets[game_name].items():
       scope="original_mod4_separate" if map_name=="SOU-original-mod4" else "common_three_owner"
       for method in (FGSV,MC):
        for budget in BUDGETS: matrix.append({"game":game_name,"environment":g["environment"],"comparison_scope":scope,"owner_map":map_name,"owner_sizes":"/".join(str(len(x)) for x in groups.values()),"method":method,"effective_total_budget":budget,"algorithm_seed_count":30,"player_count":N,"threshold":THRESHOLD})
    write_csv(OUT/"experiment_matrix.csv",matrix)
    run_rows=[]; owner_rows=[]
    game_order=list(games)
    for gi,game_name in enumerate(game_order):
      g=games[game_name]
      for mi,(map_name,groups) in enumerate(map_sets[game_name].items()):
       scope="original_mod4_separate" if map_name=="SOU-original-mod4" else "common_three_owner"; truths={o:float(sum(g["truth"][i] for i in xs)) for o,xs in groups.items()}
       for budget in BUDGETS:
        for seed in SEEDS:
         base_seed=1_000_000*gi+10_000*mi+seed
         for method in (FGSV,MC):
          if method==FGSV: estimates,details,stats=run_fgsv(g,g["evaluator"],groups,budget,base_seed)
          else: estimates,details,stats=run_mc(g["evaluator"],groups,budget,base_seed)
          errors={o:estimates[o]-truths[o] for o in groups}; l1=sum(abs(x) for x in errors.values())
          run_rows.append({"method":method,"game":game_name,"environment":g["environment"],"comparison_scope":scope,"owner_map":map_name,"budget":budget,"seed":seed,"utility_span":g["span"],"total_l1_error":l1,"normalized_total_l1":l1/g["span"],"estimate_sum":sum(estimates.values()),"efficiency_gap":sum(estimates.values())-g["span"],"actual_total_calls":stats["calls"],"useful_calls":stats["useful"],"padding_calls":stats["padding"],"unique_coalitions":stats["unique"],"repeated_visits":stats["repeated"],"unique_fraction":stats["unique"]/stats["calls"],"all_owner_runtime_seconds":stats["wall"],"utility_compute_seconds":stats["compute"],"solver_overhead_seconds":stats["wall"]-stats["compute"],"utility_seconds_per_call":stats["compute"]/stats["calls"],"wall_seconds_per_call":stats["wall"]/stats["calls"],"owner_estimates_json":json.dumps(estimates,sort_keys=True),"owner_truth_json":json.dumps(truths,sort_keys=True),"group_budgets_json":json.dumps(stats["group_budgets"],sort_keys=True) if stats["group_budgets"] else ""})
          for owner,xs in groups.items():
            if method==FGSV:
                dd=details[owner]; single_calls=dd["calls"]; single_unique=dd["unique"]; single_wall=dd["wall"]; single_compute=dd["compute"]; useful=dd["useful_calls"]; padding=dd["padding_calls"]; semantics="dedicated owner FGSV run"
            else:
                single_calls=stats["calls"]; single_unique=stats["unique"]; single_wall=stats["wall"]; single_compute=stats["compute"]; useful=stats["useful"]; padding=0; semantics="one complete-permutation path estimates all owners; selecting one owner does not reduce observed cost"
            e=errors[owner]
            owner_rows.append({"method":method,"game":game_name,"environment":g["environment"],"comparison_scope":scope,"owner_map":map_name,"budget":budget,"seed":seed,"owner":owner,"owner_size":len(xs),"truth":truths[owner],"utility_span":g["span"],"estimate":estimates[owner],"signed_error":e,"absolute_error":abs(e),"normalized_absolute_error":abs(e)/g["span"],"relative_to_owner_truth":abs(e)/abs(truths[owner]) if truths[owner] else "","single_owner_calls":single_calls,"single_owner_useful_calls":useful,"single_owner_padding_calls":padding,"single_owner_unique":single_unique,"single_owner_repeated":single_calls-single_unique,"single_owner_runtime":single_wall,"single_owner_utility_compute":single_compute,"single_owner_solver_overhead":single_wall-single_compute,"all_owner_calls":stats["calls"],"all_owner_unique":stats["unique"],"all_owner_runtime":stats["wall"],"cost_semantics":semantics})
        print(f"completed {game_name} {map_name} budget={budget}",flush=True)
    write_csv(OUT/"raw_runs.csv",run_rows); write_csv(OUT/"raw_owner_errors.csv",owner_rows)
    owner_frame=pd.DataFrame(owner_rows); run_frame=pd.DataFrame(run_rows); write_csv(OUT/"owner_error_summary.csv",summarize(owner_frame))
    run_summary=[]
    keys=["method","game","environment","comparison_scope","owner_map","budget"]
    for key,df in run_frame.groupby(keys,sort=True):
        x=df.normalized_total_l1.to_numpy(float); crit=float(t.ppf(.975,len(x)-1)); mean=float(x.mean()); half=crit*float(x.std(ddof=1))/math.sqrt(len(x))
        run_summary.append({**dict(zip(keys,key)),"repetitions":len(x),"raw_total_l1_mean":df.total_l1_error.mean(),"normalized_total_l1_mean":mean,"normalized_total_l1_ci95_low":max(0,mean-half),"normalized_total_l1_ci95_high":mean+half,"normalized_total_l1_sd":x.std(ddof=1),"actual_total_calls_mean":df.actual_total_calls.mean(),"useful_calls_mean":df.useful_calls.mean(),"unique_coalitions_mean":df.unique_coalitions.mean(),"repeated_visits_mean":df.repeated_visits.mean(),"unique_fraction_mean":df.unique_fraction.mean(),"all_owner_runtime_mean_seconds":df.all_owner_runtime_seconds.mean(),"utility_compute_mean_seconds":df.utility_compute_seconds.mean(),"solver_overhead_mean_seconds":df.solver_overhead_seconds.mean()})
    write_csv(OUT/"run_summary.csv",run_summary)
    after={str(p.relative_to(ROOT)):sha256(p) for p in historical}
    if before!=after: raise AssertionError("historical output changed")
    expected=1680
    if len(run_rows)!=expected or len(owner_rows)!=5280: raise AssertionError((len(run_rows),len(owner_rows)))
    if any(r["actual_total_calls"]!=r["budget"] for r in run_rows): raise AssertionError("budget mismatch")
    audit={"status":"COMPLETED_R2_5_ONLY","scope_warning":CONFIG["scope_warning"],"sou_generator_modified":False,"official_utils_sha256":sha256(OFFICIAL/"utils.py"),"paper_formula_sha256":sha256(ROOT/"src/aggregate_report_shapley/fgsv_paper_formula.py"),"permutation_source_sha256":sha256(ROOT/"experiments/run_fgsv_r2_d1p.py"),"config_sha256":sha256(ROOT/"config/fgsv_r2_5_control.json"),"historical_before":before,"historical_after":after,"rows":{"matrix":len(matrix),"runs":len(run_rows),"owners":len(owner_rows),"marginals":len(marg),"interactions":len(inter),"conditional":len(cond),"formula_s":len(per_s)},"elapsed_seconds":time.perf_counter()-started,"environment":{"python":sys.version,"platform":platform.platform(),"numpy":np.__version__,"pandas":pd.__version__,"scipy":scipy.__version__}}
    (OUT/"audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__": main()
