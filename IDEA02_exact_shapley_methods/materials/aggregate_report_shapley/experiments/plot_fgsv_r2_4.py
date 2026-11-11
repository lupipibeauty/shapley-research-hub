from __future__ import annotations

import json, sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"outputs/v4_0/R2_4"; FIG=OUT/"figures"; FIG.mkdir(exist_ok=True)
mpl.rcParams.update({"font.sans-serif":["Microsoft YaHei","SimHei","Arial Unicode MS","DejaVu Sans"],"axes.unicode_minus":False,"figure.dpi":140,"savefig.dpi":300})
VL={"V_count":"V-count","V1":"V1","V2_lambda_0_5":"V2 (λ=0.5)"}
ML={"A0_RELEASE_LOGIC_CAPPED":"A0 发布逻辑","A1_ADD_NORMALIZATION":"A1 +归一化","A2_FLOOR_INDEX":"A2 +floor","A3_FIXED_SIZE_FORWARD_DIFFERENCE":"A3 +固定规模差分","A4_COMPLETE_PAPER_INTERNAL":"A4 论文内部一致版"}
COLORS=["#6B4C9A","#D6604D","#4393C3","#1B7837","#E08214"]

def save(fig,name):
    fig.savefig(FIG/f"{name}.png",bbox_inches="tight"); fig.savefig(FIG/f"{name}.svg",bbox_inches="tight"); plt.close(fig)

def exact_approx():
    d=pd.read_csv(OUT/"per_s_exact_and_approx.csv")
    for map_name in d.owner_map.unique():
        sub=d[d.owner_map==map_name]; owners=list(sub.owner.unique())
        fig,axes=plt.subplots(len(owners),3,figsize=(13,3.2*len(owners)),sharex=True)
        for i,o in enumerate(owners):
            for j,v in enumerate(VL):
                x=sub[(sub.owner==o)&(sub.value==v)].sort_values("s")
                ax=axes[i,j]; ax.plot(x.s,x.T8_exact,"o-",label="式(8)精确 T(s)",color="#2166AC"); ax.plot(x.s,x.T9_approx,"s--",label="式(9)近似 T(s)",color="#B2182B")
                ax.axhline(0,color=".55",lw=.7); ax.set_title(f"{VL[v]}｜owner {o}（组规模 {int(x.owner_size.iloc[0])}）"); ax.set_xlabel("联盟规模 s"); ax.set_ylabel("贡献值"); ax.grid(alpha=.22)
        handles,labels=axes[0,0].get_legend_handles_labels(); fig.legend(handles,labels,loc="upper center",bbox_to_anchor=(.5,.94),ncol=2); fig.suptitle(f"{map_name}：精确式(8)与近似式(9)逐 s 对比",y=.995); fig.tight_layout(rect=[0,0,1,.89])
        save(fig,f"exact_vs_approx_{map_name}")

def error_by_s():
    d=pd.read_csv(OUT/"per_s_exact_and_approx.csv")
    fig,axes=plt.subplots(2,3,figsize=(14,7.5),sharex=True)
    for i,m in enumerate(["G-equal","G-skew"]):
        for j,v in enumerate(VL):
            ax=axes[i,j]; x=d[(d.owner_map==m)&(d.value==v)]
            for k,(o,g) in enumerate(x.groupby("owner")):
                g=g.sort_values("s"); ax.plot(g.s,g.T9_minus_T8,"o-",label=f"owner {o}",color=COLORS[k])
            ax.axhline(0,color="black",lw=.8); ax.set_title(f"{m}｜{VL[v]}"); ax.set_xlabel("联盟规模 s"); ax.set_ylabel("式(9)−式(8)"); ax.grid(alpha=.22)
    handles,labels=axes[0,0].get_legend_handles_labels(); fig.legend(handles,labels,loc="upper center",bbox_to_anchor=(.5,.93),ncol=3); fig.suptitle("不同联盟规模的确定性近似误差贡献",y=.995); fig.tight_layout(rect=[0,0,1,.88])
    save(fig,"eq9_error_contribution_by_s")

def convergence():
    d=pd.read_csv(OUT/"ablation_summary.csv")
    fig,axes=plt.subplots(2,3,figsize=(14,8),sharex=True)
    for i,m in enumerate(["G-equal","G-skew"]):
        for j,v in enumerate(VL):
            ax=axes[i,j]; x=d[(d.owner_map==m)&(d.value==v)]
            for k,method in enumerate(ML):
                g=x[x.method==method].groupby("nominal_budget",as_index=False).agg(mae=("mae","mean"),lo=("mae_ci95_low","mean"),hi=("mae_ci95_high","mean"))
                ax.plot(g.nominal_budget,g.mae,"o-",label=ML[method],color=COLORS[k]); ax.fill_between(g.nominal_budget,g.lo,g.hi,color=COLORS[k],alpha=.12)
            ax.set_yscale("symlog",linthresh=1); ax.set_title(f"{m}｜{VL[v]}"); ax.set_xlabel("共同名义调用预算"); ax.set_ylabel("owner 平均绝对误差"); ax.grid(alpha=.22)
    handles,labels=axes[0,0].get_legend_handles_labels(); fig.legend(handles,labels,loc="upper center",bbox_to_anchor=(.5,.93),ncol=3); fig.suptitle("FGSV 官方实现差异顺序消融：收敛曲线（30 个配对种子）",y=.995); fig.tight_layout(rect=[0,0,1,.86])
    save(fig,"ablation_convergence")

def main():
    exact_approx(); error_by_s(); convergence()
    files=sorted(p.name for p in FIG.iterdir() if p.suffix in {".png",".svg"})
    (FIG/"figure_manifest.json").write_text(json.dumps({"files":files,"data_sources":["per_s_exact_and_approx.csv","ablation_summary.csv"],"note":"置信带为30个随机种子的95% t区间；不平滑、不插补。"},ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__": main()
