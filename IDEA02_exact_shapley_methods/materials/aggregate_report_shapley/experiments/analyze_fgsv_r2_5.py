from __future__ import annotations
import csv, json, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"outputs/v4_0/R2_5"

def write(name,rows):
    with (OUT/name).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def main():
    # Normalize the explicit scope label; the numerical results are unchanged.
    for filename in ("conditional_means_by_s_s1.csv","eq9_error_by_s.csv","formula_error_totals.csv"):
        scoped=pd.read_csv(OUT/filename)
        scoped["comparison_scope"]=np.where(scoped.owner_map.eq("SOU-original-mod4"),"original_mod4_separate","common_three_owner")
        scoped.to_csv(OUT/filename,index=False,encoding="utf-8-sig")
    raw=pd.read_csv(OUT/"raw_runs.csv"); marg=pd.read_csv(OUT/"marginal_contributions.csv")
    keys=["method","game","environment","comparison_scope","owner_map","budget"]
    timing=[]
    for key,g in raw.groupby(keys,sort=True):
        x=g.all_owner_runtime_seconds.to_numpy(float); q1,q3=np.quantile(x,[.25,.75]); iqr=q3-q1; cutoff=q3+3*iqr
        timing.append({**dict(zip(keys,key)),"repetitions":len(x),"runtime_median_seconds":np.median(x),"runtime_q1_seconds":q1,"runtime_q3_seconds":q3,"runtime_iqr_seconds":iqr,"runtime_mean_seconds":x.mean(),"runtime_max_seconds":x.max(),"extreme_high_cutoff_q3_plus_3iqr":cutoff,"extreme_high_count":int((x>cutoff).sum()),"utility_compute_median_seconds":g.utility_compute_seconds.median(),"solver_overhead_median_seconds":g.solver_overhead_seconds.median()})
    write("runtime_robust_summary.csv",timing)

    variance=[]
    for (game,player),g in marg.groupby(["game","player"],sort=True):
        sizes=g.coalition_size.to_numpy(int); values=g.marginal.to_numpy(float)
        weights=np.asarray([1/(12*math.comb(11,int(s))) for s in sizes])
        mean=float(np.sum(weights*values)); var=float(np.sum(weights*(values-mean)**2)); span=float(g.normalized_marginal.iloc[0]/g.marginal.iloc[0]) if g.marginal.iloc[0]!=0 else np.nan
        # Robustly recover the normalization from any nonzero row.
        nz=g[np.abs(g.marginal)>1e-15].iloc[0]; utility_span=float(nz.marginal/nz.normalized_marginal)
        variance.append({"game":game,"player":player,"permutation_weighted_mean":mean,"permutation_marginal_variance":var,"permutation_marginal_sd":math.sqrt(var),"utility_span":utility_span,"normalized_permutation_marginal_sd":math.sqrt(var)/utility_span})
    write("permutation_marginal_variance.csv",variance)

    summary=[]
    for game,g in pd.DataFrame(variance).groupby("game",sort=True):
        summary.append({"game":game,"players":len(g),"mean_player_permutation_marginal_sd":g.permutation_marginal_sd.mean(),"max_player_permutation_marginal_sd":g.permutation_marginal_sd.max(),"mean_normalized_permutation_marginal_sd":g.normalized_permutation_marginal_sd.mean(),"max_normalized_permutation_marginal_sd":g.normalized_permutation_marginal_sd.max()})
    write("permutation_variance_summary.csv",summary)

    properties=pd.read_csv(OUT/"game_property_summary.csv")
    pvar=pd.DataFrame(summary)
    formula=pd.read_csv(OUT/"formula_error_totals.csv")
    formula=formula[formula.comparison_scope=="common_three_owner"].groupby("game",as_index=False).agg(mean_normalized_hybrid_abs_error=("normalized_hybrid_abs_error","mean"),max_normalized_hybrid_abs_error=("normalized_hybrid_abs_error","max"))
    combined=properties.merge(pvar,on="game").merge(formula,on="game")
    combined["normalized_uniform_edge_marginal_sd"]=combined.marginal_sd/combined.utility_span
    combined["normalized_interaction_sd"]=combined.interaction_sd/combined.utility_span
    combined.to_csv(OUT/"game_property_comparison.csv",index=False,encoding="utf-8-sig")

    common=raw[raw.comparison_scope=="common_three_owner"]
    pivot=common.pivot_table(index=["game","owner_map","budget","seed"],columns="method",values="normalized_total_l1").reset_index()
    pivot["FGSV_over_MC_normalized_L1"]=pivot["FGSV_PAPER_INTERNAL"]/pivot["COMPLETE_PERMUTATION_MC"]
    comparisons=[]
    for key,g in pivot.groupby(["game","owner_map","budget"],sort=True):
        comparisons.append({**dict(zip(["game","owner_map","budget"],key)),"paired_seeds":len(g),"FGSV_normalized_L1_mean":g.FGSV_PAPER_INTERNAL.mean(),"MC_normalized_L1_mean":g.COMPLETE_PERMUTATION_MC.mean(),"ratio_of_means":g.FGSV_PAPER_INTERNAL.mean()/g.COMPLETE_PERMUTATION_MC.mean(),"paired_ratio_median":g.FGSV_over_MC_normalized_L1.median(),"FGSV_lower_error_fraction":float((g.FGSV_PAPER_INTERNAL<g.COMPLETE_PERMUTATION_MC).mean())})
    write("controlled_method_comparison.csv",comparisons)

    manifest={"normalization":"absolute errors and total L1 divided by abs(U(N)-U(empty))","runtime_policy":"Raw timings retained. Primary timing summary uses median and IQR; values above Q3+3*IQR are flagged, not deleted.","permutation_variance":"Exact variance over the permutation-induced distribution: size is uniform on 0..n-1 and subsets are uniform conditional on size.","sampling_unit_warning":"Thirty seeds repeat algorithm randomness on one fixed game instance; they are not independent data environments."}
    (OUT/"analysis_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__": main()
