from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _box(
    ax: plt.Axes,
    xy: tuple[float, float],
    width: float,
    height: float,
    title: str,
    body: str,
    color: str,
) -> tuple[float, float, float, float]:
    x, y = xy
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.015,rounding_size=0.02",
        linewidth=1.1,
        edgecolor=color,
        facecolor="white",
        zorder=2,
    )
    ax.add_patch(patch)
    ax.text(
        x + width / 2,
        y + height * 0.67,
        title,
        ha="center",
        va="center",
        fontsize=10.5,
        fontweight="bold",
        color="#111111",
        zorder=3,
    )
    ax.text(
        x + width / 2,
        y + height * 0.30,
        body,
        ha="center",
        va="center",
        fontsize=8.6,
        color="#333333",
        linespacing=1.25,
        zorder=3,
    )
    return (x, y, width, height)


def _arrow(
    ax: plt.Axes,
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> None:
    start = (left[0] + left[2], left[1] + left[3] / 2)
    end = (right[0], right[1] + right[3] / 2)
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.2,
            color="#555555",
            zorder=1,
        )
    )


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite: {args.output}")
    args.output.mkdir(parents=True)
    plt.rcParams.update(
        {
            "font.family": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )

    fig = plt.figure(figsize=(12.2, 6.2), layout="constrained")
    grid = fig.add_gridspec(2, 1, height_ratios=[1.45, 1.0])
    pipeline_ax = fig.add_subplot(grid[0])
    theory_ax = fig.add_subplot(grid[1])
    for ax in (pipeline_ax, theory_ax):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

    colors = (
        "#0072B2",
        "#009E73",
        "#CC79A7",
        "#D55E00",
        "#56B4E9",
        "#E69F00",
    )
    boxes = [
        _box(
            pipeline_ax,
            (0.01, 0.34),
            0.135,
            0.39,
            "数据库与查询",
            "数据库实例 D\n报表查询 Q\n整表价值 v(S)",
            colors[0],
        ),
        _box(
            pipeline_ax,
            (0.175, 0.34),
            0.135,
            0.39,
            "数据玩家",
            "物理事实或事实包\n玩家集合 N\nowner 事后汇总",
            colors[1],
        ),
        _box(
            pipeline_ax,
            (0.34, 0.34),
            0.175,
            0.39,
            "来源—价值异构图",
            "玩家 | 见证 | 坐标\n价值因子 | 最终报表",
            colors[2],
        ),
        _box(
            pipeline_ax,
            (0.545, 0.34),
            0.135,
            0.39,
            "RPV-GNN",
            "类型嵌入\n关系消息传递\n玩家级残差",
            colors[3],
        ),
        _box(
            pipeline_ax,
            (0.71, 0.34),
            0.135,
            0.39,
            "安全约束",
            "可加解析锚点\n结构可达性遮罩",
            colors[4],
        ),
        _box(
            pipeline_ax,
            (0.875, 0.34),
            0.115,
            0.39,
            "混合输出",
            "安全路由\nShapley 份额\n收益分配",
            colors[5],
        ),
    ]
    for left, right in zip(boxes, boxes[1:]):
        _arrow(pipeline_ax, left, right)

    pipeline_ax.text(
        0.01,
        0.88,
        "研究流程：从数据库收益分配问题到关系图上的贡献估计",
        fontsize=12,
        fontweight="bold",
        ha="left",
        va="center",
    )
    pipeline_ax.text(
        0.01,
        0.16,
        "对照实验在相同数据库、玩家绑定、联盟价值和测试切分下比较解析基线、特征模型、图模型和采样预算。",
        fontsize=8.8,
        color="#555555",
        ha="left",
        va="center",
    )

    theory_ax.text(
        0.01,
        0.91,
        "理论与设计关系",
        fontsize=12,
        fontweight="bold",
        ha="left",
        va="center",
    )
    theory_boxes = [
        _box(
            theory_ax,
            (0.01, 0.18),
            0.22,
            0.52,
            "残差分解",
            "v = v_add + v_res\nφ(v) = φ(v_add) + φ(v_res)",
            "#0072B2",
        ),
        _box(
            theory_ax,
            (0.26, 0.18),
            0.22,
            0.52,
            "可加精确性",
            "v 为可加价值\n安全路由输出 = 解析份额",
            "#009E73",
        ),
        _box(
            theory_ax,
            (0.51, 0.18),
            0.22,
            0.52,
            "结构零支付",
            "玩家无法到达报表\n贡献支付严格为 0",
            "#D55E00",
        ),
        _box(
            theory_ax,
            (0.76, 0.18),
            0.23,
            0.52,
            "评价单位",
            "一个完整游戏为独立样本\n三种子先在游戏内平均",
            "#CC79A7",
        ),
    ]
    for left, right in zip(theory_boxes, theory_boxes[1:]):
        _arrow(theory_ax, left, right)

    for stem in ("fig01_research_framework",):
        fig.savefig(
            args.output / f"{stem}.png",
            dpi=600,
            facecolor="white",
            transparent=False,
            bbox_inches=None,
        )
        fig.savefig(
            args.output / f"{stem}.pdf",
            dpi=600,
            facecolor="white",
            transparent=False,
            bbox_inches=None,
        )
        from PIL import Image

        target = args.output / f"{stem}.png"
        with Image.open(target) as image:
            image.convert("RGB").save(target, format="PNG", dpi=(600, 600))
    plt.close(fig)


if __name__ == "__main__":
    main()
