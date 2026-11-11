from fractions import Fraction
from pathlib import Path
from threshold_lineage import entity_witnesses, exact_shapley_from_winners, load_fixture, minimal_winning_coalitions

FIXTURE = Path(__file__).resolve().parents[2] / "P3_0" / "fixtures" / "anchor_13_players.json"


def test_winners_are_direct_and_irredundant():
    groups, witnesses = entity_witnesses(load_fixture(FIXTURE))
    h1, h2 = (minimal_winning_coalitions(groups, witnesses, t) for t in (1, 2))
    assert (len(h1), len(h2)) == (9, 4)
    for winners in (h1, h2):
        assert all(not (a < b) for a in winners for b in winners if a != b)


def test_threshold_efficiency_without_oracle_input():
    groups, witnesses = entity_witnesses(load_fixture(FIXTURE))
    h1 = exact_shapley_from_winners(13, minimal_winning_coalitions(groups, witnesses, 1))
    h2 = exact_shapley_from_winners(13, minimal_winning_coalitions(groups, witnesses, 2))
    assert sum(h1) == Fraction(1) and sum(h2) == Fraction(1)
    assert sum(x + y for x, y in zip(h1, h2)) == Fraction(2)
