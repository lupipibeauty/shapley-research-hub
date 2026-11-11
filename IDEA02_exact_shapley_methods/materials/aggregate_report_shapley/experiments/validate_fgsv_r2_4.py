"""Read-only independent validation of completed R2-4 artifacts."""
from __future__ import annotations
import json, math
from decimal import Decimal, localcontext
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"outputs/v4_0/R2_4"

def main():
    s=pd.read_csv(OUT/"per_s_exact_and_approx.csv",dtype=str)
    totals=pd.read_csv(OUT/"owner_formula_totals.csv",dtype=str)
    raw=pd.read_csv(OUT/"ablation_raw_owner.csv")
    assert len(s)==18*11 and len(totals)==18 and len(raw)==10800
    with localcontext() as ctx:
        ctx.prec=80
        worst=Decimal(0)
        for _,r in s.iterrows():
            n=Decimal(12); a=Decimal(r.owner_size)/n
            reconstructed=n/Decimal(11)*a*(1-a)*Decimal(r.delta_mu)
            worst=max(worst,abs(reconstructed-Decimal(r.T9_approx)))
        identity=max(abs(Decimal(x)) for x in totals.eq8_identity_residual)
    assert worst < Decimal("1e-70") and identity < Decimal("1e-70")
    assert raw[["truth","estimate","signed_error","absolute_error"]].map(math.isfinite).all().all()
    assert (raw.utility_calls==raw.group_budget).all()
    assert raw.groupby(["method","value","owner_map","nominal_budget","owner"]).size().eq(30).all()
    audit=json.loads((OUT/"audit.json").read_text(encoding="utf-8"))
    assert audit["historical_hashes_before"]==audit["historical_hashes_after"]
    result={"status":"PASS","per_s_rows":len(s),"owner_totals":len(totals),"ablation_rows":len(raw),"max_eq9_reconstruction_residual":str(worst),"max_eq8_identity_residual":str(identity),"budget_accounting":"PASS","historical_immutability":"PASS"}
    (OUT/"validation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
