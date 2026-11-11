from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


COLORS = {
    "additive_proxy": "#0072B2",
    "feature_mlp": "#D55E00",
    "rpv_gnn": "#009E73",
    "rpv_gnn_safe_route": "#56B4E9",
    "cached_permutation_mc": "#CC79A7",
    "regression_msr": "#E69F00",
    "rpv_perturb": "#009E73",
    "mlp_perturb": "#777777",
}

MARKERS = {
    "additive_proxy": "o",
    "feature_mlp": "s",
    "rpv_gnn": "D",
    "rpv_gnn_safe_route": "*",
    "cached_permutation_mc": "o",
    "regression_msr": "^",
    "rpv_perturb": "D",
    "mlp_perturb": "s",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build final Chinese paper figures")
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--external", required=True, type=Path)
    parser.add_argument("--sql", required=True, type=Path)
    parser.add_argument("--perturbation", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _lookup(
    rows: list[dict],
    *,
    metric: str,
    split: str,
    method: str,
    budget: int = 0,
    condition: str = "overall",
) -> dict:
    for row in rows:
        if (
            row["metric"] == metric
            and row["split"] == split
            and row["method"] == method
            and int(row["budget"]) == budget
            and row["condition"] == condition
        ):
            return row
    raise KeyError((metric, split, method, budget, condition))


def _save(fig: plt.Figure, output: Path, stem: str, dpi: int = 600) -> None:
    for suffix in ("png", "pdf"):
        target = output / f"{stem}.{suffix}"
        fig.savefig(
            target,
            dpi=dpi,
            bbox_inches=None,
            facecolor="white",
            transparent=False,
        )
        if suffix == "png":
            from PIL import Image

            with Image.open(target) as image:
                image.convert("RGB").save(
                    target,
                    format="PNG",
                    dpi=(dpi, dpi),
                )


def _point_with_ci(
    ax: plt.Axes,
    row: dict,
    x: float,
    *,
    label: str,
    color: str,
    marker: str,
    linestyle: str = "none",
) -> None:
    mean = float(row["mean"])
    low = float(row["ci95_low"])
    high = float(row["ci95_high"])
    ax.errorbar(
        x,
        mean,
        yerr=[[mean - low], [high - mean]],
        fmt=marker,
        linestyle=linestyle,
        color=color,
        markerfacecolor=color,
        markeredgecolor="white",
        markeredgewidth=0.6,
        markersize=5,
        capsize=2.5,
        linewidth=1.1,
        label=label,
    )


def _main_figure(rows: list[dict], output: Path) -> None:
    splits = (
        ("in_distribution", "分布内测试"),
        ("ood", "组合 OOD 测试"),
        ("scale_ood", "SF1 规模外推"),
    )
    methods = (
        ("additive_proxy", 0, "可加代理"),
        ("feature_mlp", 0, "特征 MLP"),
        ("rpv_gnn", 0, "RPV-GNN"),
        ("rpv_gnn_safe_route", 0, "安全路由"),
        ("cached_permutation_mc", 64, "MC-64"),
        ("cached_permutation_mc", 256, "MC-256"),
        ("cached_permutation_mc", 1024, "MC-1024"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 4.2), layout="constrained")
    handles = []
    labels = []
    for panel_index, (ax, (split, title)) in enumerate(zip(axes, splits)):
        for index, (method, budget, label) in enumerate(methods):
            row = _lookup(
                rows,
                metric="share_l1",
                split=split,
                method=method,
                budget=budget,
            )
            _point_with_ci(
                ax,
                row,
                index,
                label=label,
                color=COLORS[method],
                marker=MARKERS[method],
            )
            if panel_index == 0:
                handles.append(ax.lines[-1])
                labels.append(label)
        ax.set_xticks(range(len(methods)))
        ax.set_xticklabels(
            [item[2] for item in methods],
            rotation=32,
            ha="right",
            fontsize=7.5,
        )
        ax.set_ylabel("玩家份额 L1 误差（越低越好）")
        ax.set_title(title)
    fig.suptitle(
        "三种测试场景下的贡献估算结果（三模型种子，游戏级 Bootstrap 95% CI）",
        fontsize=10,
    )
    fig.legend(
        handles,
        labels,
        loc="outside lower center",
        ncol=7,
        frameon=False,
        fontsize=7.2,
    )
    _save(fig, output, "fig02_main_results")
    plt.close(fig)


def _metric_figure(rows: list[dict], output: Path) -> None:
    metric_specs = (
        ("p95_abs_share", "玩家误差 P95（越低越好）"),
        ("high_value_mae", "高贡献玩家 MAE（越低越好）"),
        ("ndcg3", "NDCG@3（越高越好）"),
        ("owner_l1", "Owner 份额 L1（越低越好）"),
    )
    methods = (
        ("rpv_gnn", 0, "RPV-GNN"),
        ("rpv_gnn_safe_route", 0, "安全路由"),
        ("cached_permutation_mc", 256, "MC-256"),
        ("cached_permutation_mc", 1024, "MC-1024"),
    )
    split_styles = (
        ("in_distribution", "分布内", "#0072B2", "o", "-"),
        ("ood", "组合 OOD", "#D55E00", "s", "--"),
        ("scale_ood", "SF1 规模外推", "#009E73", "^", "-."),
    )
    fig, axes = plt.subplots(2, 2, figsize=(9.6, 5.8), layout="constrained")
    for ax, (metric, title) in zip(axes.reshape(-1), metric_specs):
        for split, split_label, color, marker, linestyle in split_styles:
            for index, (method, budget, _label) in enumerate(methods):
                row = _lookup(
                    rows,
                    metric=metric,
                    split=split,
                    method=method,
                    budget=budget,
                )
                _point_with_ci(
                    ax,
                    row,
                    index,
                    label=split_label if index == 0 else "",
                    color=color,
                    marker=marker,
                    linestyle=linestyle,
                )
        ax.set_xticks(range(len(methods)))
        ax.set_xticklabels(
            [item[2] for item in methods],
            rotation=25,
            ha="right",
            fontsize=7.5,
        )
        ax.set_title(title)
    axes[0, 0].legend(frameon=False, fontsize=7)
    fig.suptitle(
        "尾部、高贡献排序与 Owner 汇总指标（三模型种子，95% CI）",
        fontsize=10,
    )
    _save(fig, output, "fig03_extended_metrics")
    plt.close(fig)


def _regression_figure(rows: list[dict], output: Path) -> None:
    budgets = (64, 256, 1024)
    splits = (
        ("in_distribution", "分布内"),
        ("ood", "组合 OOD"),
        ("scale_ood", "SF1 规模外推"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.4), layout="constrained")
    for ax, (split, title) in zip(axes, splits):
        for method, label, color, marker in (
            ("cached_permutation_mc", "缓存置换 MC", COLORS["cached_permutation_mc"], "o"),
            ("regression_msr", "回归 MSR", COLORS["regression_msr"], "^"),
        ):
            means = []
            lows = []
            highs = []
            for budget in budgets:
                row = _lookup(
                    rows,
                    metric="share_l1",
                    split=split,
                    method=method,
                    budget=budget,
                )
                means.append(float(row["mean"]))
                lows.append(float(row["ci95_low"]))
                highs.append(float(row["ci95_high"]))
            ax.errorbar(
                budgets,
                means,
                yerr=[
                    [mean - low for mean, low in zip(means, lows)],
                    [high - mean for mean, high in zip(means, highs)],
                ],
                marker=marker,
                color=color,
                capsize=2.5,
                linewidth=1.2,
                label=label,
            )
        safe = _lookup(
            rows,
            metric="share_l1",
            split=split,
            method="rpv_gnn_safe_route",
        )
        ax.axhline(
            float(safe["mean"]),
            color=COLORS["rpv_gnn_safe_route"],
            linestyle=":",
            linewidth=1.2,
            label="安全路由",
        )
        ax.set_xscale("log", base=2)
        ax.set_xticks(budgets)
        ax.set_xticklabels([str(item) for item in budgets])
        ax.set_xlabel("名义联盟采样预算")
        ax.set_ylabel("玩家份额 L1 误差")
        ax.set_title(title)
    axes[0].legend(frameon=False, fontsize=7)
    fig.suptitle(
        "同查询预算强基线：回归 MSR 未优于缓存置换 MC",
        fontsize=10,
    )
    _save(fig, output, "fig04_regression_baseline")
    plt.close(fig)


def _graph_perturbation_figure(rows: list[dict], output: Path) -> None:
    splits = (
        ("in_distribution", "分布内"),
        ("ood", "组合 OOD"),
        ("scale_ood", "SF1 规模外推"),
    )
    fractions = (0, 5, 10, 20, 30)
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.3), layout="constrained")
    for ax, (split, title) in zip(axes, splits):
        for family, label, color, marker, linestyle in (
            ("rpv_gnn", "RPV-GNN", COLORS["rpv_perturb"], "D", "-"),
            ("feature_mlp", "特征 MLP（对照）", COLORS["mlp_perturb"], "s", "--"),
        ):
            means = []
            lows = []
            highs = []
            for fraction in fractions:
                row = _lookup(
                    rows,
                    metric="share_l1",
                    split=split,
                    method=f"{family}_perturb_{fraction:02d}",
                )
                means.append(float(row["mean"]))
                lows.append(float(row["ci95_low"]))
                highs.append(float(row["ci95_high"]))
            ax.errorbar(
                fractions,
                means,
                yerr=[
                    [mean - low for mean, low in zip(means, lows)],
                    [high - mean for mean, high in zip(means, highs)],
                ],
                marker=marker,
                linestyle=linestyle,
                color=color,
                capsize=2.5,
                linewidth=1.2,
                label=label,
            )
        ax.set_xticks(fractions)
        ax.set_xlabel("随机删除来源/来源-坐标边比例（%）")
        ax.set_ylabel("玩家份额 L1 误差")
        ax.set_yscale("log")
        ax.set_title(title)
    axes[0].legend(frameon=False, fontsize=7)
    fig.suptitle(
        "图结构扰动鲁棒性（三个抗扰动种子与三个模型种子）",
        fontsize=10,
    )
    _save(fig, output, "fig05_graph_perturbation")
    plt.close(fig)


def _external_figure(external_path: Path, output: Path) -> None:
    payload = json.loads(external_path.read_text(encoding="utf-8"))
    rows = payload["summary"]
    game_labels = {
        "d1p_v1": "D1-P V1",
        "d1p_v2": "D1-P V2",
        "p3_g0": "P3-0 G0",
        "p3_g1": "P3-0 G1",
    }
    methods = (
        ("uniform_base", "均匀基线", "#777777", "o"),
        ("feature_mlp_zero_shot", "特征 MLP 零样本", COLORS["feature_mlp"], "s"),
        ("rpv_gnn_zero_shot", "RPV-GNN 零样本", COLORS["rpv_gnn"], "D"),
    )
    lookup = {
        (row["method"], row["game_id"]): row
        for row in rows
    }
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.5), layout="constrained")
    for ax, metric, title in (
        (axes[0], "share_l1", "玩家份额 L1 误差（越低越好）"),
        (axes[1], "spearman", "玩家份额 Spearman 相关（越高越好）"),
    ):
        for method, label, color, marker in methods:
            values = [
                float(lookup[(method, game_id)][metric])
                for game_id in game_labels
            ]
            ax.scatter(
                range(len(game_labels)),
                values,
                marker=marker,
                color=color,
                s=34,
                label=label,
                edgecolors="white",
                linewidths=0.6,
            )
        ax.set_xticks(range(len(game_labels)))
        ax.set_xticklabels(list(game_labels.values()))
        ax.set_title(title)
        ax.axhline(0.0, color="#BBBBBB", linewidth=0.7)
    axes[0].legend(frameon=False, fontsize=7)
    fig.suptitle(
        "D1-P 与 P3 零样本语义适配（仅 4 个外部游戏，描述性结果）",
        fontsize=10,
    )
    _save(fig, output, "fig06_external_zero_shot")
    plt.close(fig)


def _sql_figure(sql_path: Path, output: Path) -> None:
    payload = json.loads(sql_path.read_text(encoding="utf-8"))
    stages = {row["stage"]: row for row in payload["stages"]}
    component_specs = (
        ("sql_bind_plan", "SQL 绑定/规划"),
        ("lineage_extract", "来源抽取"),
        ("graph_construct", "来源图构造"),
        ("graph_tensorize", "图张量化"),
        ("model_forward", "模型前向"),
        ("owner_aggregate", "Owner 汇总"),
    )
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 3.8), layout="constrained")
    component_values = [
        float(stages[stage]["median_ms"]) for stage, _label in component_specs
    ]
    axes[0].barh(
        range(len(component_specs)),
        component_values,
        color=["#0072B2", "#56B4E9", "#009E73", "#CC79A7", "#D55E00", "#777777"],
    )
    axes[0].set_yticks(range(len(component_specs)))
    axes[0].set_yticklabels([label for _stage, label in component_specs])
    axes[0].set_xscale("log")
    axes[0].set_xlabel("中位时间（ms，对数刻度）")
    axes[0].set_title("RPV-GNN 端到端分阶段成本")
    comparison_specs = (
        ("model_end_to_end", "RPV-GNN"),
        ("mc_64_end_to_end", "MC-64"),
        ("mc_256_end_to_end", "MC-256"),
        ("mc_1024_end_to_end", "MC-1024"),
    )
    values = [
        float(stages[stage]["median_ms"]) for stage, _label in comparison_specs
    ]
    axes[1].barh(
        range(len(comparison_specs)),
        values,
        color=[
            COLORS["rpv_gnn"],
            COLORS["cached_permutation_mc"],
            COLORS["cached_permutation_mc"],
            COLORS["cached_permutation_mc"],
        ],
    )
    axes[1].set_yticks(range(len(comparison_specs)))
    axes[1].set_yticklabels([label for _stage, label in comparison_specs])
    axes[1].set_xscale("log")
    axes[1].set_xlabel("每游戏中位端到端时间（ms，对数刻度）")
    axes[1].set_title("模型与 SQL 采样总成本")
    for ax in axes:
        ax.grid(axis="x", color="#DDDDDD", linewidth=0.5)
    fig.suptitle(
        "DuckDB 来源抽取与模型推理成本（10 个分布内游戏，三次重复的中位数）",
        fontsize=10,
    )
    _save(fig, output, "fig07_sql_end_to_end")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite figure directory: {args.output}")
    args.output.mkdir(parents=True)
    plt.rcParams.update(
        {
            "font.family": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "font.size": 8.5,
            "axes.unicode_minus": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#DDDDDD",
            "grid.linewidth": 0.5,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
        }
    )
    summary_rows = _read_csv(args.summary / "summary_metrics.csv")
    perturb_rows = _read_csv(
        args.perturbation / "summary_metrics.csv"
    )
    _main_figure(summary_rows, args.output)
    _metric_figure(summary_rows, args.output)
    _regression_figure(summary_rows, args.output)
    _graph_perturbation_figure(perturb_rows, args.output)
    _external_figure(args.external, args.output)
    _sql_figure(args.sql, args.output)
    sources = [
        args.summary / "summary_metrics.csv",
        args.external,
        args.sql,
        args.perturbation / "summary_metrics.csv",
    ]
    manifest = {
        "status": "final_course_paper_candidate",
        "language": "zh-CN",
        "engine": "Matplotlib Agg",
        "dpi": 600,
        "background": "white opaque RGB PNG",
        "uncertainty": (
            "game-level 95% bootstrap intervals where available; "
            "external and SQL panels are descriptive"
        ),
        "sources": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources
        },
        "outputs": sorted(
            path.name for path in args.output.iterdir() if path.is_file()
        ),
    }
    (args.output / "figure_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
