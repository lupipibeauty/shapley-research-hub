from __future__ import annotations


def semantic_stats(report: dict[tuple[str,str],dict]) -> dict[str,float]:
    def metric(node, category, name):
        row=report.get((node,category),{})
        value=row.get(name,0.0)
        return 0.0 if value is None else float(value)
    return {
        "root_distinct": metric("ROOT","ALL","distinct_entity_count"),
        "root_value": metric("ROOT","ALL","value_sum_coalesced"),
        "a_bag": metric("A","ALL","bag_count"),
        "b_distinct": metric("B","ALL","distinct_entity_count"),
        "root_c1_value": metric("ROOT","C1","value_sum_coalesced"),
        "b_c2_distinct": metric("B","C2","distinct_entity_count"),
    }


def utility(report: dict, utility_id: str) -> float:
    s=semantic_stats(report)
    if utility_id == "G0-ADD-COMMON":
        # Strictly common to H0/H1/H2.
        return 1.5*s["root_distinct"] + 0.25*s["root_value"]
    if utility_id == "G0-ADD-NATURAL":
        return sum(0.5*float(row["bag_count"]) + 1.5*float(row["distinct_entity_count"]) +
                   0.25*float(row["value_sum_coalesced"]) for row in report.values())
    if utility_id == "G1-LOCAL-COMMON":
        return 0.5*min(s["a_bag"],2) + 1.5*min(s["b_distinct"],1) + 0.25*min(s["root_value"],6)
    if utility_id == "G2-JOINT-TASK-COMMON":
        # Exact frozen P1 action A1, the largest coordinate subset present in both H1/H2.
        return max(0.0, 6*min(s["root_distinct"],2) + 4*min(s["a_bag"],3) - 10)
    if utility_id == "G2-JOINT-TASK-FULL":
        a1=6*min(s["root_distinct"],2) + 4*min(s["a_bag"],3) - 10
        a2=1*min(s["root_c1_value"],10) + 5*min(s["b_c2_distinct"],1) - 8
        return max(0.0,a1,a2)
    raise KeyError(utility_id)

