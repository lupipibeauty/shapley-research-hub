from fractions import Fraction
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from study import (ReducedADD, VALUE_NAMES, build_threshold2_game, exhaustive_values,
                   historical_g1_redundancy, shapley_from_values, study_components,
                   component_value, study_value, threshold_witness_examples)


def test_threshold2_is_non_degenerate():
    game = build_threshold2_game()
    assert game.n == 12
    assert len(threshold_witness_examples(game)) == 4
    assert any(study_value(game, mask, "GR") != study_value(game, mask, "GL") for mask in range(1 << game.n))
    assert any(study_value(game, mask, "GL") != study_value(game, mask, "GC") for mask in range(1 << game.n))


def test_boolean_decomposition():
    game = build_threshold2_game()
    for name in VALUE_NAMES:
        components = study_components(game, name)
        for mask in range(1 << game.n):
            assert component_value(components, mask) == study_value(game, mask, name)


def test_add_exact_shapley():
    game = build_threshold2_game()
    values = exhaustive_values(game, "GC")
    add = ReducedADD(game.n, lambda mask: values[mask])
    assert add.shapley() == shapley_from_values(values, game.n)

