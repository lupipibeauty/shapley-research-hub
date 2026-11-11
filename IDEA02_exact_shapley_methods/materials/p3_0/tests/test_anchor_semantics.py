from pathlib import Path

from build_lineage import extract_lineage,validate_lineage
from oracle_sql import all_sql_counts,create_database,load_fixture,python_counts

ROOT=Path(__file__).resolve().parents[1]


def test_anchor_all_coalitions_sql_equals_python():
    fixture=load_fixture(ROOT/"fixtures"/"anchor_13_players.json")
    con=create_database(ROOT/"schema"/"complete_schema.sql",fixture)
    try:
        sql=all_sql_counts(con,13)
        py=[python_counts(fixture,m) for m in range(1<<13)]
        assert sql==py
        assert sql[0]==(0,0) and sql[-1]==(2,2)
    finally:con.close()


def test_lineage_has_required_complementarity_and_reuse():
    fixture=load_fixture(ROOT/"fixtures"/"anchor_13_players.json")
    con=create_database(ROOT/"schema"/"complete_schema.sql",fixture)
    try:audit=validate_lineage(extract_lineage(con),13)
    finally:con.close()
    assert audit=={"entities":4,"groundings":6,"alternative_entities":2,"cross_entity_shared_players":3}

