from __future__ import annotations

import csv, hashlib, json, math, platform, sys, time
from collections import defaultdict
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import yaml
from scipy.stats import t

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from aggregate_report_shapley.d1p import all_incremental_states, load_d1p_spec
from aggregate_report_shapley.d1p_values import D1PValueSuite
from aggregate_report_shapley.fgsv_ablation import STAGES, fgsv_sequential_ablation
from aggregate_report_shapley.fgsv_paper_formula import paper_formula_fgsv_budget_capped
from experiments.run_fgsv_r2_d1p import CountingUtility, common_effective_budget, even_group_budgets

OUT = ROOT / "outputs" / "v4_0" / "R2_4"
OUT.mkdir(parents=True, exist_ok=True)
VALUE_NAMES = ("V_count", "V1", "V2_lambda_0_5")
NOMINAL_BUDGETS = (500, 1000, 2000, 5000)
SEEDS = tuple(range(30))
THRESHOLD = 10
A4 = "A4_COMPLETE_PAPER_INTERNAL"
METHODS = (*STAGES, A4)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows: raise ValueError(f"empty output: {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def dec(value) -> Decimal:
    if isinstance(value, Fraction):
        return Decimal(value.numerator) / Decimal(value.denominator)
    return Decimal(str(value))


def parse_exact(text: str) -> Decimal:
    return dec(Fraction(text)) if "/" in text else Decimal(text)


def exact_decomposition(all_values, owner_maps, exact_payload, n: int):
    conditional_rows, per_s_rows, total_rows = [], [], []
    with localcontext() as ctx:
        ctx.prec = 100
        record_truth = {v: [parse_exact(x) for x in exact_payload["record_shapley"][v]] for v in VALUE_NAMES}
        for value_name in VALUE_NAMES:
            values = [dec(x) for x in all_values[value_name]]
            for map_name, mapping in owner_maps.items():
                for owner, group in mapping.items():
                    group_set, s0 = set(group), len(group)
                    truth = sum((record_truth[value_name][i] for i in group), Decimal(0))
                    linear = Decimal(s0) / Decimal(n) * (values[-1] - values[0])
                    total8, total9, hybrid = linear, linear, linear
                    for s in range(1, n):
                        strata = defaultdict(list)
                        for mask, value in enumerate(values):
                            if mask.bit_count() == s:
                                s1 = sum((mask >> i) & 1 for i in group_set)
                                strata[s1].append(value)
                        means = {s1: sum(vs, Decimal(0)) / Decimal(len(vs)) for s1, vs in strata.items()}
                        t8 = Decimal(0)
                        for s1, mean in sorted(means.items()):
                            count = math.comb(s0, s1) * math.comb(n - s0, s - s1)
                            p = Decimal(count) / Decimal(math.comb(n, s))
                            coeff = p * Decimal(n) / (Decimal(s) * Decimal(n-s)) * (Decimal(s1) - Decimal(s*s0)/Decimal(n))
                            contribution = coeff * mean
                            t8 += contribution
                            conditional_rows.append({
                                "value": value_name, "owner_map": map_name, "owner": owner,
                                "owner_size": s0, "s": s, "s1": s1,
                                "coalition_count": len(strata[s1]), "hypergeom_weight": str(p),
                                "conditional_mean": str(mean), "eq8_coefficient": str(coeff),
                                "eq8_stratum_contribution": str(contribution),
                            })
                        k = math.floor(s*s0/n)
                        delta = means[k+1] - means[k]
                        alpha = Decimal(s0) / Decimal(n)
                        t9 = Decimal(n) / Decimal(n-1) * alpha * (Decimal(1)-alpha) * delta
                        error = t9 - t8
                        total8 += t8; total9 += t9; hybrid += t8 if s < THRESHOLD else t9
                        per_s_rows.append({
                            "value": value_name, "owner_map": map_name, "owner": owner,
                            "owner_size": s0, "s": s, "k_floor": k,
                            "mu_k": str(means[k]), "mu_k_plus_1": str(means[k+1]),
                            "delta_mu": str(delta), "T8_exact": str(t8), "T9_approx": str(t9),
                            "T9_minus_T8": str(error), "abs_T9_minus_T8": str(abs(error)),
                        })
                    residual = total8 - truth
                    tolerance = Decimal("1e-75") if value_name == "V2_lambda_0_5" else Decimal("1e-90")
                    if abs(residual) > tolerance:
                        raise AssertionError(f"Eq8 identity failed {value_name}/{map_name}/{owner}: {residual}")
                    total_rows.append({
                        "value": value_name, "owner_map": map_name, "owner": owner,
                        "owner_size": s0, "linear_base": str(linear), "exact_group_truth": str(truth),
                        "eq8_total": str(total8), "eq8_identity_residual": str(residual),
                        "eq9_all_s_total": str(total9), "eq9_all_s_error": str(total9-truth),
                        "r2_3_hybrid_total": str(hybrid), "r2_3_hybrid_deterministic_error": str(hybrid-truth),
                    })
    return conditional_rows, per_s_rows, total_rows


def summarize(frame: pd.DataFrame):
    keys = ["method","value","owner_map","nominal_budget","effective_budget","owner","owner_size"]
    rows=[]
    for key,g in frame.groupby(keys, sort=True):
        e=g.signed_error.to_numpy(float); ae=np.abs(e); crit=float(t.ppf(.975,len(e)-1))
        sd=float(e.std(ddof=1)); asd=float(ae.std(ddof=1)); bias=float(e.mean()); mae=float(ae.mean())
        rows.append({**dict(zip(keys,key)),"repetitions":len(e),"truth":float(g.truth.iloc[0]),
            "estimate_mean":float(g.estimate.mean()),"systematic_bias_mean":bias,
            "bias_ci95_low":bias-crit*sd/math.sqrt(len(e)),"bias_ci95_high":bias+crit*sd/math.sqrt(len(e)),
            "random_error_sd":sd,"mae":mae,"mae_ci95_low":max(0,mae-crit*asd/math.sqrt(len(e))),
            "mae_ci95_high":mae+crit*asd/math.sqrt(len(e)),"rmse":float(np.sqrt(np.mean(e**2))),
            "single_owner_calls_mean":float(g.utility_calls.mean()),"single_owner_runtime_mean_seconds":float(g.runtime_seconds.mean())})
    return rows


def paired_steps(frame: pd.DataFrame):
    idx=["value","owner_map","nominal_budget","effective_budget","seed","owner","owner_size"]
    p=frame.pivot(index=idx,columns="method",values="absolute_error").reset_index(); rows=[]
    for prev,curr in zip(METHODS[:-1],METHODS[1:]):
        p["delta"]=p[curr]-p[prev]
        for key,g in p.groupby(idx[:4]+["owner","owner_size"],sort=True):
            x=g.delta.to_numpy(float); crit=float(t.ppf(.975,len(x)-1)); mean=float(x.mean()); half=crit*float(x.std(ddof=1))/math.sqrt(len(x))
            rows.append({**dict(zip(idx[:4]+["owner","owner_size"],key)),"from_method":prev,"to_method":curr,
                "paired_seeds":len(x),"mean_change_in_absolute_error":mean,"ci95_low":mean-half,"ci95_high":mean+half,
                "fraction_improved":float((x<0).mean()),"interpretation":"ordered sequential ablation; not a factorial main effect"})
    return rows


def main():
    started=time.perf_counter()
    historical=[ROOT/"outputs/v4_0/R2/d1p/raw_runs.csv",ROOT/"outputs/v4_0/R2_3/raw_owner_errors.csv",ROOT/"outputs/v4_0/R2_3/exact_targets.json"]
    before={str(p.relative_to(ROOT)):sha256(p) for p in historical}
    spec=load_d1p_spec(ROOT/"config/d1p_design.yaml"); states=all_incremental_states(spec)
    suite=D1PValueSuite(spec,states[-1],ROOT/"config/value_spec_v3_2.yaml"); all_values=suite.all_values(states)
    raw=yaml.safe_load((ROOT/"config/owner_map_fgsv_r2.yaml").read_text(encoding="utf-8")); index={r.record_id:r.player_index for r in spec.records}
    maps={m:{o:[index[x] for x in xs] for o,xs in owners.items()} for m,owners in raw["maps"].items()}
    exact_payload=json.loads((ROOT/"outputs/v4_0/R2_3/exact_targets.json").read_text(encoding="utf-8"))
    cond, per_s, totals=exact_decomposition(all_values,maps,exact_payload,spec.player_count)
    write_csv(OUT/"conditional_means_exact.csv",cond); write_csv(OUT/"per_s_exact_and_approx.csv",per_s); write_csv(OUT/"owner_formula_totals.csv",totals)

    # Analytic smoke gates: additive games expose normalization exactly.
    smoke=[]
    for n,weights,group in [(2,[1.,4.],[0]),(3,[1.,1.,4.],[0,1])]:
        def ev(mask,w=weights): return sum(w[i] for i in range(len(w)) if mask>>i&1)
        for method in METHODS:
            u=CountingUtility(n,ev); rng=np.random.RandomState(20261030)
            if method==A4: d=paper_formula_fgsv_budget_capped(u,n,group,200,rng,10)
            else: d=fgsv_sequential_ablation(u,n,group,200,rng,10,method)
            smoke.append({"n":n,"game":"additive","group":str(group),"method":method,"truth":sum(weights[i] for i in group),"estimate":d["estimate"],"absolute_error":abs(d["estimate"]-sum(weights[i] for i in group)),"calls":u.calls})
    write_csv(OUT/"analytic_smoke_tests.csv",smoke)
    if any(r["absolute_error"]>1e-10 for r in smoke if r["method"] not in (STAGES[0],)):
        raise AssertionError("n=2/n=3 corrected-stage smoke gate failed")

    truth={(v,m,o):float(Decimal(next(r["exact_group_truth"] for r in totals if r["value"]==v and r["owner_map"]==m and r["owner"]==o))) for v in VALUE_NAMES for m in maps for o in maps[m]}
    tables={v:[float(x) for x in all_values[v]] for v in VALUE_NAMES}; rows=[]
    # V-count is deliberately completed first as a gate before V1/V2.
    for vi,v in enumerate(VALUE_NAMES):
      for mi,(m,groups) in enumerate(maps.items()):
       evaluator=lambda mask,tab=tables[v]:tab[mask]
       for nominal in NOMINAL_BUDGETS:
        effective=common_effective_budget(nominal,spec.player_count); budgets=even_group_budgets(effective,len(groups))
        for seed in SEEDS:
         base=1_000_000*vi+10_000*mi+seed
         for method in METHODS:
          rng=np.random.RandomState(base)
          for (owner,group),budget in zip(groups.items(),budgets):
           u=CountingUtility(spec.player_count,evaluator); tick=time.perf_counter()
           if method==A4: detail=paper_formula_fgsv_budget_capped(u,spec.player_count,group,budget,rng,THRESHOLD)
           else: detail=fgsv_sequential_ablation(u,spec.player_count,group,budget,rng,THRESHOLD,method)
           elapsed=time.perf_counter()-tick; estimate=float(detail["estimate"]); target=truth[(v,m,owner)]
           rows.append({"method":method,"value":v,"owner_map":m,"nominal_budget":nominal,"effective_budget":effective,"seed":seed,
             "owner":owner,"owner_size":len(group),"group_budget":budget,"truth":target,"estimate":estimate,"signed_error":estimate-target,
             "absolute_error":abs(estimate-target),"utility_calls":u.calls,"useful_calls":detail["useful_calls"],"padding_calls":detail["padding_calls"],
             "runtime_seconds":elapsed,"utility_compute_seconds":u.compute_seconds,"solver_overhead_seconds":elapsed-u.compute_seconds,
             "utility_seconds_per_call":u.compute_seconds/u.calls,"wall_seconds_per_call":elapsed/u.calls})
        print(f"completed {v} {m} {nominal}",flush=True)
      if v=="V_count" and (not rows or not np.isfinite(pd.DataFrame(rows)[["estimate","signed_error"]].to_numpy()).all()): raise AssertionError("V-count gate failed")
    write_csv(OUT/"ablation_raw_owner.csv",rows); frame=pd.DataFrame(rows)
    write_csv(OUT/"ablation_summary.csv",summarize(frame)); write_csv(OUT/"ablation_paired_steps.csv",paired_steps(frame))

    r23=pd.read_csv(ROOT/"outputs/v4_0/R2_3/owner_error_summary.csv")
    r23=r23[(r23.method=="B_PAPER_FORMULA_CONSISTENT") & (r23.nominal_budget==5000)]
    compare=[]
    for r in totals:
        match=r23[(r23.value==r["value"])&(r23.owner_map==r["owner_map"])&(r23.owner==r["owner"])].iloc[0]
        det=float(Decimal(r["r2_3_hybrid_deterministic_error"])); obs=float(match.systematic_bias_mean_signed_error)
        compare.append({"value":r["value"],"owner_map":r["owner_map"],"owner":r["owner"],"owner_size":r["owner_size"],
          "hybrid_deterministic_approx_error":det,"r2_3_budget5000_observed_mean_bias":obs,"observed_minus_deterministic":obs-det,
          "r2_3_random_sd":float(match.random_error_sd_across_seeds),"bias_ci95_low":float(match.bias_ci95_low),"bias_ci95_high":float(match.bias_ci95_high)})
    write_csv(OUT/"approximation_vs_r2_3_bias.csv",compare)
    after={str(p.relative_to(ROOT)):sha256(p) for p in historical}
    if before!=after: raise AssertionError("historical R2/R2-3 output changed")
    audit={"status":"COMPLETED_R2_4_ONLY","historical_hashes_before":before,"historical_hashes_after":after,
      "official_source_sha256":sha256(ROOT/"external/fgsv/source/Faithful_GSV-main/exp1_benchmark/estimators.py"),
      "formula_identity_max_abs_residual":str(max(abs(Decimal(r["eq8_identity_residual"])) for r in totals)),
      "rows":{"conditional":len(cond),"per_s":len(per_s),"totals":len(totals),"ablation":len(rows)},
      "methods":list(METHODS),"seeds":list(SEEDS),"budgets":list(NOMINAL_BUDGETS),"threshold":THRESHOLD,
      "sequential_ablation_warning":"A1-A4 are ordered changes, not factorial main effects.",
      "elapsed_seconds":time.perf_counter()-started,"environment":{"python":sys.version,"platform":platform.platform(),"numpy":np.__version__,"pandas":pd.__version__,"scipy":scipy.__version__}}
    (OUT/"audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__": main()
