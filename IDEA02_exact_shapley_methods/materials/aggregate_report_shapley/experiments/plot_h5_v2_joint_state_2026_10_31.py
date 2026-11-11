from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "v4_0" / "H5_V2_JOINT_STATE_2026_10_31"
FIG = OUT / "figures"


def choose_chinese_font() -> str:
    available = {font.name for font in fm.fontManager.ttflist}
    for candidate in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"):
        if candidate in available:
            return candidate
    raise RuntimeError("未找到可用的中文字体")


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(OUT / "family_state_growth.csv")
    additive = data[data["score_mode"] == "additive"].sort_values("family_count")
    geometric = data[data["score_mode"] == "geometric"].sort_values("family_count")
    font = choose_chinese_font()
    with plt.rc_context(
        {
            "font.family": font,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
        }
    ):
        fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.2), layout="constrained")
        x = additive["family_count"].to_numpy()
        axes[0].plot(
            x,
            additive["observed_distinct_projected_states"],
            color="#0072B2",
            marker="o",
            linewidth=2,
            label="可达联合状态",
        )
        axes[0].plot(
            x,
            additive["observed_distinct_game_values"],
            color="#009E73",
            marker="s",
            linestyle="--",
            linewidth=1.8,
            label="可加评分值",
        )
        axes[0].plot(
            x,
            geometric["observed_distinct_game_values"],
            color="#D55E00",
            marker="^",
            linestyle=":",
            linewidth=2,
            label="几何联合评分值",
        )
        axes[0].axhline(4096, color="#333333", linewidth=1, linestyle="-.", label="全部联盟 4096")
        axes[0].set(
            xticks=x,
            xlabel="统计族数",
            ylabel="不同状态/值的数量",
            title="(a) 联合状态与评分值增长",
        )
        axes[0].grid(axis="y", alpha=0.25)
        axes[0].legend(frameon=False, fontsize=8)

        axes[1].plot(
            x,
            additive["B2_intermediate_state_visits"],
            color="#CC79A7",
            marker="o",
            linewidth=2,
            label="中间状态访问",
        )
        axes[1].plot(
            x,
            additive["B2_transition_writes"],
            color="#E69F00",
            marker="s",
            linestyle="--",
            linewidth=1.8,
            label="状态转移写入",
        )
        axes[1].plot(
            x,
            additive["B2_terminal_state_visits_all_focals"],
            color="#56B4E9",
            marker="^",
            linestyle=":",
            linewidth=2,
            label="12个焦点的终端状态",
        )
        axes[1].set(
            xticks=x,
            xlabel="统计族数",
            ylabel="累计计数",
            title="(b) B2 充分状态 DP 实际工作量",
        )
        axes[1].grid(axis="y", alpha=0.25)
        axes[1].legend(frameon=False, fontsize=8)
        fig.suptitle("D1-P 统计族联合状态增长（固定12玩家）", fontsize=13)

        outputs = []
        for suffix in ("png", "svg"):
            path = FIG / f"h5_family_joint_state_growth.{suffix}"
            fig.savefig(path, dpi=300, facecolor="white")
            outputs.append(str(path.relative_to(ROOT)))
        plt.close(fig)

    manifest = {
        "figure": "H5统计族联合状态增长",
        "source_data": str((OUT / "family_state_growth.csv").relative_to(ROOT)),
        "transformations": ["按family_count排序", "展示原始确定性计数", "无平滑、无置信区间"],
        "font": font,
        "outputs": outputs,
        "caption": "图H5-1：在玩家、SQL与满表参考均固定时，从P族逐步增加到P/E/J/M四族。左图给出实际可达联合状态和不同评分值数；右图给出B2充分状态DP的实际状态访问与转移写入。数据为确定性完整计算，不应添加抽样置信区间。",
    }
    (FIG / "figure_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
