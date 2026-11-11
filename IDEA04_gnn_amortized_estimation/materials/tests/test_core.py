from __future__ import annotations

import math
import unittest

from course_paper_gnn.graph import build_provenance_value_graph
from course_paper_gnn.metrics import evaluate_game, owner_shares
from course_paper_gnn.schema import GameRecord, GraphData, PlayerRecord
from course_paper_gnn.tpch import exact_shapley, g0_player_weight, utility_from_mask


def _fake_players() -> list[PlayerRecord]:
    specs = (
        ("o:1", "order", "customer:1", {"total_price": 1000.0}, {}),
        ("c:1", "customer", "customer:1", {"account_balance": 100.0}, {}),
        (
            "l:1:1",
            "lineitem",
            "supplier:10",
            {"quantity": 10.0, "extended_price": 500.0},
            {"supplier_id": "s:10", "nation_id": "n:1"},
        ),
        (
            "l:1:2",
            "lineitem",
            "supplier:11",
            {"quantity": 20.0, "extended_price": 400.0},
            {"supplier_id": "s:11", "nation_id": "n:2"},
        ),
        ("s:10", "supplier", "supplier:10", {"account_balance": 20.0}, {"nation_id": "n:1"}),
        ("s:11", "supplier", "supplier:11", {"account_balance": 30.0}, {"nation_id": "n:2"}),
        ("n:1", "nation", "nation:1", {"region_key": 1.0}, {}),
        ("n:2", "nation", "nation:2", {"region_key": 2.0}, {}),
    )
    return [
        PlayerRecord(
            player_id=player_id,
            player_index=index,
            relation=relation,
            relation_key=player_id.split(":", 1)[1],
            owner_id=owner,
            attributes=dict(attributes),
            links=dict(links),
        )
        for index, (player_id, relation, owner, attributes, links) in enumerate(specs)
    ]


def _relation_edges() -> list[dict[str, str]]:
    return [
        {"source": "o:1", "target": "c:1", "type": "order_customer"},
        {"source": "l:1:1", "target": "o:1", "type": "lineitem_order"},
        {"source": "l:1:1", "target": "s:10", "type": "lineitem_supplier"},
        {"source": "l:1:2", "target": "o:1", "type": "lineitem_order"},
        {"source": "l:1:2", "target": "s:11", "type": "lineitem_supplier"},
        {"source": "s:10", "target": "n:1", "type": "supplier_nation"},
        {"source": "s:11", "target": "n:2", "type": "supplier_nation"},
    ]


def _make_game(value_type: str = "joint") -> GameRecord:
    players = _fake_players()
    edges = _relation_edges()
    condition = {
        "source_sharing": "shared",
        "hierarchy": "cross",
        "value_function": value_type,
    }
    graph = build_provenance_value_graph(
        game_id="test_game",
        players=players,
        relation_edges=edges,
        condition=condition,
        value_type=value_type,
    )
    weights = [g0_player_weight(player) for player in players]
    base_total = sum(weights)
    base_share = [item / base_total for item in weights]
    values = [
        utility_from_mask(players, mask, value_type)
        for mask in range(1 << len(players))
    ]
    shapley = exact_shapley(values, len(players))
    target_total = sum(shapley)
    return GameRecord(
        game_id="test_game",
        source_database="synthetic",
        split="train",
        condition=condition,
        players=players,
        relation_edges=edges,
        graph=graph,
        base_share=base_share,
        shapley_share=[item / target_total for item in shapley],
        revenue_pool=1000.0,
        metadata={"n_players": len(players)},
    )


class CoreTests(unittest.TestCase):
    def test_exact_shapley_efficiency(self) -> None:
        values = [0.0, 1.0, 2.0, 4.0]
        allocation = exact_shapley(values, 2)
        self.assertAlmostEqual(sum(allocation), values[-1] - values[0], places=12)

    def test_utilities_are_monotone(self) -> None:
        players = _fake_players()
        for value_type in ("additive", "threshold", "joint"):
            values = [
                utility_from_mask(players, mask, value_type)
                for mask in range(1 << len(players))
            ]
            for mask in range(len(values)):
                for player in range(len(players)):
                    bit = 1 << player
                    if mask & bit:
                        continue
                    self.assertGreaterEqual(
                        values[mask | bit] + 1e-12,
                        values[mask],
                        msg=f"{value_type=} {mask=} {player=}",
                    )

    def test_graph_is_valid(self) -> None:
        game = _make_game()
        self.assertEqual(len(game.graph.player_node_ids), len(game.players))
        node_ids = {node.node_id for node in game.graph.nodes}
        self.assertEqual(len(node_ids), len(game.graph.nodes))
        for edge in game.graph.edges:
            self.assertIn(edge.source, node_ids)
            self.assertIn(edge.target, node_ids)
        self.assertAlmostEqual(sum(game.shapley_share), 1.0, places=10)
        self.assertAlmostEqual(sum(game.base_share), 1.0, places=10)

    def test_metrics_known_values(self) -> None:
        metric = evaluate_game(
            predicted_share=[0.6, 0.3, 0.1],
            target_share=[0.5, 0.4, 0.1],
            owners=["a", "a", "b"],
        )
        self.assertAlmostEqual(metric.share_l1, 0.1)
        self.assertAlmostEqual(metric.owner_l1, 0.0)
        self.assertAlmostEqual(metric.p95_abs_share, 0.1)
        self.assertAlmostEqual(metric.max_abs_share, 0.1)
        self.assertAlmostEqual(metric.high_value_mae, 0.1)
        self.assertAlmostEqual(metric.top3_overlap, 1.0)
        self.assertGreaterEqual(metric.ndcg3, 0.0)
        self.assertLessEqual(metric.ndcg3, 1.0)
        self.assertAlmostEqual(metric.efficiency_error, 0.0)
        aggregated = owner_shares([0.6, 0.3, 0.1], ["a", "a", "b"])
        self.assertAlmostEqual(aggregated["a"], 0.9)
        self.assertAlmostEqual(aggregated["b"], 0.1)

    def test_bootstrap_is_finite(self) -> None:
        from course_paper_gnn.metrics import bootstrap_mean_ci

        lower, upper = bootstrap_mean_ci([0.1, 0.2, 0.3], samples=200)
        self.assertTrue(math.isfinite(lower))
        self.assertTrue(math.isfinite(upper))
        self.assertLessEqual(lower, upper)

    def test_permutation_baseline_returns_valid_shares(self) -> None:
        from course_paper_gnn.baselines import permutation_shapley

        players = _fake_players()
        prediction, utility_calls = permutation_shapley(
            players,
            "joint",
            seed=42,
            nominal_steps=128,
        )
        self.assertEqual(len(prediction), len(players))
        self.assertTrue(all(item >= 0 for item in prediction))
        self.assertAlmostEqual(sum(prediction), 1.0, places=10)
        self.assertGreater(utility_calls, 0)

    def test_regression_msr_is_exact_for_additive_game(self) -> None:
        from course_paper_gnn.advanced_baselines import regression_msr_shapley

        game = _make_game("additive")
        prediction, utility_calls, nominal_evaluations, diagnostics = (
            regression_msr_shapley(
                game.players,
                "additive",
                game.base_share,
                seed=42,
                nominal_steps=128,
            )
        )
        self.assertEqual(len(prediction), len(game.players))
        self.assertAlmostEqual(sum(prediction), 1.0, places=10)
        self.assertLess(
            max(
                abs(predicted - target)
                for predicted, target in zip(
                    prediction,
                    game.shapley_share,
                )
            ),
            1e-10,
        )
        self.assertGreater(utility_calls, 0)
        self.assertGreaterEqual(nominal_evaluations, utility_calls)
        self.assertAlmostEqual(diagnostics["proxy_beta"], 1.0, places=10)

    def test_cached_mc_reuses_duplicate_coalitions(self) -> None:
        from course_paper_gnn.advanced_baselines import (
            cached_permutation_shapley,
        )

        players = _fake_players()
        prediction, utility_calls, nominal_evaluations = (
            cached_permutation_shapley(
                players,
                "joint",
                seed=42,
                nominal_steps=128,
            )
        )
        self.assertEqual(len(prediction), len(players))
        self.assertAlmostEqual(sum(prediction), 1.0, places=10)
        self.assertGreater(utility_calls, 0)
        self.assertGreater(nominal_evaluations, utility_calls)


class ModelTests(unittest.TestCase):
    def test_models_preserve_allocation_simplex(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch is not installed")
        from course_paper_gnn.data import collate_games
        from course_paper_gnn.model import build_model

        game = _make_game("joint")
        batch = collate_games([game])
        for model_name in ("feature_mlp", "rpv_gnn"):
            model = build_model(model_name, hidden_dim=16, num_layers=1)
            with torch.no_grad():
                prediction = model(batch)
            self.assertEqual(prediction.shape[0], len(game.players))
            self.assertTrue(torch.all(prediction >= 0))
            self.assertAlmostEqual(float(prediction.sum()), 1.0, places=6)
            if model_name == "rpv_gnn":
                self.assertLess(
                    float((prediction - batch.base_share).abs().max()),
                    1e-6,
                )

    def test_structural_zero_player_receives_zero(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch is not installed")
        from course_paper_gnn.data import collate_games
        from course_paper_gnn.model import build_model

        game = _make_game("joint")
        batch = collate_games([game])
        batch.structural_zero[0] = True
        model = build_model("rpv_gnn", hidden_dim=16, num_layers=1)
        with torch.no_grad():
            prediction = model(batch)
        self.assertEqual(float(prediction[0]), 0.0)
        self.assertAlmostEqual(float(prediction.sum()), 1.0, places=6)

    def test_player_permutation_equivariance(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch is not installed")
        from course_paper_gnn.data import collate_games
        from course_paper_gnn.model import build_model

        game = _make_game("joint")
        permutation = [2, 0, 7, 1, 6, 3, 5, 4]
        permuted_players = [game.players[index] for index in permutation]
        for new_index, player in enumerate(permuted_players):
            player.player_index = new_index
        player_node_map = {
            node.node_id: node for node in game.graph.nodes if node.node_type == "player"
        }
        other_nodes = [
            node for node in game.graph.nodes if node.node_type != "player"
        ]
        permuted_graph = GraphData(
            nodes=[
                player_node_map[player.player_id] for player in permuted_players
            ]
            + other_nodes,
            edges=list(game.graph.edges),
            player_node_ids=[player.player_id for player in permuted_players],
            value_descriptor=list(game.graph.value_descriptor),
        )
        permuted_game = GameRecord(
            game_id=game.game_id + "_permuted",
            source_database=game.source_database,
            split=game.split,
            condition=dict(game.condition),
            players=permuted_players,
            relation_edges=list(game.relation_edges),
            graph=permuted_graph,
            base_share=[game.base_share[index] for index in permutation],
            shapley_share=[game.shapley_share[index] for index in permutation],
            revenue_pool=game.revenue_pool,
            metadata=dict(game.metadata),
        )
        model = build_model("rpv_gnn", hidden_dim=16, num_layers=1)
        model.eval()
        with torch.no_grad():
            original = model(collate_games([game]))
            reordered = model(collate_games([permuted_game]))
        self.assertLess(float((reordered - original[permutation]).abs().max()), 1e-6)


if __name__ == "__main__":
    unittest.main()
