from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntityLineage:
    entity_id: str
    group_id: str
    clauses: tuple[tuple[int, ...], ...]
    witness_ids: tuple[str, ...]


def extract_lineage(connection) -> tuple[EntityLineage, ...]:
    """Extract OR-of-AND witnesses from full database facts, never from coalition values."""
    rows=connection.execute("""
      SELECT e.entity_id,e.group_id,e.player_index,l.player_index,a.player_index,
             e.record_id||':'||l.record_id||':'||a.record_id AS witness_id
      FROM EntityFact e JOIN LinkFact l ON e.entity_id=l.entity_id
      JOIN AttributeFact a ON l.attribute_id=a.attribute_id
      WHERE a.valid=TRUE ORDER BY e.entity_id,l.link_id,a.attribute_id
    """).fetchall()
    grouped={}
    for entity,group,eidx,lidx,aidx,wid in rows:
        item=grouped.setdefault(entity,{"group":group,"clauses":[],"witnesses":[]})
        item["clauses"].append(tuple(sorted((eidx,lidx,aidx))));item["witnesses"].append(wid)
    return tuple(EntityLineage(e,item["group"],tuple(item["clauses"]),tuple(item["witnesses"]))
                 for e,item in sorted(grouped.items()))


def validate_lineage(lineage: tuple[EntityLineage,...], n_players: int) -> dict:
    clauses=[c for entity in lineage for c in entity.clauses]
    if any(len(set(c))!=3 for c in clauses): raise AssertionError("each witness must use three fact players")
    if any(i<0 or i>=n_players for c in clauses for i in c): raise AssertionError("invalid player index")
    return {
      "entities":len(lineage),"groundings":len(clauses),
      "alternative_entities":sum(len(e.clauses)>1 for e in lineage),
      "cross_entity_shared_players":sum(1 for i in range(n_players)
          if len({e.entity_id for e in lineage if any(i in c for c in e.clauses)})>1),
    }

