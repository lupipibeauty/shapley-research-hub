from __future__ import annotations

from aggregate_report_shapley.rapid_gap import (
    coalition_values,
    exact_shapley,
    exact_treewidth,
    make_instance,
    primal_graph,
    shapley_variable_elimination,
)


def test_exact_treewidth_known_graphs() -> None:
    clique4 = {i: {j for j in range(4) if j != i} for i in range(4)}
    cycle4 = {0: {1, 3}, 1: {0, 2}, 2: {1, 3}, 3: {0, 2}}
    assert exact_treewidth(clique4) == 3
    assert exact_treewidth(cycle4) == 2


def test_rapid_gap_aligned_exact_shapley() -> None:
    instance = make_instance("ALIGNED", 12)
    graph = primal_graph(instance.n, instance.source_scopes + instance.value_scopes)
    assert exact_treewidth(graph) == 3
    values = coalition_values(instance)
    truth = exact_shapley(values, instance.n)
    estimate, _ = shapley_variable_elimination(instance)
    assert values[0] == 0.0
    assert abs(values[-1] - 1000.0) < 1e-12
    assert max(abs(a - b) for a, b in zip(truth, estimate, strict=True)) < 1e-9
