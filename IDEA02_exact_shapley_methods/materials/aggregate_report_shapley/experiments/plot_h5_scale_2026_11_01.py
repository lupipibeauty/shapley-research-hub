from __future__ import annotations

import csv
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "v4_0" / "H5_SCALE_2026_11_01"
FIG = OUT / "figures"


def read_csv(name: str) -> list[dict[str, str]]:
    with (OUT / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def choose_chinese_font() -> str:
    names = {item.name for item in font_manager.fontManager.ttflist}
    for candidate in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"):
        if candidate in names:
            return candidate
    raise RuntimeError("未找到可用中文字体")


def save(fig: plt.Figure, stem: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "svg"):
        fig.savefig(FIG / f"{stem}.{suffix}", dpi=220 if suffix == "png" else None, bbox_inches="tight")
    plt.close(fig)


def f(value: str) -> float:
    return float(value) if value not in ("", "NA") else math.nan


def median(values: list[float]) -> float:
    return float(np.median(np.asarray(values, dtype=float)))


def main() -> None:
    font = choose_chinese_font()
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [font],
            "axes.unicode_minus": False,
            "figure.dpi": 140,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    instances = read_csv("instance_structural_metrics.csv")
    states = read_csv("state_growth_summary.csv")
    perf = read_csv("performance_summary.csv")

    # Figure 1: player scale. Exact reachable counts are separated from upper bounds.
    g1 = sorted(
        [row for row in states if row["config_id"].startswith("G1_N")],
        key=lambda row: int(row["config_id"].split("_N", 1)[1].split("_", 1)[0]),
    )
    ns = [int(row["config_id"].split("_N", 1)[1].split("_", 1)[0]) for row in g1]
    exact = [f(row["reachable_states_median"]) for row in g1]
    upper = []
    for row, n in zip(g1, ns):
        subset = [r for r in instances if r["config_id"] == row["config_id"]]
        upper.append(median([float(r["factorized_type_grid_upper"]) for r in subset]))
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    valid = [(n, y) for n, y in zip(ns, exact) if not math.isnan(y)]
    ax.plot([x for x, _ in valid], [math.log10(y) for _, y in valid], "o-", lw=2, label="实际可达状态（已精确计数）")
    ax.plot(ns, [math.log10(value) for value in upper], "s--", lw=1.7, label="类型因子格上界")
    ax.plot(ns, [n * math.log10(2.0) for n in ns], ":", lw=1.5, color="#666666", label="全联盟数 $2^n$")
    ax.set_xscale("log")
    ax.set_xlabel("逻辑玩家数 n（对数轴）")
    ax.set_ylabel("$\\log_{10}$(状态/联盟数)")
    ax.set_title("固定4叶、4族时的联合状态增长")
    ax.grid(alpha=0.25, which="both")
    ax.legend(fontsize=9)
    save(fig, "fig1_player_scale_state_growth")

    # Figure 2: two controlled structural sweeps.
    leaf_rows = sorted(
        [row for row in states if row["config_id"].startswith("G2_LEAF")],
        key=lambda row: int(re.search(r"G2_LEAF_L(\d+)", row["config_id"]).group(1)),
    )
    dim_rows = sorted(
        [row for row in states if row["config_id"].startswith("G2_ATTRIBUTE")],
        key=lambda row: int(re.search(r"G2_ATTRIBUTE_D(\d+)", row["config_id"]).group(1)),
    )
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.1), sharey=True)
    axes[0].plot(
        [int(re.search(r"G2_LEAF_L(\d+)", row["config_id"]).group(1)) for row in leaf_rows],
        [f(row["reachable_states_median"]) for row in leaf_rows],
        "o-",
        lw=2,
        color="#0072B2",
    )
    axes[0].set_xlabel("叶节点数 L")
    axes[0].set_ylabel("实际可达状态数（对数轴）")
    axes[0].set_title("增加真实叶节点")
    axes[1].plot(
        [int(re.search(r"G2_ATTRIBUTE_D(\d+)", row["config_id"]).group(1)) for row in dim_rows],
        [f(row["reachable_states_median"]) for row in dim_rows],
        "s-",
        lw=2,
        color="#D55E00",
    )
    axes[1].set_xlabel("有效基础统计维度 d")
    axes[1].set_title("增加真实统计属性")
    for ax in axes:
        ax.set_yscale("log")
        ax.grid(alpha=0.25, which="both")
    fig.suptitle("固定 n=16 时的结构变量对照")
    fig.tight_layout()
    save(fig, "fig2_leaf_and_attribute_state_growth")

    # Figure 3: same raw input, different sharing; representation vs evaluation.
    share_order = ["INDEPENDENT", "PARTIAL", "FULL"]
    share_ids = {label: f"G3_SHARE_{label}_N16_L4_D4" for label in share_order}
    state_by_share = {
        label: f(next(row["reachable_states_median"] for row in states if row["config_id"] == config_id))
        for label, config_id in share_ids.items()
    }
    b0_time = {}
    for label, config_id in share_ids.items():
        for mode in ("additive", "geometric"):
            match = next(
                row
                for row in perf
                if row["config_id"] == config_id
                and row["score_mode"] == mode
                and row["method"] == "B0_FULL_ENUMERATION"
            )
            b0_time[(label, mode)] = f(match["wall_median_seconds"])
    x = np.arange(len(share_order))
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.2))
    axes[0].bar(x, [state_by_share[label] for label in share_order], color=["#0072B2", "#56B4E9", "#009E73"])
    axes[0].set_xticks(x, ["独立", "部分共享", "完全共享"])
    axes[0].set_yscale("log")
    axes[0].set_ylabel("可达状态数（对数轴）")
    axes[0].set_title("状态表示成本")
    width = 0.36
    axes[1].bar(x - width / 2, [b0_time[(label, "additive")] for label in share_order], width, label="可加评分")
    axes[1].bar(x + width / 2, [b0_time[(label, "geometric")] for label in share_order], width, label="几何评分")
    axes[1].set_xticks(x, ["独立", "部分共享", "完全共享"])
    axes[1].set_ylabel("B0中位运行时间（秒）")
    axes[1].set_title("价值评价成本")
    axes[1].legend()
    for ax in axes:
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("同一基础状态下：表示与评价分开审计")
    fig.tight_layout()
    save(fig, "fig3_sharing_representation_vs_value_cost")

    # Figure 4: runtime comparison for methods that actually completed.
    selected = {
        "G1_N12_L4_D4_ORIGINAL_FAMILIES": "G1 n=12",
        "G2_LEAF_L2_N16_D4": "G2 L=2",
        "G2_LEAF_L4_N16_D4": "G2 L=4",
        "G3_SHARE_FULL_N16_L4_D4": "G3完全共享",
    }
    methods = [
        "B0_FULL_ENUMERATION",
        "B2_STATE_DP",
        "B3_LEAF_FACTOR",
        "B4_TYPE_VARIABLE_ELIMINATION",
    ]
    labels = {"B0_FULL_ENUMERATION": "B0", "B2_STATE_DP": "B2", "B3_LEAF_FACTOR": "B3", "B4_TYPE_VARIABLE_ELIMINATION": "B4"}
    colors = ["#444444", "#0072B2", "#D55E00", "#009E73"]
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    base = np.arange(len(selected))
    width = 0.19
    for index, (method, color) in enumerate(zip(methods, colors)):
        values = []
        for config_id in selected:
            matches = [row for row in perf if row["config_id"] == config_id and row["method"] == method and row["status"] == "SUCCESS"]
            values.append(f(matches[0]["wall_median_seconds"]) if matches else math.nan)
        ax.bar(base + (index - 1.5) * width, values, width, label=labels[method], color=color)
    ax.set_xticks(base, list(selected.values()))
    ax.set_yscale("log")
    ax.set_ylabel("中位运行时间（秒，对数轴）")
    ax.set_title("已通过资源门槛的精确方法运行成本")
    ax.legend(ncol=4)
    ax.grid(axis="y", alpha=0.25, which="both")
    save(fig, "fig4_runtime_cost_comparison")

    captions = """# H5-SCALE 图注与数据来源

- 图1：G1 固定4叶和4族。实线只连接已精确计数的可达状态；虚线是类型因子格上界，点线是 $2^n$，三者不得混同。
- 图2：n=16 的两个单因素扫描；新叶和新属性都实际进入评分，不是虚假标签。
- 图3：G3 在同一原始记录上改变族间共享；左图表示状态数，右图表示 B0 价值评价+求解的中位总时间。
- 图4：只展示真实完成且通过正确性关卡的精确方法；空缺不补值。

数据均来自 `outputs/v4_0/H5_SCALE_2026_11_01/` 内本轮真实 CSV。
"""
    (FIG / "figure_captions.md").write_text(captions, encoding="utf-8")


if __name__ == "__main__":
    main()
