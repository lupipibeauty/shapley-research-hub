from p2_instances import build_instances
from p2_oracle import lineage,q2_groundings,report


def test_all_source_families_share_query_scale():
    instances=build_instances()
    assert {x.n_players for x in instances.values()}=={12}
    assert {(len(x.entities),len(x.links),len(x.attributes)) for x in instances.values()}=={(4,4,4)}
    assert {sum(map(len,lineage(x).values())) for x in instances.values()}=={4}


def test_factorial_pair_has_identical_full_reports_but_different_reuse():
    instances=build_instances(); low=instances["F5-OUTPUT-MATCHED-LOW"]; high=instances["F2-PATH-HIGH"]
    for hierarchy in ("H1-TREE","H2-CROSS"):
        assert report(q2_groundings(low,(1<<12)-1),hierarchy)==report(q2_groundings(high,(1<<12)-1),hierarchy)
    low_lin,high_lin=lineage(low),lineage(high)
    assert not any(sum(p in c for terms in low_lin.values() for c in terms)>1 for p in ("p9","p10","p11","p12"))
    assert any(sum(p in c for terms in high_lin.values() for c in terms)>1 for p in ("p9","p10","p11","p12"))

