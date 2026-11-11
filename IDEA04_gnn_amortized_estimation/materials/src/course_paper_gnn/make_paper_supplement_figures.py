from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


BLUE = "#0072B2"
GREEN = "#009E73"
PINK = "#CC79A7"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build evidence-focused supplementary figures for the course paper"
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def save_figure(fig: plt.Figure, output: Path, stem: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for suffix in ("pdf", "png"):
        fig.savefig(
            output / f"{stem}.{suffix}",
            dpi=600,
            facecolor="white",
            transparent=False,
        )


def lookup_accuracy(summary_path: Path) -> dict[str, tuple[float, float, float]]:
    wanted = {
        ("rpv_gnn_safe_route", 0): "安全路由（模型路径）",
        ("cached_permutation_mc", 64): "MC-64",
        ("cached_permutation_mc", 256): "MC-256",
        ("cached_permutation_mc", 1024): "MC-1024",
    }
    result: dict[str, tuple[float, float, float]] = {}
    with summary_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row["method"], int(row["budget"]))
            if (
                key in wanted
                and row["split"] == "in_distribution"
                and row["condition"] == "overall"
                and row["metric"] == "share_l1"
            ):
                result[wanted[key]] = (
                    float(row["mean"]),
                    float(row["ci95_low"]),
                    float(row["ci95_high"]),
                )
    missing = set(wanted.values()) - set(result)
    if missing:
        raise KeyError(f"Missing accuracy rows: {sorted(missing)}")
    return result


def lookup_runtime(runtime_path: Path) -> dict[str, float]:
    payload = json.loads(runtime_path.read_text(encoding="utf-8"))
    stage_to_label = {
        "model_end_to_end": "安全路由（模型路径）",
        "mc_64_end_to_end": "MC-64",
        "mc_256_end_to_end": "MC-256",
        "mc_1024_end_to_end": "MC-1024",
    }
    result = {
        stage_to_label[item["stage"]]: float(item["median_ms"])
        for item in payload["stages"]
        if item["stage"] in stage_to_label
    }
    missing = set(stage_to_label.values()) - set(result)
    if missing:
        raise KeyError(f"Missing runtime stages: {sorted(missing)}")
    return result


def make_pareto(root: Path, output: Path) -> None:
    accuracy = lookup_accuracy(root / "runs/final_summary_v8/summary_metrics.csv")
    runtime = lookup_runtime(
        root / "runs/benchmark_end_to_end_ind_g10_final_20261108/summary.json"
    )
    styles = {
        "安全路由（模型路径）": (GREEN, "D"),
        "MC-64": (PINK, "o"),
        "MC-256": (PINK, "s"),
        "MC-1024": (PINK, "^")
    }

    fig, ax = plt.subplots(figsize=(5.7, 3.8), layout="constrained")
    for label in ("安全路由（模型路径）", "MC-64", "MC-256", "MC-1024"):
        mean, low, high = accuracy[label]
        color, marker = styles[label]
        ax.errorbar(
            runtime[label],
            mean,
            yerr=[[mean - low], [high - mean]],
            fmt=marker,
            color=color,
            markerfacecolor=color,
            markeredgecolor="white",
            markeredgewidth=0.8,
            markersize=7,
            capsize=3,
            linewidth=1.2,
            label=label,
            zorder=3,
        )
        ax.annotate(
            label,
            (runtime[label], mean),
            xytext=(5, 6 if label != "MC-1024" else -14),
            textcoords="offset points",
            fontsize=8,
        )

    ax.plot(
        [runtime["安全路由（模型路径）"], runtime["MC-256"], runtime["MC-1024"]],
        [accuracy["安全路由（模型路径）"][0], accuracy["MC-256"][0], accuracy["MC-1024"][0]],
        color="#666666",
        linewidth=0.9,
        linestyle="--",
        zorder=1,
        label="经验 Pareto 前沿",
    )
    ax.set_xscale("log")
    ax.set_xlabel("每游戏端到端中位耗时（ms，对数刻度）")
    ax.set_ylabel("玩家份额 L1 误差（越低越好）")
    ax.set_title("分布内测试的精度—成本权衡")
    ax.grid(True, which="both", alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    save_figure(fig, output, "fig08_accuracy_cost_pareto")
    plt.close(fig)


def align_histories(histories: list[list[dict]], key: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    common_epochs = sorted(set.intersection(*(set(item["epoch"] for item in run) for run in histories)))
    values = []
    for run in histories:
        index = {item["epoch"]: float(item[key]) for item in run}
        values.append([index[epoch] for epoch in common_epochs])
    array = np.asarray(values, dtype=float)
    return np.asarray(common_epochs), array.mean(axis=0), array.std(axis=0, ddof=1)


def make_learning_curves(root: Path, output: Path) -> None:
    seeds = (20261107, 20261108, 20261109)
    histories = [
        read_jsonl(root / f"runs/final_rpv_v2_seed{seed}/history.jsonl")
        for seed in seeds
    ]
    epochs, train_mean, train_sd = align_histories(histories, "train_loss")
    _, val_mean, val_sd = align_histories(histories, "validation_share_l1")

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.3), layout="constrained")
    panels = (
        (axes[0], train_mean, train_sd, BLUE, "训练目标", "训练损失"),
        (axes[1], val_mean, val_sd, GREEN, "验证指标", "验证集 Share-L1"),
    )
    for ax, mean, sd, color, title, ylabel in panels:
        ax.plot(epochs, mean, color=color, marker="o", markersize=3, linewidth=1.5)
        ax.fill_between(epochs, mean - sd, mean + sd, color=color, alpha=0.18, linewidth=0)
        ax.set_xlabel("训练轮次")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)

    best_index = int(np.argmin(val_mean))
    axes[1].scatter(
        [epochs[best_index]], [val_mean[best_index]], color="#D55E00", marker="*", s=85, zorder=4
    )
    axes[1].annotate(
        f"三种子均值最低：第 {int(epochs[best_index])} 轮",
        (epochs[best_index], val_mean[best_index]),
        xytext=(-88, -24),
        textcoords="offset points",
        fontsize=7.5,
        arrowprops={"arrowstyle": "->", "color": "#555555", "lw": 0.8},
    )
    fig.suptitle("RPV-GNN 训练与验证学习曲线（三模型种子，阴影为 ±1 SD）", fontsize=10)
    save_figure(fig, output, "fig09_learning_curves")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    plt.rcParams.update(
        {
            "font.family": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "font.size": 8.5,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )
    make_pareto(args.root, args.output)
    make_learning_curves(args.root, args.output)
    manifest = {
        "status": "paper_outline_support",
        "source_note": "Generated only from frozen local result tables and training logs; no values were invented.",
        "outputs": [
            "fig08_accuracy_cost_pareto.pdf",
            "fig08_accuracy_cost_pareto.png",
            "fig09_learning_curves.pdf",
            "fig09_learning_curves.png",
        ],
    }
    (args.output / "figure_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
