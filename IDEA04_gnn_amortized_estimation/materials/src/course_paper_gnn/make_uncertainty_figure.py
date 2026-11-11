from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .make_figures import _save_figure


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot seed-ensemble uncertainty diagnostics")
    parser.add_argument("--full-summary", required=True, type=Path)
    parser.add_argument("--safe-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite figure: {args.output}")
    full = json.loads(args.full_summary.read_text(encoding="utf-8"))
    safe = json.loads(args.safe_summary.read_text(encoding="utf-8"))
    splits = ("in_distribution", "ood", "scale_ood")
    labels = ("分布内", "组合分布外", "SF1 规模外推")
    full_by_split = {row["split"]: row for row in full}
    safe_by_split = {row["split"]: row for row in safe}

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
            "pdf.fonttype": 42,
        }
    )
    fig, axes = plt.subplots(1, 3, figsize=(9.2, 3.0), layout="constrained")
    methods = (
        ("RPV-GNN", full_by_split, "#009E73", "D", "-"),
        ("安全路由", safe_by_split, "#56B4E9", "o", "--"),
    )
    panels = (
        (
            "uncertainty_error_spearman",
            "种子分歧与误差的 Spearman 相关",
            "相关系数（越高越好）",
        ),
        (
            "interval_coverage_95",
            "95% 种子区间覆盖率",
            "覆盖率（越接近 0.95 越好）",
        ),
        (
            "high_uncertainty_quartile_mae",
            "高不确定性组 MAE",
            "MAE（越低越好）",
        ),
    )
    for ax, (field, title, ylabel) in zip(axes, panels):
        for label, values, color, marker, line_style in methods:
            y = [float(values[split][field]) for split in splits]
            ax.plot(
                range(len(splits)),
                y,
                color=color,
                marker=marker,
                linestyle=line_style,
                label=label,
            )
        ax.set_xticks(range(len(splits)))
        ax.set_xticklabels(labels, rotation=20, ha="right")
        ax.set_title(title)
        ax.set_ylabel(ylabel)
    axes[0].legend(frameon=False)
    fig.suptitle("多种子不确定性诊断", fontsize=10)
    _save_figure(fig, args.output.with_suffix(".png"))
    _save_figure(fig, args.output.with_suffix(".pdf"))
    plt.close(fig)


if __name__ == "__main__":
    main()
