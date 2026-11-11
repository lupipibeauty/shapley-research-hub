from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib as mpl
mpl.use("Agg", force=True)
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import t


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "v4_0" / "R2_3"
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

METHODS = [
    "A_OFFICIAL_CODE_DERIVED",
    "B_PAPER_FORMULA_CONSISTENT",
    "C_COMPLETE_PERMUTATION_MC",
]
LABELS = {
    METHODS[0]: "A 官方代码派生版",
    METHODS[1]: "B 论文公式一致版",
    METHODS[2]: "C 完整排列 MC",
}
COLORS = {
    METHODS[0]: "#D55E00",
    METHODS[1]: "#0072B2",
    METHODS[2]: "#009E73",
}
MARKERS = {METHODS[0]: "o", METHODS[1]: "s", METHODS[2]: "^"}
LINESTYLES = {METHODS[0]: "-", METHODS[1]: "--", METHODS[2]: "-."}
VALUE_LABELS = {"V_count": "V-count", "V1": "V1", "V2_lambda_0_5": "V2（λ=0.5）"}


def choose_chinese_font() -> str:
    available = {font.name for font in fm.fontManager.ttflist}
    for candidate in (
        "Microsoft YaHei",
        "Microsoft JhengHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Source Han Sans CN",
    ):
        if candidate in available:
            return candidate
    raise RuntimeError("No installed Chinese font found; refusing to emit missing glyphs")


def save_all(fig: mpl.figure.Figure, stem: str) -> list[str]:
    outputs = []
    for suffix in ("png", "svg", "pdf"):
        path = FIG / f"{stem}.{suffix}"
        fig.savefig(path, dpi=300 if suffix == "png" else None, facecolor="white")
        outputs.append(str(path.relative_to(ROOT)))
    plt.close(fig)
    return outputs


def mean_ci(frame: pd.DataFrame, column: str, keys: list[str]) -> pd.DataFrame:
    rows = []
    for key, group in frame.groupby(keys, sort=True):
        values = group[column].to_numpy(dtype=float)
        mean = float(values.mean())
        half = float(t.ppf(0.975, len(values) - 1)) * float(values.std(ddof=1)) / np.sqrt(
            len(values)
        )
        rows.append({**dict(zip(keys, key if isinstance(key, tuple) else (key,))), "mean": mean, "low": max(0.0, mean - half), "high": mean + half})
    return pd.DataFrame(rows)


def plot_overall(raw: pd.DataFrame) -> list[str]:
    summary = mean_ci(
        raw,
        "total_l1_error",
        ["method", "value", "owner_map", "nominal_budget"],
    )
    fig, axes = plt.subplots(2, 3, figsize=(13.2, 7.6), layout="constrained", sharex=True)
    for row, owner_map in enumerate(("G-equal", "G-skew")):
        for column, value in enumerate(("V_count", "V1", "V2_lambda_0_5")):
            ax = axes[row, column]
            subset = summary[(summary.owner_map == owner_map) & (summary.value == value)]
            for method in METHODS:
                data = subset[subset.method == method].sort_values("nominal_budget")
                x = data.nominal_budget.to_numpy()
                y = data["mean"].to_numpy()
                ax.plot(
                    x,
                    y,
                    color=COLORS[method],
                    marker=MARKERS[method],
                    linestyle=LINESTYLES[method],
                    linewidth=1.8,
                    markersize=5,
                    label=LABELS[method],
                )
                ax.fill_between(x, data.low, data.high, color=COLORS[method], alpha=0.13)
            ax.axhline(0, color="#333333", linewidth=0.8, label="D 精确真值（误差0）")
            ax.set_yscale("symlog", linthresh=0.1)
            ax.margins(y=0.14)
            ax.grid(True, which="major", color="#D9D9D9", linewidth=0.6)
            ax.set_title(f"{owner_map} · {VALUE_LABELS[value]}")
            if row == 1:
                ax.set_xlabel("名义效用调用预算")
            if column == 0:
                ax.set_ylabel("三位 owner 总 L1 误差（95% t 区间）")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside upper center", ncol=4, frameon=False)
    return save_all(fig, "r2_3_overall_convergence")


def plot_owner_curves(summary: pd.DataFrame, owner_map: str) -> list[str]:
    fig, axes = plt.subplots(3, 3, figsize=(13.2, 10.2), layout="constrained", sharex=True)
    owners = ["A", "B", "C"]
    values = ["V_count", "V1", "V2_lambda_0_5"]
    for row, owner in enumerate(owners):
        for column, value in enumerate(values):
            ax = axes[row, column]
            subset = summary[
                (summary.owner_map == owner_map)
                & (summary.owner == owner)
                & (summary.value == value)
            ]
            for method in METHODS:
                data = subset[subset.method == method].sort_values("nominal_budget")
                x = data.nominal_budget.to_numpy()
                y = data.mean_absolute_error.to_numpy()
                low = data.mae_ci95_low.to_numpy()
                high = data.mae_ci95_high.to_numpy()
                ax.plot(
                    x,
                    y,
                    color=COLORS[method],
                    marker=MARKERS[method],
                    linestyle=LINESTYLES[method],
                    linewidth=1.6,
                    markersize=4.5,
                    label=LABELS[method],
                )
                ax.fill_between(x, low, high, color=COLORS[method], alpha=0.13)
            ax.axhline(0, color="#333333", linewidth=0.8, label="D 精确真值（误差0）")
            ax.set_yscale("symlog", linthresh=0.1)
            ax.margins(y=0.14)
            ax.grid(True, which="major", color="#D9D9D9", linewidth=0.6)
            ax.set_title(f"{owner_map} · owner {owner} · {VALUE_LABELS[value]}")
            if row == 2:
                ax.set_xlabel("名义效用调用预算")
            if column == 0:
                ax.set_ylabel("平均绝对误差（95% t 区间）")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside upper center", ncol=4, frameon=False)
    return save_all(fig, f"r2_3_owner_convergence_{owner_map.lower()}")


def plot_bias_random(summary: pd.DataFrame) -> list[str]:
    data = summary[summary.nominal_budget == 5000].copy()
    fig, axes = plt.subplots(2, 3, figsize=(13.2, 7.6), layout="constrained")
    for row, owner_map in enumerate(("G-equal", "G-skew")):
        for column, value in enumerate(("V_count", "V1", "V2_lambda_0_5")):
            ax = axes[row, column]
            subset = data[(data.owner_map == owner_map) & (data.value == value)]
            for method in METHODS:
                points = subset[subset.method == method]
                ax.scatter(
                    points.systematic_bias_mean_signed_error.abs(),
                    points.random_error_sd_across_seeds,
                    color=COLORS[method],
                    marker=MARKERS[method],
                    s=45,
                    label=LABELS[method],
                )
                owner_offsets = {"A": (5, -12), "B": (5, 2), "C": (5, 16)}
                for _, point in points.iterrows():
                    ax.annotate(
                        str(point.owner),
                        (
                            abs(point.systematic_bias_mean_signed_error),
                            point.random_error_sd_across_seeds,
                        ),
                        xytext=owner_offsets[str(point.owner)],
                        textcoords="offset points",
                        fontsize=8,
                    )
            ax.set_xscale("symlog", linthresh=0.1)
            ax.set_yscale("symlog", linthresh=0.1)
            ax.margins(x=0.12, y=0.16)
            ax.grid(True, which="major", color="#D9D9D9", linewidth=0.6)
            ax.set_title(f"{owner_map} · {VALUE_LABELS[value]}")
            if row == 1:
                ax.set_xlabel("系统性偏差绝对值 |平均有符号误差|")
            if column == 0:
                ax.set_ylabel("随机误差：跨种子标准差")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside upper center", ncol=3, frameon=False)
    return save_all(fig, "r2_3_bias_vs_random")


def main() -> None:
    font = choose_chinese_font()
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [font, "DejaVu Sans"],
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "font.size": 10,
            "axes.titlesize": 11,
        }
    )
    raw = pd.read_csv(OUT / "raw_runs.csv")
    summary = pd.read_csv(OUT / "owner_error_summary.csv")
    expected_raw = 2160
    expected_summary = 216
    if len(raw) != expected_raw or len(summary) != expected_summary:
        raise ValueError(f"Unexpected input rows: raw={len(raw)}, summary={len(summary)}")
    if raw.isna().any().any() or summary.isna().any().any():
        # Empty details fields in raw are intentional; numerical inputs are checked separately.
        numeric_summary = summary.select_dtypes(include=[np.number])
        if numeric_summary.isna().any().any():
            raise ValueError("Missing numerical values in figure source data")

    files = []
    files.extend(plot_overall(raw))
    files.extend(plot_owner_curves(summary, "G-equal"))
    files.extend(plot_owner_curves(summary, "G-skew"))
    files.extend(plot_bias_random(summary))
    manifest = {
        "status": "generated_from_real_r2_3_outputs",
        "font": font,
        "source_files": [
            "outputs/v4_0/R2_3/raw_runs.csv",
            "outputs/v4_0/R2_3/owner_error_summary.csv",
        ],
        "uncertainty": "95% t confidence interval across 30 independent random seeds",
        "transformations": [
            "arithmetic mean across seeds",
            "symlog display scale with linear threshold 0.1",
            "no smoothing or interpolation",
        ],
        "missing_data": "none in numerical figure inputs",
        "outputs": files,
        "matplotlib": mpl.__version__,
    }
    (FIG / "figure_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
