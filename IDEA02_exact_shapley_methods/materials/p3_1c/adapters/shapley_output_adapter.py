"""将官方 LExaShap 暴露的梯度向量转换为标准 Shapley 标量。"""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def scalarize(circuit, full_player_space: Iterable[str] | None = None) -> tuple[dict[str, float], dict]:
    """使用源码的按联盟大小梯度口径：dot(grad, prob) * 2^n / n!。

    full_player_space 仅用于显式补回未出现在 Boolean 函数中的 dummy 玩家；
    不改变官方电路的变量集合或归一化。
    """
    n_active = len(circuit.var_dict)
    scale = (2**n_active) / math.factorial(n_active)
    result: dict[str, float] = {}
    raw = {}
    for label, grad in circuit.banzhaf_values:
        prob = circuit.var_dict[label].prob
        scalar = float(np.dot(grad, prob) * scale)
        result[str(label)] = scalar
        raw[str(label)] = {
            "gradient": [float(x) for x in grad],
            "probability_vector": [float(x) for x in prob],
            "active_variable_count": n_active,
            "normalization_scale": scale,
            "scalar": scalar,
        }
    if full_player_space is not None:
        result = {str(player): result.get(str(player), 0.0) for player in full_player_space}
    return result, raw
