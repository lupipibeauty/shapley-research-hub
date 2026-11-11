from __future__ import annotations
import json
from pathlib import Path
import matplotlib as mpl
mpl.use("Agg",force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"outputs/v4_0/R2_5"; FIG=OUT/"figures"; FIG.mkdir(exist_ok=True)
mpl.rcParams.update({"font.sans-serif":["Microsoft YaHei","SimHei","Arial Unicode MS","DejaVu Sans"],"axes.unicode_minus":False,"figure.dpi":140,"savefig.dpi":300})
GAMES=["SOU_n12_seed42","D1P_V1","D1P_V2"]; GL={"SOU_n12_seed42":"SOU（n=12，seed=42）","D1P_V1":"D1-P V1","D1P_V2":"D1-P V2"}; METHODS=["FGSV_PAPER_INTERNAL","COMPLETE_PERMUTATION_MC"]; ML={METHODS[0]:"公式内部一致版 FGSV",METHODS[1]:"完整排列 MC"}; C={METHODS[0]:"#D55E00",METHODS[1]:"#0072B2"}

def save(fig,name):
    fig.savefig(FIG/f"{name}.png",bbox_inches="tight",facecolor="white"); fig.savefig(FIG/f"{name}.svg",bbox_inches="tight",facecolor="white"); plt.close(fig)

def convergence():
    d=pd.read_csv(OUT/"run_summary.csv"); d=d[d.comparison_scope=="common_three_owner"]
    fig,axes=plt.subplots(2,3,figsize=(14,8),sharex=True)
    for i,m in enumerate(["G-equal","G-skew"]):
      for j,g in enumerate(GAMES):
        ax=axes[i,j]
        for method in METHODS:
            x=d[(d.owner_map==m)&(d.game==g)&(d.method==method)].sort_values("budget")
            ax.plot(x.budget,x.normalized_total_l1_mean,"o-",color=C[method],label=ML[method]); ax.fill_between(x.budget,x.normalized_total_l1_ci95_low,x.normalized_total_l1_ci95_high,color=C[method],alpha=.16)
        ax.set_yscale("log"); ax.set_title(f"{m}｜{GL[g]}"); ax.set_xlabel("有效总效用调用预算"); ax.set_ylabel("归一化全 owner 总 L1"); ax.grid(alpha=.22)
    h,l=axes[0,0].get_legend_handles_labels(); fig.legend(h,l,loc="upper center",bbox_to_anchor=(.5,.94),ncol=2); fig.suptitle("同为 12 玩家时，FGSV 与完整排列 MC 的精度收敛",y=.995); fig.tight_layout(rect=[0,0,1,.89]); save(fig,"normalized_accuracy_convergence")

def bias_random():
    d=pd.read_csv(OUT/"owner_error_summary.csv"); d=d[(d.comparison_scope=="common_three_owner")&(d.budget==4992)]
    fig,axes=plt.subplots(2,3,figsize=(14,8))
    width=.18
    for i,m in enumerate(["G-equal","G-skew"]):
      for j,g in enumerate(GAMES):
        ax=axes[i,j]; x=d[(d.owner_map==m)&(d.game==g)].groupby("method").agg(abs_bias=("normalized_bias",lambda z:np.abs(z).mean()),random_sd=("normalized_random_sd","mean"))
        pos=np.arange(2)
        for k,method in enumerate(METHODS):
            ax.bar(pos+k*width,[x.loc[method,"abs_bias"],x.loc[method,"random_sd"]],width,label=ML[method],color=C[method],alpha=.88)
        ax.set_xticks(pos+width/2,["|平均偏差|","跨种子 SD"]); ax.set_yscale("log"); ax.set_title(f"{m}｜{GL[g]}"); ax.set_ylabel("归一化误差"); ax.grid(axis="y",alpha=.22)
    h,l=axes[0,0].get_legend_handles_labels(); fig.legend(h,l,loc="upper center",bbox_to_anchor=(.5,.94),ncol=2); fig.suptitle("预算 4992：系统性偏差与随机误差",y=.995); fig.tight_layout(rect=[0,0,1,.89]); save(fig,"bias_vs_random_error")

def coverage():
    d=pd.read_csv(OUT/"run_summary.csv"); d=d[d.comparison_scope=="common_three_owner"]
    fig,axes=plt.subplots(2,3,figsize=(14,8),sharex=True,sharey=True)
    for i,m in enumerate(["G-equal","G-skew"]):
      for j,g in enumerate(GAMES):
        ax=axes[i,j]
        for method in METHODS:
            x=d[(d.owner_map==m)&(d.game==g)&(d.method==method)].sort_values("budget")
            ax.plot(x.budget,x.unique_fraction_mean,"o-",color=C[method],label=ML[method])
        ax.set_title(f"{m}｜{GL[g]}"); ax.set_xlabel("有效总效用调用预算"); ax.set_ylabel("唯一联盟数 / 总调用数"); ax.grid(alpha=.22)
    h,l=axes[0,0].get_legend_handles_labels(); fig.legend(h,l,loc="upper center",bbox_to_anchor=(.5,.94),ncol=2); fig.suptitle("联盟访问覆盖与重复访问",y=.995); fig.tight_layout(rect=[0,0,1,.89]); save(fig,"coalition_coverage")

def structure():
    d=pd.read_csv(OUT/"game_property_comparison.csv").set_index("game").loc[GAMES]
    metrics=[("mean_normalized_permutation_marginal_sd","排列边际 SD"),("normalized_interaction_sd","二阶交互 SD"),("mean_normalized_hybrid_abs_error","式(9)混合误差")]
    fig,axes=plt.subplots(1,3,figsize=(13,4.5))
    colors=["#009E73","#56B4E9","#CC79A7"]
    for ax,(col,label) in zip(axes,metrics):
        vals=d[col].to_numpy(); ax.bar([GL[x] for x in GAMES],vals,color=colors); ax.set_yscale("log"); ax.set_title(label); ax.set_ylabel("按效用跨度归一化"); ax.tick_params(axis="x",rotation=18); ax.grid(axis="y",alpha=.22)
    fig.suptitle("三类 12 玩家价值游戏的结构差异",y=.995); fig.tight_layout(rect=[0,0,1,.93]); save(fig,"game_structure_comparison")

def main():
    convergence(); bias_random(); coverage(); structure()
    files=sorted(p.name for p in FIG.iterdir() if p.suffix in {".png",".svg"})
    (FIG/"figure_manifest.json").write_text(json.dumps({"files":files,"normalization":"误差、边际和交互均除以 |U(N)-U(empty)|","uncertainty":"精度曲线为30个算法随机种子的均值与95% t区间；种子不是独立数据环境。","scope":"主图只含共同三 owner 分组；SOU 模4结果保留在CSV与报告的独立对照中。","smoothing":False},ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__": main()
