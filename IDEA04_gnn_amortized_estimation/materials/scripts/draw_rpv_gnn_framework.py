from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.font_manager import FontProperties


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "paper_template" / "latex_template" / "figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FONT_PATH = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT = FontProperties(fname=str(FONT_PATH))
FONT_BOLD = FontProperties(fname=str(Path(r"C:\Windows\Fonts\msyhbd.ttc")))

mpl.rcParams.update(
    {
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "axes.unicode_minus": False,
    }
)


def box(ax, xy, width, height, text, *, face, edge="#334155", bold=False, size=8.2):
    x, y = xy
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.05,
        edgecolor=edge,
        facecolor=face,
        zorder=2,
    )
    ax.add_patch(patch)
    ax.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center",
        va="center",
        fontproperties=FONT_BOLD if bold else FONT,
        fontsize=size,
        color="#172033",
        linespacing=1.28,
        zorder=3,
    )
    return patch


def arrow(ax, start, end, *, color="#475569", style="-"):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=10,
        linewidth=1.05,
        linestyle=style,
        color=color,
        shrinkA=2,
        shrinkB=2,
        zorder=1,
    )
    ax.add_patch(patch)


fig, ax = plt.subplots(figsize=(180 / 25.4, 100 / 25.4), layout="constrained")
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")
fig.patch.set_facecolor("white")

# Main structural path.
box(ax, (0.02, 0.67), 0.13, 0.17, "数据库实例、查询\n与来源依赖", face="#E8F1FA", bold=True)
box(ax, (0.19, 0.67), 0.15, 0.17, "来源—价值\n异构图", face="#DCEBFA", bold=True)
box(ax, (0.38, 0.67), 0.16, 0.17, "类型/子类型嵌入\n数值特征投影", face="#E8F1FA")
box(ax, (0.58, 0.67), 0.17, 0.17, "关系类型感知\n消息传递", face="#DDEFE8", bold=True)
box(ax, (0.79, 0.67), 0.18, 0.17, "玩家表示 $h_i$\n注意力图表示 $g$", face="#DDEFE8")

for x1, x2 in [(0.15, 0.19), (0.34, 0.38), (0.54, 0.58), (0.75, 0.79)]:
    arrow(ax, (x1, 0.755), (x2, 0.755))

# Auxiliary inputs and fusion.
box(ax, (0.05, 0.34), 0.16, 0.15, "价值条件描述符 $d$\n价值嵌入 $z$", face="#FFF1D6")
box(ax, (0.27, 0.34), 0.16, 0.15, "可加价值分量\n解析基础份额 $b_i$", face="#FFF1D6")
box(ax, (0.49, 0.32), 0.18, 0.19, "贡献残差头\n$[h_i;g;z;b_i]$", face="#FCE4EC", bold=True)
box(ax, (0.73, 0.32), 0.20, 0.19, "解析锚定 logits\n结构零遮罩\n图内 softmax", face="#FCE4EC", bold=True)

arrow(ax, (0.13, 0.49), (0.49, 0.415))
arrow(ax, (0.43, 0.415), (0.49, 0.415))
arrow(ax, (0.88, 0.67), (0.62, 0.51))
arrow(ax, (0.67, 0.415), (0.73, 0.415))

# Safe route and output.
box(ax, (0.27, 0.07), 0.16, 0.13, "价值类型条件", face="#F1F5F9")
box(ax, (0.51, 0.05), 0.19, 0.17, "安全路由\n可加：返回 $b$\n非可加：返回 $\hat y$", face="#E6E0F8", bold=True)
box(ax, (0.78, 0.07), 0.17, 0.13, "玩家贡献份额\n" + r"$\hat{\mathbf{y}}^{\mathrm{safe}}$", face="#DFF3E4", bold=True)

arrow(ax, (0.35, 0.20), (0.55, 0.22))
arrow(ax, (0.83, 0.32), (0.66, 0.22))
arrow(ax, (0.70, 0.135), (0.78, 0.135))

ax.text(
    0.02,
    0.95,
    "结构表示路径",
    fontproperties=FONT_BOLD,
    fontsize=9.2,
    color="#1D4E89",
)
ax.text(
    0.02,
    0.56,
    "解析信息与约束路径",
    fontproperties=FONT_BOLD,
    fontsize=9.2,
    color="#8A4B08",
)

for suffix in ("pdf", "svg", "png"):
    destination = OUTPUT_DIR / f"rpv_gnn_framework.{suffix}"
    fig.savefig(destination, dpi=400, facecolor="white", bbox_inches=None)

plt.close(fig)
