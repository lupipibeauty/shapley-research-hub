from exact_shapley import mobius_shapley,subset_shapley
from p2_instances import build_instances
from p2_oracle import q2_groundings,report
from p2_utilities import utility


def test_independent_exact_oracles_and_efficiency():
    instance=build_instances()["F2-PATH-HIGH"]
    values=[utility(report(q2_groundings(instance,m),"H2-CROSS"),"G2-JOINT-TASK-FULL") for m in range(1<<12)]
    a=subset_shapley(values,12); b=mobius_shapley(values,12)
    assert max(abs(x-y) for x,y in zip(a,b))<1e-10
    assert abs(sum(a)-(values[-1]-values[0]))<1e-10


def test_full_g2_is_active_on_reachable_reports():
    instance=build_instances()["F2-PATH-HIGH"]
    values=[utility(report(q2_groundings(instance,m),"H2-CROSS"),"G2-JOINT-TASK-FULL") for m in range(1<<12)]
    assert len(set(values))>2
    assert any(values[m|3]-values[m|1]-values[m|2]+values[m] for m in range(1<<12) if not m&3)

