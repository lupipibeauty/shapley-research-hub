from __future__ import annotations

from collections import defaultdict

from p2_instances import GROUP_CLOSURE, HIERARCHIES


def q2_groundings(instance, mask: int) -> list[dict]:
    chosen=lambda row: bool(mask & (1 << row["player_index"]))
    entities={r["entity_id"]:r for r in instance.entities if chosen(r)}
    attributes={r["attribute_id"]:r for r in instance.attributes if chosen(r)}
    rows=[]
    for link in instance.links:
        if chosen(link) and link["entity_id"] in entities and link["attribute_id"] in attributes:
            e,a=entities[link["entity_id"]],attributes[link["attribute_id"]]
            rows.append({"entity_id":e["entity_id"],"leaf_group":e["group_id"],"category":a["category"],
                         "value":a["value"],"witness_id":f"{e['entity_rec_id']}:{link['link_rec_id']}:{a['attribute_rec_id']}",
                         "players":tuple(sorted((e["player_id"],link["player_id"],a["player_id"])))})
    return rows


def report(rows: list[dict], hierarchy: str) -> dict[tuple[str,str],dict]:
    closure=defaultdict(set)
    for node,leaf in GROUP_CLOSURE: closure[node].add(leaf)
    result={}
    for node,category in HIERARCHIES[hierarchy]:
        selected=[r for r in rows if r["leaf_group"] in closure[node] and (category=="ALL" or r["category"]==category)]
        values=[float(r["value"]) for r in selected if r["value"] is not None]
        result[(node,category)]={
            "bag_count":len(selected),"distinct_entity_count":len({r["entity_id"] for r in selected}),
            "raw_sum":None if not values else sum(values),"value_sum_coalesced":sum(values) if values else 0.0,
        }
    return result


def lineage(instance) -> dict[str,list[tuple[str,...]]]:
    result=defaultdict(list)
    for row in q2_groundings(instance,(1<<instance.n_players)-1):
        result[row["entity_id"]].append(row["players"])
    return dict(result)

