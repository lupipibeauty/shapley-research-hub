from fractions import Fraction
from pathlib import Path

from build_lineage import extract_lineage
from native_exact_baseline import LayeredJointDecisionDiagram,game_value,shapley_from_conditional
from oracle_shapley import mobius_shapley,subset_shapley
from oracle_sql import all_sql_counts,create_database,load_fixture

ROOT=Path(__file__).resolve().parents[1]


def test_native_fact_lineage_method_matches_two_independent_oracles():
    fixture=load_fixture(ROOT/"fixtures"/"anchor_13_players.json")
    con=create_database(ROOT/"schema"/"complete_schema.sql",fixture)
    try:
        diagram=LayeredJointDecisionDiagram(extract_lineage(con),13)
        distributions=diagram.all_conditional_distributions()
        counts=all_sql_counts(con,13)
    finally:con.close()
    assert sum(diagram.distribution().values())==8192
    for i in range(13):
        assert sum(distributions[(i,0)].values())==4096
        assert sum(distributions[(i,1)].values())==4096
    for game in ("G0","G1"):
        values=[game_value(game,*x) for x in counts]
        native=shapley_from_conditional(distributions,13,game)
        assert native==subset_shapley(values,13)==mobius_shapley(values,13)
        assert sum(native)==values[-1]-values[0]


def test_revenue_rule_and_owner_mapping_do_not_change_record_shapley():
    fixture=load_fixture(ROOT/"fixtures"/"anchor_13_players.json")
    con=create_database(ROOT/"schema"/"complete_schema.sql",fixture)
    try:diagram=LayeredJointDecisionDiagram(extract_lineage(con),13)
    finally:con.close()
    phi=shapley_from_conditional(diagram.all_conditional_distributions(),13,"G1")
    payments=[Fraction(1000)*x/2 for x in phi]
    assert sum(phi)==2 and sum(payments)==1000 and all(x>=0 for x in phi)
    assert set(fixture["owner_maps"]["OwnerMap-A"])==set(fixture["owner_maps"]["OwnerMap-B"])

