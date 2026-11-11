from fractions import Fraction
from p3_to_boolean_dnf import build_games


def test_p3_dnf_is_fixture_derived_and_complete():
    payload=build_games()
    assert payload["oracle_used"] is False
    assert len(payload["players"])==13 and len(set(payload["players"]))==13
    assert payload["games"]["H1"]["clause_count"]==9
    assert payload["games"]["H2"]["clause_count"]==4
    assert set().union(*(set(c) for g in payload["games"].values() for c in g["clauses"]))==set(payload["players"])


def test_saved_p3_1b_threshold_efficiency():
    import csv
    from pathlib import Path
    path=Path(__file__).resolve().parents[2]/"P3_1B"/"results"/"threshold_shapley.csv"
    rows=list(csv.DictReader(path.open(encoding="utf-8-sig")))
    for game in ("H1","H2"):
        assert sum(Fraction(r["shapley_fraction"]) for r in rows if r["threshold"]==game)==1
