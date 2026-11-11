from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "v4_0" / "H5_R_2026_11_01"
FIG = OUT / "figures"
METHOD_LABEL = {
    "S0_PER_FOCUS_B2": "S0 逐焦点B2",
    "S1_PER_FOCUS_B3": "S1 逐焦点B3",
    "S2_PER_FOCUS_B4": "S2 逐焦点B4",
    "S3_SHARED_FORWARD_DIVISION": "S3 共享前向",
    "S4_PREFIX_SUFFIX_REUSE": "S4 前后缀复用",
    "S5_TYPE_MULTI_OUTPUT_VE": "S5 类型多输出",
    "S6_REVERSE_MULTILINEAR_AD": "S6 反向求导",
    "V1_COORDINATE_DECOMPOSITION": "V1逐坐标分解",
}
GAME_LABEL = {
    "D1P_V1": "D1-P V1",
    "D1P_V2": "D1-P V2",
    "SCALE_N12_V2": "生成实例 n=12",
    "SCALE_N16_V2": "生成实例 n=16",
}


def rows(name: str) -> list[dict[str, str]]:
    with (OUT / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def numeric(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def setup() -> None:
    plt.rcParams.update(
        {
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "font.size": 9,
            "figure.dpi": 140,
            "savefig.dpi": 300,
        }
    )
    FIG.mkdir(parents=True, exist_ok=True)


def save(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIG / f"{stem}.png", bbox_inches="tight")
    fig.savefig(FIG / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)


def timing_decomposition(summary: list[dict[str, str]]) -> None:
    methods = list(METHOD_LABEL)[:7]
    games = list(GAME_LABEL)
    fig, axes = plt.subplots(2, 2, figsize=(14, 8.2), constrained_layout=True)
    colors = ("#4C78A8", "#F58518")
    for ax, game in zip(axes.flat, games, strict=True):
        subset = {r["method"]: r for r in summary if r["game_id"] == game}
        preprocess = [numeric(subset[m]["shared_preprocess_seconds_median"]) for m in methods]
        solve = [numeric(subset[m]["all_player_solve_seconds_median"]) for m in methods]
        x = np.arange(len(methods))
        ax.bar(x, preprocess, color=colors[0], label="共享前处理")
        ax.bar(x, solve, bottom=preprocess, color=colors[1], label="全部玩家求解")
        ax.set_title(GAME_LABEL[game])
        ax.set_ylabel("时间（秒，中位数）")
        ax.set_xticks(x, [f"S{i}" for i in range(7)])
        ax.grid(axis="y", alpha=0.25)
    axes[0, 0].legend(frameon=False, ncol=2)
    fig.suptitle("H5-R：共享前处理与全玩家求解耗时分解（同一冻结实例重复3次）", fontsize=13)
    save(fig, "H5_R_图1_耗时分解")


def state_reuse(summary: list[dict[str, str]]) -> None:
    methods = list(METHOD_LABEL)[:7]
    games = list(GAME_LABEL)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4), constrained_layout=True)
    width = 0.18
    x = np.arange(len(methods))
    for offset, game in enumerate(games):
        subset = {r["method"]: r for r in summary if r["game_id"] == game}
        rebuild = [numeric(subset[m]["state_rebuild_count"]) for m in methods]
        terminal = [numeric(subset[m]["terminal_state_visits"]) for m in methods]
        axes[0].bar(x + (offset - 1.5) * width, rebuild, width, label=GAME_LABEL[game])
        axes[1].bar(x + (offset - 1.5) * width, terminal, width, label=GAME_LABEL[game])
    axes[0].set_title("状态结构重复构建次数")
    axes[0].set_ylabel("重建次数")
    axes[1].set_title("终端状态访问量（对数尺度）")
    axes[1].set_ylabel("访问次数")
    axes[1].set_yscale("log")
    for ax in axes:
        ax.set_xticks(x, [f"S{i}" for i in range(7)])
        ax.set_xlabel("算法版本")
        ax.grid(axis="y", alpha=0.25)
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle("H5-R：复用机制减少结构重建，但不必然减少全部状态评价", fontsize=13)
    save(fig, "H5_R_图2_状态复用")


def v1_v2_comparison(summary: list[dict[str, str]]) -> None:
    methods = list(METHOD_LABEL)[:7]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2), constrained_layout=True)
    x = np.arange(len(methods))
    width = 0.36
    for offset, game in enumerate(("D1P_V1", "D1P_V2")):
        subset = {r["method"]: r for r in summary if r["game_id"] == game}
        values = [numeric(subset[m]["end_to_end_seconds_median"]) for m in methods]
        axes[0].bar(x + (offset - 0.5) * width, values, width, label=GAME_LABEL[game])
    axes[0].set_xticks(x, [f"S{i}" for i in range(7)])
    axes[0].set_title("口径A：相同联合状态表示")
    axes[0].set_ylabel("端到端时间（秒，中位数）")
    axes[0].legend(frameon=False)
    axes[0].grid(axis="y", alpha=0.25)

    v1 = next(r for r in summary if r["game_id"] == "D1P_V1" and r["method"] == "V1_COORDINATE_DECOMPOSITION")
    v2_candidates = [r for r in summary if r["game_id"] == "D1P_V2" and r["method"] in methods]
    v2 = min(v2_candidates, key=lambda r: numeric(r["end_to_end_seconds_median"]))
    labels = ["V1逐坐标分解", f"V2最优实测\n{METHOD_LABEL[v2['method']]}"]
    values = [numeric(v1["end_to_end_seconds_median"]), numeric(v2["end_to_end_seconds_median"])]
    bars = axes[1].bar(labels, values, color=["#54A24B", "#E45756"])
    axes[1].bar_label(bars, fmt="%.3f秒", padding=3)
    axes[1].set_title("口径B：各价值函数最强适用精确方法")
    axes[1].set_ylabel("端到端时间（秒，中位数）")
    axes[1].grid(axis="y", alpha=0.25)
    fig.suptitle("H5-R：V1与V2的两种公平比较口径", fontsize=13)
    save(fig, "H5_R_图3_V1与V2比较")


def main() -> None:
    setup()
    summary = rows("performance_summary.csv")
    timing_decomposition(summary)
    state_reuse(summary)
    v1_v2_comparison(summary)
    print(FIG)


if __name__ == "__main__":
    main()
