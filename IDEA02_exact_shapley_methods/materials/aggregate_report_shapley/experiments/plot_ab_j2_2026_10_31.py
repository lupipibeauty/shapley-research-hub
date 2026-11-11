from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "v4_0" / "AB_J2_2026_10_31"
FIG = BASE / "figures"
GAME_LABELS = {
    "Q1_COUNT_STAR_BAG": "Q1 连接行计数",
    "Q2_COUNT_DISTINCT_KEY": "Q2 去重键计数",
    "Q3_HAVING_COUNT_GE_2": "Q3 门槛通过键计数",
}
COLORS = ["#0072B2", "#D55E00", "#009E73"]
HATCHES = ["", "//", "xx"]


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def configure_font():
    available = {item.name for item in font_manager.fontManager.ttflist}
    candidates = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC"]
    selected = next((name for name in candidates if name in available), "DejaVu Sans")
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [selected, "DejaVu Sans"],
            "axes.unicode_minus": False,
            "figure.dpi": 140,
            "savefig.dpi": 300,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    return selected


def save_all(fig, stem):
    outputs = []
    for suffix in ("png", "svg", "pdf"):
        path = FIG / (stem + "." + suffix)
        fig.savefig(path, bbox_inches="tight", facecolor="white")
        outputs.append(str(path.relative_to(ROOT)))
    plt.close(fig)
    return outputs


def plot_alliance_distribution():
    rows = read_csv(BASE / "coalition_value_distribution.csv")
    lookup = {(row["game"], int(row["coalition_value"])): int(row["coalition_count"]) for row in rows}
    values = np.arange(6)
    width = 0.24
    fig, ax = plt.subplots(figsize=(9.4, 5.6), constrained_layout=True)
    for index, game in enumerate(GAME_LABELS):
        heights = [lookup.get((game, value), 0) for value in values]
        ax.bar(
            values + (index - 1) * width,
            heights,
            width=width,
            color=COLORS[index],
            edgecolor="#222222",
            linewidth=0.6,
            hatch=HATCHES[index],
            label=GAME_LABELS[game],
        )
    ax.set(xlabel="联盟查询值", ylabel="64个联盟中的出现次数", title="AB-J2 三类查询的完整联盟值分布")
    ax.set_xticks(values)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", color="#D8D8D8", linewidth=0.7, alpha=0.75)
    ax.legend(frameon=False, ncol=1, loc="upper right")
    ax.text(
        0.01,
        0.98,
        "完整枚举64个联盟；无抽样、无置信区间",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        color="#444444",
    )
    return save_all(fig, "figure_1_alliance_value_distribution")


def plot_shapley_and_expression():
    shapley = read_csv(BASE / "record_shapley.csv")
    stats = read_csv(BASE / "source_expression_stats.csv")
    players = ["p1", "p2", "p3", "p4", "p5", "p6"]
    x = np.arange(len(players))
    width = 0.24
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 5.8), constrained_layout=True, gridspec_kw={"width_ratios": [1.7, 1]})
    for index, game in enumerate(GAME_LABELS):
        game_rows = {row["player"]: row for row in shapley if row["game"] == game}
        exact = [float(game_rows[player]["exact_record_shapley_float"]) for player in players]
        official = [float(game_rows[player]["official_reduced_DNF_shapley"]) for player in players]
        positions = x + (index - 1) * width
        axes[0].bar(
            positions,
            exact,
            width=width,
            color=COLORS[index],
            edgecolor="#222222",
            linewidth=0.6,
            hatch=HATCHES[index],
            label=GAME_LABELS[game],
        )
        axes[0].scatter(positions, official, marker="_", s=155, linewidths=1.6, color="#111111", zorder=3)
    axes[0].set_xticks(x, players)
    axes[0].set(xlabel="基础记录玩家", ylabel="记录级 Shapley", title="精确 Shapley 与官方归约输入结果")
    axes[0].set_ylim(bottom=0)
    axes[0].grid(axis="y", color="#D8D8D8", linewidth=0.7, alpha=0.75)
    axes[0].legend(frameon=False, fontsize=9)
    axes[0].text(
        0.02,
        0.97,
        "黑色短线：官方LExaShap（与柱高完全重合）",
        transform=axes[0].transAxes,
        ha="left",
        va="top",
        fontsize=8.5,
        color="#444444",
    )

    game_order = list(GAME_LABELS)
    clauses = [int(next(row for row in stats if row["game"] == game)["dnf_clause_count"]) for game in game_order]
    occurrences = [int(next(row for row in stats if row["game"] == game)["variable_occurrences"]) for game in game_order]
    gx = np.arange(3)
    axes[1].bar(gx - 0.18, clauses, width=0.36, color="#6C8EBF", edgecolor="#222222", label="DNF子句数")
    axes[1].bar(gx + 0.18, occurrences, width=0.36, color="#B85450", edgecolor="#222222", hatch="//", label="变量出现次数")
    axes[1].set_xticks(gx, ["Q1", "Q2", "Q3"])
    axes[1].set(xlabel="查询", ylabel="表达规模", title="手工归约后的来源表达规模")
    axes[1].set_ylim(bottom=0)
    axes[1].grid(axis="y", color="#D8D8D8", linewidth=0.7, alpha=0.75)
    axes[1].legend(frameon=False, fontsize=9)
    return save_all(fig, "figure_2_shapley_and_expression_structure")


def plot_runtime():
    rows = read_csv(BASE / "costs.csv")
    stages = [
        ("source_compile_seconds", "来源编译", "o", "-"),
        ("official_dtree_compile_seconds", "d-tree编译", "s", "--"),
        ("official_shapley_solve_seconds", "Shapley求解", "^", "-."),
        ("duckdb_64_alliance_seconds", "64联盟SQL验收", "D", ":"),
    ]
    x = np.arange(3)
    fig, ax = plt.subplots(figsize=(9.2, 5.6), constrained_layout=True)
    for index, (column, label, marker, linestyle) in enumerate(stages):
        values = [float(row[column]) for row in rows]
        ax.plot(x, values, marker=marker, linestyle=linestyle, linewidth=1.8, markersize=6, label=label, color=["#0072B2", "#D55E00", "#009E73", "#000000"][index])
    ax.set_yscale("log")
    ax.set_xticks(x, ["Q1", "Q2", "Q3"])
    ax.set(xlabel="查询", ylabel="单次实测时间（秒，对数轴）", title="AB-J2 分阶段计算成本记录")
    ax.grid(axis="y", which="both", color="#D8D8D8", linewidth=0.7, alpha=0.75)
    ax.legend(frameon=False, ncol=2)
    ax.text(
        0.01,
        0.02,
        "单次固定小实例计时，仅作复现记录；不表示性能优劣或不确定性范围",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.5,
        color="#444444",
    )
    return save_all(fig, "figure_3_runtime_breakdown")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    selected_font = configure_font()
    outputs = plot_alliance_distribution() + plot_shapley_and_expression() + plot_runtime()
    manifest = {
        "matplotlib": matplotlib.__version__,
        "python": sys.version,
        "font": selected_font,
        "inputs": [
            "outputs/v4_0/AB_J2_2026_10_31/coalition_value_distribution.csv",
            "outputs/v4_0/AB_J2_2026_10_31/record_shapley.csv",
            "outputs/v4_0/AB_J2_2026_10_31/source_expression_stats.csv",
            "outputs/v4_0/AB_J2_2026_10_31/costs.csv",
        ],
        "transformations": ["complete finite-population frequency count", "no smoothing", "no imputation"],
        "uncertainty": "none; complete deterministic enumeration and single-run descriptive timings",
        "missing_data": "none in plotted tables",
        "outputs": outputs,
        "captions": {
            "figure_1": "64个联盟的实际DuckDB查询值频数；Q1保留bag multiplicity，Q2按key去重，Q3统计通过HAVING门槛的key。",
            "figure_2": "左图为逐记录精确Shapley，黑色短线是官方LExaShap在归约DNF上的结果；右图为子句和变量出现次数。",
            "figure_3": "来源编译、d-tree编译、Shapley求解和64联盟SQL验收的单次描述性成本；纵轴为对数尺度。",
        },
        "alt_text": {
            "figure_1": "分组柱状图显示三类查询在64个联盟中的值分布，Q1范围0到5，Q2范围0到2，Q3范围0到1。",
            "figure_2": "逐玩家分组柱状图显示Q1中p1、p2、p4、p5各为1，p3、p6各为0.5；Q2中K1四玩家各0.25，K2两玩家各0.5；Q3只有K1四玩家各0.25。",
            "figure_3": "对数折线图显示三种查询的来源编译最快，64联盟SQL验收最慢；所有计时仅一次运行。",
        },
    }
    (FIG / "figure_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
