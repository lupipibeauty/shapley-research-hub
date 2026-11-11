from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


COLORS = {
    "base_share": "#0072B2",
    "feature_mlp": "#D55E00",
    "rpv_gnn": "#009E73",
    "rpv_gnn_safe_route": "#56B4E9",
    "rpv_gnn_no_edges": "#CC79A7",
    "rpv_gnn_no_anchor": "#000000",
    "permutation_mc": "#0072B2",
}

MARKERS = {
    "base_share": "o",
    "feature_mlp": "s",
    "rpv_gnn": "D",
    "rpv_gnn_safe_route": "*",
    "rpv_gnn_no_edges": "^",
    "rpv_gnn_no_anchor": "P",
    "permutation_mc": "o",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create figures from frozen metric summaries")
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def read_rows(path: Path) -> list[dict]:
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
    raise KeyError((metric, split, method, budget))


def _point(
    ax: plt.Axes,
    x: float,
    row: dict,
    *,
    label: str,
    color: str,
    marker: str,
    offset: float = 0.0,
) -> None:
    mean = float(row["mean"])
    low = float(row["ci95_low"])
    high = float(row["ci95_high"])
    ax.errorbar(
        x + offset,
        mean,
        yerr=[[mean - low], [high - mean]],
        fmt=marker,
        color=color,
        markerfacecolor=color,
        markeredgecolor="white",
        markeredgewidth=0.8,
        markersize=6,
        capsize=3,
        linewidth=1.2,
        label=label,
    )


def _save_figure(fig: plt.Figure, path: Path, *, dpi: int = 600) -> None:
    fig.savefig(path, dpi=dpi, bbox_inches=None, facecolor="white", transparent=False)
    if path.suffix.lower() != ".png":
        return
    from PIL import Image

    with Image.open(path) as image:
        image.convert("RGB").save(path, format="PNG", dpi=(dpi, dpi))


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite figure directory: {args.output}")
    args.output.mkdir(parents=True)
    summary_path = args.summary / "summary_metrics.csv"
    rows = read_rows(summary_path)

    plt.rcParams.update(
        {
            "font.family": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "font.size": 9,
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

    # Figure 2: main model comparison and MC budget curve.
    fig, axes = plt.subplots(2, 2, figsize=(10.0, 5.8), layout="constrained")
    comparison_axes = (axes[0, 0], axes[0, 1], axes[1, 0])
    method_specs = (
        ("base_share", 0, "可加基线"),
        ("feature_mlp", 0, "特征 MLP"),
        ("rpv_gnn", 0, "RPV-GNN"),
        ("rpv_gnn_safe_route", 0, "安全路由"),
        ("permutation_mc", 64, "MC-64"),
        ("permutation_mc", 256, "MC-256"),
        ("permutation_mc", 1024, "MC-1024"),
    )
    comparison_splits = ("in_distribution", "ood", "scale_ood")
    for panel, split in enumerate(comparison_splits):
        ax = comparison_axes[panel]
        for index, (method, budget, label) in enumerate(method_specs):
            row = _lookup(
                rows,
                metric="share_l1",
                split=split,
                method=method,
                budget=budget,
            )
            _point(
                ax,
                float(index),
                row,
                label=label,
                color=COLORS[method],
                marker=MARKERS[method],
            )
        ax.set_xticks(range(len(method_specs)))
        ax.set_xticklabels([item[2] for item in method_specs], rotation=30, ha="right")
        ax.set_ylabel("份额 L1 误差（越低越好）")
        ax.set_title(
            {
                "in_distribution": "分布内测试",
                "ood": "组合分布外测试",
                "scale_ood": "SF1 规模外推",
            }[split]
        )

    budget_ax = axes[1, 1]
    budgets = [64, 256, 1024, 4096]
    for split, marker, line_style in (
        ("in_distribution", "o", "-"),
        ("ood", "s", "--"),
    ):
        means = [
            float(_lookup(rows, metric="share_l1", split=split, method="permutation_mc", budget=budget)["mean"])
            for budget in budgets
        ]
        lows = [
            float(_lookup(rows, metric="share_l1", split=split, method="permutation_mc", budget=budget)["ci95_low"])
            for budget in budgets
        ]
        highs = [
            float(_lookup(rows, metric="share_l1", split=split, method="permutation_mc", budget=budget)["ci95_high"])
            for budget in budgets
        ]
        budget_ax.errorbar(
            budgets,
            means,
            yerr=[
                [mean - low for mean, low in zip(means, lows)],
                [high - mean for mean, high in zip(means, highs)],
            ],
            color=COLORS["permutation_mc"] if split == "in_distribution" else "#D55E00",
            marker=marker,
            linestyle=line_style,
            capsize=3,
            label="MC 分布内" if split == "in_distribution" else "MC 组合分布外",
        )
        rpv = _lookup(rows, metric="share_l1", split=split, method="rpv_gnn")
        budget_ax.axhline(
            float(rpv["mean"]),
            color=COLORS["rpv_gnn"],
            linestyle=":",
            linewidth=1.2,
            label=(
                "RPV-GNN 分布内"
                if split == "in_distribution"
                else "RPV-GNN 组合分布外"
            ),
        )
    budget_ax.set_xscale("log", base=2)
    budget_ax.set_xticks(budgets)
    budget_ax.set_xticklabels([str(item) for item in budgets])
    budget_ax.set_xlabel("边际采样步数（名义预算）")
    budget_ax.set_ylabel("份额 L1 误差")
    budget_ax.set_title("联盟采样预算敏感性")
    budget_ax.legend(fontsize=6, frameon=False)
    fig.suptitle(
        "TPC-H 初步实验结果：三个模型种子，游戏级 Bootstrap 95% 置信区间",
        fontsize=10,
    )
    _save_figure(fig, args.output / "fig02_main_results.png")
    _save_figure(fig, args.output / "fig02_main_results.pdf")
    plt.close(fig)

    # Figure 3: ablation contrast.
    fig, ax = plt.subplots(figsize=(6.4, 3.1), layout="constrained")
    methods = (
        ("rpv_gnn", "完整 RPV-GNN"),
        ("rpv_gnn_no_edges", "去除图边"),
        ("rpv_gnn_no_anchor", "去除可加基线"),
    )
    split_styles = (
        ("in_distribution", -0.18, "#0072B2", "分布内"),
        ("ood", 0.0, "#D55E00", "组合分布外"),
        ("scale_ood", 0.18, "#009E73", "SF1 规模外推"),
    )
    for split, offset, split_color, split_label in split_styles:
        for index, (method, _label) in enumerate(methods):
            row = _lookup(rows, metric="share_l1", split=split, method=method)
            mean = float(row["mean"])
            low = float(row["mean"]) - float(row["ci95_low"])
            high = float(row["ci95_high"]) - float(row["mean"])
            ax.errorbar(
                index + offset,
                mean,
                yerr=[[low], [high]],
                fmt="o",
                markersize=6,
                color=split_color,
                markerfacecolor=split_color,
                markeredgewidth=1.0,
                capsize=3,
                label=split_label if index == 0 else None,
            )
    ax.set_xticks(range(len(methods)))
    ax.set_xticklabels([item[1] for item in methods])
    ax.set_ylabel("份额 L1 误差（越低越好）")
    ax.set_title("")
    ax.legend(frameon=False, loc="upper left")
    fig.suptitle("不同测试场景下的组件消融", fontsize=10)
    _save_figure(fig, args.output / "fig03_ablation.png")
    _save_figure(fig, args.output / "fig03_ablation.pdf")
    plt.close(fig)

    # Figure 4: additional evaluation metrics.
    metric_specs = (
        ("share_l1", "玩家份额 L1 误差", "越低越好"),
        ("owner_l1", "所有者份额 L1 误差", "越低越好"),
        ("spearman", "玩家份额 Spearman 相关", "越高越好"),
        ("top3_overlap", "Top-3 高贡献玩家重合率", "越高越好"),
    )
    metric_fig, metric_axes = plt.subplots(
        2,
        2,
        figsize=(10.0, 6.4),
        layout="constrained",
    )
    split_styles = (
        ("in_distribution", "分布内", "#0072B2", "o", "-"),
        ("ood", "组合分布外", "#D55E00", "s", "--"),
        ("scale_ood", "SF1 规模外推", "#009E73", "^", "-."),
    )
    for ax, (metric_name, title, direction) in zip(
        metric_axes.reshape(-1),
        metric_specs,
    ):
        for split, split_label, color, marker, line_style in split_styles:
            means = []
            lows = []
            highs = []
            for method, budget, _label in method_specs:
                row = _lookup(
                    rows,
                    metric=metric_name,
                    split=split,
                    method=method,
                    budget=budget,
                )
                means.append(float(row["mean"]))
                lows.append(float(row["ci95_low"]))
                highs.append(float(row["ci95_high"]))
            ax.errorbar(
                range(len(method_specs)),
                means,
                yerr=[
                    [mean - low for mean, low in zip(means, lows)],
                    [high - mean for mean, high in zip(means, highs)],
                ],
                color=color,
                marker=marker,
                linestyle=line_style,
                linewidth=1.1,
                markersize=5,
                capsize=2,
                label=split_label,
            )
        ax.set_xticks(range(len(method_specs)))
        ax.set_xticklabels(
            [item[2] for item in method_specs],
            rotation=28,
            ha="right",
            fontsize=7.5,
        )
        ax.set_ylabel(f"{title}（{direction}）")
        ax.set_title(title)
    metric_axes[0, 0].legend(frameon=False, loc="upper right")
    metric_fig.suptitle(
        "评价指标分析：均值与游戏级 Bootstrap 95% 置信区间",
        fontsize=10,
    )
    _save_figure(metric_fig, args.output / "fig04_metric_analysis.png")
    _save_figure(metric_fig, args.output / "fig04_metric_analysis.pdf")
    plt.close(metric_fig)

    # Figure 5: tail error, macro-condition error, high-value error, and NDCG@3.
    extended_specs = (
        ("share_l1", "macro", "条件宏平均 Share-L1", "越低越好"),
        ("p95_abs_share", "overall", "玩家误差 P95", "越低越好"),
        ("high_value_mae", "overall", "高贡献玩家 MAE", "越低越好"),
        ("ndcg3", "overall", "NDCG@3", "越高越好"),
    )
    extended_fig, extended_axes = plt.subplots(
        2,
        2,
        figsize=(10.0, 6.4),
        layout="constrained",
    )
    for ax, (metric_name, condition, title, direction) in zip(
        extended_axes.reshape(-1),
        extended_specs,
    ):
        for split, split_label, color, marker, line_style in split_styles:
            means = []
            lows = []
            highs = []
            for method, budget, _label in method_specs:
                row = _lookup(
                    rows,
                    metric=metric_name,
                    split=split,
                    method=method,
                    budget=budget,
                    condition=condition,
                )
                means.append(float(row["mean"]))
                lows.append(float(row["ci95_low"]))
                highs.append(float(row["ci95_high"]))
            ax.errorbar(
                range(len(method_specs)),
                means,
                yerr=[
                    [mean - low for mean, low in zip(means, lows)],
                    [high - mean for mean, high in zip(means, highs)],
                ],
                color=color,
                marker=marker,
                linestyle=line_style,
                linewidth=1.1,
                markersize=5,
                capsize=2,
                label=split_label,
            )
        ax.set_xticks(range(len(method_specs)))
        ax.set_xticklabels(
            [item[2] for item in method_specs],
            rotation=28,
            ha="right",
            fontsize=7.5,
        )
        ax.set_ylabel(f"{title}（{direction}）")
        ax.set_title(title)
    extended_axes[0, 0].legend(frameon=False, loc="upper right")
    extended_fig.suptitle(
        "扩展评价：尾部误差、条件宏平均、高贡献误差与 NDCG@3",
        fontsize=10,
    )
    _save_figure(
        extended_fig,
        args.output / "fig05_extended_metrics.png",
    )
    _save_figure(
        extended_fig,
        args.output / "fig05_extended_metrics.pdf",
    )
    plt.close(extended_fig)

    source_hash = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    (args.output / "figure_manifest.json").write_text(
        json.dumps(
            {
                "summary_source": str(summary_path),
                "summary_sha256": source_hash,
                "uncertainty": "95% game-level bootstrap CI from summary_metrics.csv",
                "palette": "Okabe-Ito subset on white",
                "language": "zh-CN",
                "font": "Microsoft YaHei",
                "status": "provisional; SQL audit coverage and inference timing remain incomplete",
                "outputs": sorted(path.name for path in args.output.iterdir()),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "source_sha256": source_hash}, indent=2))


if __name__ == "__main__":
    main()
