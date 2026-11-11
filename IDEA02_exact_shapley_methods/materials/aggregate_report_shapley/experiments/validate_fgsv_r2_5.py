"""Read-only validation of R2-5 results and scope invariants."""
from __future__ import annotations
import json, math
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"outputs/v4_0/R2_5"

def main():
    matrix=pd.read_csv(OUT/"experiment_matrix.csv"); runs=pd.read_csv(OUT/"raw_runs.csv"); owners=pd.read_csv(OUT/"raw_owner_errors.csv"); formula=pd.read_csv(OUT/"formula_error_totals.csv"); truth=json.loads((OUT/"exact_truths.json").read_text(encoding="utf-8")); audit=json.loads((OUT/"audit.json").read_text(encoding="utf-8"))
    assert len(matrix)==56 and len(runs)==1680 and len(owners)==5280
    assert set(runs.method)=={"FGSV_PAPER_INTERNAL","COMPLETE_PERMUTATION_MC"}
    assert set(runs.budget)=={494,988,1976,4992} and runs.groupby(["method","game","owner_map","budget"]).size().eq(30).all()
    assert (runs.actual_total_calls==runs.budget).all() and (runs.unique_coalitions<=runs.actual_total_calls).all() and (runs.repeated_visits==runs.actual_total_calls-runs.unique_coalitions).all()
    assert owners.groupby(["method","game","owner_map","budget","owner"]).size().eq(30).all()
    assert owners.groupby(["game","owner_map","owner"]).truth.nunique().eq(1).all()
    assert owners[["truth","estimate","signed_error","absolute_error","normalized_absolute_error"]].map(math.isfinite).all().all()
    assert (owners.normalized_absolute_error-(owners.absolute_error/owners.utility_span)).abs().max()<1e-14
    assert formula.eq8_residual.abs().max()<1e-10
    sou=truth["sou_generator_validation"]; assert sou["supports_n12"] and not sou["generator_modified"] and sou["analytic_vs_enumeration_max_abs"]<1e-12 and abs(sou["efficiency_gap"])<1e-12
    assert audit["historical_before"]==audit["historical_after"] and not audit["sou_generator_modified"]
    # Both methods must target identical owner truths in every controlled cell.
    target_counts=owners.groupby(["game","owner_map","budget","seed","owner"]).truth.nunique()
    assert target_counts.eq(1).all()
    result={"status":"PASS","matrix_rows":len(matrix),"run_rows":len(runs),"owner_rows":len(owners),"sou_n12_generator":"PASS_UNMODIFIED","sou_truth_analytic_vs_enumeration_max_abs":sou["analytic_vs_enumeration_max_abs"],"same_target_check":"PASS","budget_and_unique_coalition_accounting":"PASS","eq8_identity_max_abs":formula.eq8_residual.abs().max(),"historical_immutability":"PASS","scope":"R2-5 only; no 64-player D1-P run"}
    (OUT/"validation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
