from fractions import Fraction
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joint_game import build_game, component_value, exact_shapley, report_python, value, value_components


def test_frozen_sizes_and_full_reports():
    assert build_game("F0_EBH").n == 10
    assert build_game("F1_SITE_LINK", "balanced").n == 16
    assert build_game("F2_ENTITY_LINK", "balanced").n == 14
    for version, distribution in (("F0_EBH", "base"), ("F1_SITE_LINK", "balanced"), ("F2_ENTITY_LINK", "balanced")):
        game = build_game(version, distribution)
        report = report_python(game, (1 << game.n) - 1)
        assert report[("NAT", "workers")] > 0
        assert len(report) == 35


def test_exact_boolean_decomposition_for_every_coalition():
    for version, distribution in (("F0_EBH", "base"), ("F2_ENTITY_LINK", "balanced")):
        game = build_game(version, distribution)
        for name in ("G0", "G1", "G2"):
            components = value_components(game, name)
            for mask in range(1 << game.n):
                assert component_value(components, mask) == value(game, mask, name)


def test_efficiency_and_negative_service_contribution():
    game = build_game("F0_EBH")
    allocation, _ = exact_shapley(game, "G1")
    assert sum(allocation) == value(game, (1 << game.n) - 1, "G1")
    service = next(player.index for player in game.players if player.player_id == "H:S2")
    assert allocation[service] < Fraction(0)
