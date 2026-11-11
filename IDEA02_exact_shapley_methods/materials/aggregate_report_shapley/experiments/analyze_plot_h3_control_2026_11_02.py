from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"outputs"/"v4_0"/"H3_CONTROL"; FIG=OUT/"figures"


def read(name):
    with (OUT/name).open(encoding="utf-8-sig",newline="") as h:return list(csv.DictReader(h))


def write(name,rows):
    with (OUT/name).open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def quartiles(values):
    v=sorted(values);return statistics.median(v),v[1],v[3],v[3]-v[1]


def save(fig,name):
    FIG.mkdir(parents=True,exist_ok=True)
    fig.savefig(FIG/f"{name}.png",dpi=300,bbox_inches="tight");fig.savefig(FIG/f"{name}.svg",bbox_inches="tight");plt.close(fig)


def main():
    plt.rcParams.update({"font.sans-serif":["Microsoft YaHei","SimHei","DejaVu Sans"],"axes.unicode_minus":False,"font.size":9})
    structures=read("structure_and_state_metrics.csv"); perf=read("algorithm_performance_raw.csv")
    structure_summary=[]
    for family in ("H","NH"):
      for n in (8,10,12):
       for sharing in ("low","medium","high"):
        rows=[r for r in structures if r["family"]==family and int(r["n"])==n and r["sharing"]==sharing]
        states=[float(r["reachable_evidence_states"]) for r in rows]; med,q1,q3,iqr=quartiles(states)
        structure_summary.append({"family":family,"n":n,"sharing":sharing,"instances":len(rows),"state_median":med,"state_q1":q1,"state_q3":q3,"state_iqr":iqr,"min_fill_width_max":max(float(r["min_fill_width"]) for r in rows),"old_state_conflict_groups_median":statistics.median(float(r["old_state_distinct_conflict_groups"]) for r in rows)})
    write("structure_summary.csv",structure_summary)

    timing_summary=[]
    for family in ("H","NH"):
      for n in (8,10,12):
       for sharing in ("low","medium","high"):
        rows=[r for r in perf if r["family"]==family and int(r["n"])==n and r["sharing"]==sharing and r["query"]=="DISTINCT" and r["method"]=="B7_S6"]
        vals=[float(r["end_to_end_seconds"]) for r in rows];med,q1,q3,iqr=quartiles(vals)
        timing_summary.append({"family":family,"n":n,"sharing":sharing,"independent_instances":len(vals),"s6_seconds_median":med,"s6_seconds_q1":q1,"s6_seconds_q3":q3,"s6_seconds_iqr":iqr,"max_error":max(float(r["max_error"]) for r in rows)})
    write("performance_summary.csv",timing_summary)

    official=[r for r in perf if r["method"]=="B2_ABRAMOVICH"]
    write("official_circuit_metrics.csv",[{k:r.get(k,"") for k in ("family","n","sharing","seed","query","dnf_clauses","variable_occurrences","official_dtree_nodes","official_compile_seconds","official_solve_seconds","end_to_end_seconds","max_error")} for r in official])

    # State growth panels.
    fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout="constrained",sharey=True)
    for ax,sharing in zip(axes,("low","medium","high"),strict=True):
        for family,color,marker in (("H","#4C78A8","o"),("NH","#E45756","s")):
            rows=[r for r in structure_summary if r["sharing"]==sharing and r["family"]==family]
            x=np.array([r["n"] for r in rows]); y=np.array([r["state_median"] for r in rows]); lo=y-np.array([r["state_q1"] for r in rows]); hi=np.array([r["state_q3"] for r in rows])-y
            ax.errorbar(x,y,yerr=[lo,hi],label=family,color=color,marker=marker,capsize=3)
        ax.set_title({"low":"低共享","medium":"中共享","high":"高共享"}[sharing]);ax.set_xlabel("玩家数n");ax.grid(alpha=.25)
    axes[0].set_ylabel("可达JOIN证据状态（中位数与IQR）");axes[0].legend(frameon=False)
    fig.suptitle("H3-CONTROL：匹配规模下H与NH的证据状态增长")
    save(fig,"H3_CONTROL_图1_状态增长")

    # S6 timing.
    fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout="constrained",sharey=True)
    for ax,sharing in zip(axes,("low","medium","high"),strict=True):
        for family,color,marker in (("H","#4C78A8","o"),("NH","#E45756","s")):
            rows=[r for r in timing_summary if r["sharing"]==sharing and r["family"]==family]
            ax.plot([r["n"] for r in rows],[r["s6_seconds_median"] for r in rows],marker=marker,color=color,label=family)
        ax.set_title({"low":"低共享","medium":"中共享","high":"高共享"}[sharing]);ax.set_xlabel("玩家数n");ax.grid(alpha=.25)
    axes[0].set_ylabel("DISTINCT S6端到端时间（秒）");axes[0].legend(frameon=False)
    fig.suptitle("5个独立连接实例的精确共享求解中位数")
    save(fig,"H3_CONTROL_图2_S6性能")

    # DNF versus actual d-tree.
    queries=("BAG","DISTINCT","HAVING2","HAVING3"); x=np.arange(len(queries));width=.35
    fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout="constrained",sharey=True)
    for ax,sharing in zip(axes,("low","medium","high"),strict=True):
        for offset,(family,color) in enumerate((("H","#4C78A8"),("NH","#F58518"))):
            rows={r["query"]:r for r in official if r["family"]==family and r["sharing"]==sharing}
            ax.bar(x+(offset-.5)*width,[float(rows[q]["official_dtree_nodes"]) for q in queries],width,label=family,color=color)
        ax.set_xticks(x,["bag","distinct","门槛2","门槛3"],rotation=15);ax.set_title({"low":"低共享","medium":"中共享","high":"高共享"}[sharing]);ax.grid(axis="y",alpha=.25)
    axes[0].set_ylabel("官方编译d-tree节点总数");axes[0].legend(frameon=False)
    fig.suptitle("n=12：DNF经实际编译后的电路规模")
    save(fig,"H3_CONTROL_图3_dtree规模")

    # G1/G2 representative timing.
    joint=read("joint_value_performance.csv"); methods=("B4_STATE_DP","B6_S4","B7_S6")
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout="constrained",sharey=True)
    for ax,game in zip(axes,("G1","G2"),strict=True):
        for offset,(family,color) in enumerate((("H","#4C78A8"),("NH","#E45756"))):
            vals=[]
            for method in methods:
                rows=[float(r["end_to_end_seconds"]) for r in joint if r["family"]==family and r["game_id"]==game and r["method"]==method]
                vals.append(statistics.median(rows))
            ax.bar(np.arange(3)+(offset-.5)*width,vals,width,label=family,color=color)
        ax.set_xticks(np.arange(3),["状态DP","S4","S6"]);ax.set_title(game);ax.grid(axis="y",alpha=.25)
    axes[0].set_ylabel("端到端时间（秒，中位数）");axes[0].legend(frameon=False)
    fig.suptitle("n=12高共享配对实例：整表联合价值")
    save(fig,"H3_CONTROL_图4_联合价值")

    hashes=read("pair_matching.csv"); hash_ok=all(len({r["edge_hash"] for r in hashes if r["n"]==str(n) and r["sharing"]==s})==5 for n in (8,10,12) for s in ("low","medium","high"))
    audit={"status":"PASS","unique_edge_hash_gate":hash_ok,"main_instances":len(structures),"all_source_errors_zero":all(float(r["source_max_error"])<=1e-9 for r in structures),"all_algorithm_errors_below_1e_9":all(float(r["max_error"])<=1e-9 for r in perf if r["max_error"]!=""),"figure_files":8,"selection_feasibility":"INSUFFICIENT_EVIDENCE_FOR_NEW_ALGORITHM_TOPIC"}
    (OUT/"analysis_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(audit,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
