from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .make_figures import _save_figure


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot inference and SQL-aware costs")
    parser.add_argument("--rpv", required=True, type=Path)
    parser.add_argument("--mlp", required=True, type=Path)
    parser.add_argument("--mc", required=True, type=Path)
    parser.add_argument("--sql", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rpv = json.loads(args.rpv.read_text(encoding="utf-8"))
    mlp = json.loads(args.mlp.read_text(encoding="utf-8"))
    mc = json.loads(args.mc.read_text(encoding="utf-8"))
    sql = json.loads(args.sql.read_text(encoding="utf-8"))
    rpv32 = next(row for row in rpv if row["batch_size"] == 32)
    mlp32 = next(row for row in mlp if row["batch_size"] == 32)
    mc64 = next(row for row in mc if row["budget"] == 64)
    mc256 = next(row for row in mc if row["budget"] == 256)
    sql64 = next(row for row in sql if row["budget"] == 64)
    sql256 = next(row for row in sql if row["budget"] == 256)
    context_ms = float(sql64["median_context_prepare_ms"])

    labels = (
        "RPV-GNN\n内存效用",
        "特征 MLP\n内存效用",
        "MC-64\n内存效用",
        "MC-256\n内存效用",
        "MC-64\nSQL 效用",
        "MC-256\nSQL 效用",
    )
    values = (
        float(rpv32["median_ms_per_game"]),
        float(mlp32["median_ms_per_game"]),
        float(mc64["median_ms_per_game"]),
        float(mc256["median_ms_per_game"]),
        context_ms + 64.0 * float(sql64["median_ms_per_sql_evaluation"]),
        context_ms + 256.0 * float(sql256["median_ms_per_sql_evaluation"]),
    )
    colors = ("#009E73", "#D55E00", "#0072B2", "#0072B2", "#CC79A7", "#CC79A7")

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
    fig, ax = plt.subplots(figsize=(8.0, 3.6), layout="constrained")
    bars = ax.bar(range(len(labels)), values, color=colors, edgecolor="white")
    ax.set_yscale("log")
    ax.set_ylabel("每游戏中位耗时（毫秒，对数刻度）")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_title("推理成本比较")
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value * 1.12,
            f"{value:.1f}",
            ha="center",
            va="bottom",
            fontsize=7,
        )
    _save_figure(fig, args.output.with_suffix(".png"))
    _save_figure(fig, args.output.with_suffix(".pdf"))
    plt.close(fig)


if __name__ == "__main__":
    main()
