from __future__ import annotations

import csv
import json
from fractions import Fraction
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "v4_0" / "AB_N3_L_N4_DP_2026_10_31"
FIG = BASE / "figures"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def f(text: str) -> float:
    return float(Fraction(text))


def configure_chinese_font() -> str:
    candidates = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC"]
    available = {item.name for item in font_manager.fontManager.ttflist}
    selected = next((name for name in candidates if name in available), "DejaVu Sans")
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [selected, "DejaVu Sans"],
            "axes.unicode_minus": False,
            "figure.dpi": 140,
            "savefig.dpi": 300,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    return selected


def save_all(fig, stem: str) -> list[str]:
    outputs = []
    for suffix in ("png", "svg", "pdf"):
        target = FIG / f"{stem}.{suffix}"
        fig.savefig(target, bbox_inches="tight", facecolor="white")
        outputs.append(str(target.relative_to(ROOT)))
    return outputs


def plot_value_decomposition() -> list[str]:
    rows = read_csv(BASE / "v1_record_shapley_comparison.csv")
    players = [row["record_id"] for row in rows]
    linear = np.array([f(row["B_exact_linear_part"]) for row in rows])
    ratio = np.array([f(row["C_ratio_state_DP"]) for row in rows])
    exact = np.array([f(row["A_existing_4096_exact_V1"]) for row in rows])
    x = np.arange(len(players))
    fig, ax = plt.subplots(figsize=(10.2, 5.6), constrained_layout=True)
    ax.bar(x, linear, color="#4C78A8", label="线性计数部分（AB-N3-L）")
    ax.bar(x, ratio, bottom=linear, color="#F58518", label="比例评分部分（AB-N4-DP）")
    ax.scatter(x, exact, marker="x", s=52, linewidths=1.8, color="#111111", label="4096联盟精确真值", zorder=3)
    ax.set_xticks(x, players)
    ax.set_ylabel("记录级 Shapley 收益")
    ax.set_xlabel("逻辑记录玩家")
    ax.set_title("V1 记录级 Shapley 的线性来源与比例状态分解")
    ax.grid(axis="y", color="#D8D8D8", linewidth=0.7, alpha=0.75)
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.14), frameon=False)
    ax.text(
        0.01,
        0.98,
        "确定性精确计算；两部分之和与真值逐记录完全重合",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        color="#444444",
    )
    return save_all(fig, "figure_1_v1_shapley_decomposition")


def plot_state_costs() -> list[str]:
    rows = [
        row
        for row in read_csv(BASE / "AB_N4_DP" / "dp_state_summary.csv")
        if row["focal_type"] != "irrelevant"
    ]
    metric_short = {
        "category_a_target_share": "A类比例",
        "category_b_target_share": "B类比例",
    }
    labels = [f'{row["node"]}\n{metric_short[row["metric"]]}' for row in rows]
    states = np.array([int(row["terminal_state_count"]) for row in rows])
    transitions = np.array([int(row["transition_updates"]) for row in rows])
    types = [row["focal_type"] for row in rows]
    colors = ["#2A9D8F" if kind == "target" else "#E76F51" for kind in types]
    markers = ["o" if kind == "target" else "s" for kind in types]
    x = np.arange(len(rows))
    fig, axes = plt.subplots(2, 1, figsize=(12.2, 7.8), sharex=True, constrained_layout=True)
    axes[0].bar(x, states, color=colors, width=0.72)
    axes[0].set_ylabel("终端状态数")
    axes[0].set_title("AB-N4-DP 各比例坐标代表玩家的实际状态与转移成本")
    axes[0].grid(axis="y", color="#D8D8D8", linewidth=0.7, alpha=0.75)
    for index, (value, marker, color) in enumerate(zip(transitions, markers, colors)):
        axes[1].scatter(index, value, marker=marker, color=color, s=38, zorder=3)
        axes[1].vlines(index, 0, value, color=color, linewidth=1.2, alpha=0.8)
    axes[1].set_ylabel("转移写入次数")
    axes[1].set_xlabel("报表节点与比例指标（每坐标按实际存在的目标/非目标类型分别运行）")
    axes[1].grid(axis="y", color="#D8D8D8", linewidth=0.7, alpha=0.75)
    axes[1].set_xticks(x, labels, rotation=55, ha="right", fontsize=8)
    axes[0].scatter([], [], marker="o", color="#2A9D8F", label="目标类别代表玩家")
    axes[0].scatter([], [], marker="s", color="#E76F51", label="非目标类别代表玩家")
    axes[0].legend(loc="upper left", frameon=False, ncol=2)
    axes[1].text(
        0.01,
        0.97,
        "状态少仅是本固定12玩家实例的观测，不构成一般复杂度证明",
        transform=axes[1].transAxes,
        ha="left",
        va="top",
        fontsize=9,
        color="#444444",
    )
    return save_all(fig, "figure_2_dp_state_transition_costs")


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    font = configure_chinese_font()
    outputs = plot_value_decomposition() + plot_state_costs()
    manifest = {
        "font": font,
        "input_files": [
            "outputs/v4_0/AB_N3_L_N4_DP_2026_10_31/v1_record_shapley_comparison.csv",
            "outputs/v4_0/AB_N3_L_N4_DP_2026_10_31/AB_N4_DP/dp_state_summary.csv",
        ],
        "outputs": outputs,
        "uncertainty": "none; deterministic exact computations",
        "smoothing": False,
        "captions": {
            "figure_1": "蓝色为21个计数坐标的官方来源算法线性部分，橙色为14个比例坐标的独立计数状态DP；黑色叉号为4096联盟精确V1真值。",
            "figure_2": "14个比例坐标中实际存在的27个目标/非目标代表玩家DP的终端状态数与转移写入次数；无关玩家按零边际直接跳过。",
        },
    }
    (FIG / "figure_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
