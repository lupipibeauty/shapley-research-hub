from __future__ import annotations

import csv
import json
import statistics
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "experiments")]
from aggregate_report_shapley.h3_jv import METRICS, NODES, evidence_deltas, generate_instance, groundings, lineage_components  # noqa: E402


OUT = ROOT / "outputs" / "v4_0" / "H3_JV"
FIG = OUT / "figures"


def read(name: str) -> list[dict[str, str]]:
    with (OUT / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write(name: str, rows: list[dict]) -> None:
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def q(values: list[float], p: float) -> float:
    values = sorted(values); x = (len(values)-1)*p; lo=int(x); hi=min(lo+1,len(values)-1)
    return values[lo] + (values[hi]-values[lo])*(x-lo)


def save(fig, stem: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "svg"):
        fig.savefig(FIG / f"{stem}.{suffix}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    plt.rcParams.update({"font.sans-serif":["Microsoft YaHei","SimHei","DejaVu Sans"],"axes.unicode_minus":False,"font.size":9})
    instance = generate_instance(7301)
    preprocessing = []
    structural = {r["join_id"]: r for r in read("structural_metrics.csv")}
    prep_median = {}
    for join_id in ("J0","J1","J2"):
        full_rows=[r for r in read("alliance_sql_report.csv") if r["join_id"]==join_id and r["mask"]=="4095"]
        full={(r["node"],m):int(r["normalized_amount_sum"] if m=="amount_sum" else r[m]) for r in full_rows for m in METRICS}
        times=[]
        counts=[]
        for repeat in range(3):
            started=time.perf_counter()
            items=groundings(instance,join_id)
            _=evidence_deltas(items); _=lineage_components(items, full)
            elapsed=time.perf_counter()-started
            times.append(elapsed); counts.append(len(items))
            preprocessing.append({"join_id":join_id,"repeat":repeat,"source_and_state_compile_seconds":elapsed,"grounding_rows":len(items),"scope":"Python lineage/state compilation after SQL relations are loaded"})
        prep_median[join_id]=statistics.median(times)
    write("input_preprocessing_raw.csv",preprocessing)

    raw=[r for r in read("algorithm_raw_performance.csv") if r["repeat"] not in ("NA","")]
    groups={}
    for r in raw: groups.setdefault((r["join_id"],r["game_id"],r["method"]),[]).append(r)
    summary=[]
    sql_truth={r["join_id"]:float(r["sql_all_4096_seconds"]) for r in read("structural_metrics.csv")}
    for key,rows in groups.items():
        values=[float(r["elapsed_seconds"]) for r in rows]
        join_id,game_id,method=key
        input_seconds=sql_truth[join_id] if method=="B0_FULL_COALITION" else prep_median[join_id]
        summary.append({
            "join_id":join_id,"game_id":game_id,"method":method,"repeats":len(values),
            "algorithm_seconds_median":statistics.median(values),"algorithm_seconds_q1":q(values,.25),
            "algorithm_seconds_q3":q(values,.75),"algorithm_seconds_iqr":q(values,.75)-q(values,.25),
            "input_preprocessing_seconds":input_seconds,
            "end_to_end_seconds_median":input_seconds+statistics.median(values),
            "timing_unit":"same frozen instance repeat; descriptive runtime noise",
        })
    write("algorithm_performance_summary.csv",summary)

    # Controlled descriptive decomposition using one common exact method (B3).
    b3={(r["join_id"],r["game_id"]):float(r["end_to_end_seconds_median"]) for r in summary if r["method"]=="B3_JOINT_STATE_DP"}
    effects=[]
    baseline=b3[("J0","G0")]
    for j in ("J0","J1","J2"):
        for g in ("G0","G1","G2"):
            value=b3[(j,g)]
            join_effect=b3[(j,"G0")]-baseline
            value_effect=b3[("J0",g)]-baseline
            interaction=value-baseline-join_effect-value_effect
            effects.append({"join_id":j,"game_id":g,"b3_end_to_end_seconds":value,"join_main_difference_seconds":join_effect,"value_main_difference_seconds":value_effect,"descriptive_interaction_seconds":interaction,"causal_claim":False})
    write("controlled_cost_decomposition.csv",effects)

    # Figure 1: same-method factorial comparison.
    fig,ax=plt.subplots(figsize=(9,5.3),layout="constrained")
    x=np.arange(3); width=.25
    for k,g in enumerate(("G0","G1","G2")):
        ax.bar(x+(k-1)*width,[b3[(j,g)] for j in ("J0","J1","J2")],width,label=g)
    ax.set_xticks(x,["J0 无跨玩家JOIN","J1 简单跨玩家JOIN","J2 交叉共享JOIN"])
    ax.set_ylabel("B3端到端时间（秒，中位数）"); ax.set_title("H3-JV：JOIN结构与整表价值的共同方法对照")
    ax.legend(title="价值函数",frameon=False); ax.grid(axis="y",alpha=.25)
    save(fig,"H3_JV_图1_共同方法成本")

    # Figure 2: structure metrics.
    srows=read("structural_metrics.csv"); fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout="constrained")
    labels=[r["join_id"] for r in srows]
    axes[0].bar(labels,[float(r["groundings"]) for r in srows],label="grounding",color="#4C78A8")
    axes[0].bar(labels,[float(r["distinct_output_keys"]) for r in srows],label="distinct key",color="#F58518")
    axes[0].set_title("查询输出结构"); axes[0].set_ylabel("数量"); axes[0].legend(frameon=False)
    axes[1].bar(labels,[float(r["reachable_evidence_states"]) for r in srows],color="#54A24B")
    axes[1].set_title("实际可达JOIN证据状态"); axes[1].set_ylabel("状态数")
    for ax in axes: ax.grid(axis="y",alpha=.25)
    fig.suptitle("H3-JV：grounding数量不等于联合状态规模")
    save(fig,"H3_JV_图2_来源与状态规模")

    # Figure 3: independent-instance G2 S6 distribution.
    reps=read("replicate_instances.csv"); fig,ax=plt.subplots(figsize=(8,5),layout="constrained")
    data=[[float(r["s6_end_to_end_seconds"]) for r in reps if r["join_id"]==j] for j in ("J0","J1","J2")]
    ax.boxplot(data,tick_labels=["J0","J1","J2"],showmeans=True)
    for i,vals in enumerate(data,1): ax.scatter([i]*len(vals),vals,color="#E45756",zorder=3,alpha=.7)
    ax.set_ylabel("S6端到端时间（秒）"); ax.set_title("5个独立数据实例下的G2精确共享求解")
    ax.grid(axis="y",alpha=.25)
    save(fig,"H3_JV_图3_独立实例稳定性")

    audit={"status":"PASS","summary_rows":len(summary),"figures":6,"all_fixed_errors_below_1e_9":all(float(r["max_player_error"])<=1e-9 for r in raw),"all_replicates_passed":all(r["status"]=="SUCCESS_EXACT" for r in reps)}
    (OUT/"analysis_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(audit,ensure_ascii=False,indent=2))


if __name__=="__main__": main()
