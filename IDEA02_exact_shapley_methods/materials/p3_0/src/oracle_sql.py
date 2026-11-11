from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import duckdb


def load_fixture(path):return json.loads(Path(path).read_text(encoding="utf-8"))


def create_database(schema_path,fixture):
    con=duckdb.connect();con.execute(Path(schema_path).read_text(encoding="utf-8"))
    con.executemany("INSERT INTO GroupDimension VALUES (?,?)",[(g["group_id"],g["group_name"]) for g in fixture["groups"]])
    for r in fixture["entities"]:
        con.execute("INSERT INTO EntityFact VALUES (?,?,?,?,?,?,?,?)",[r["player_index"],r["record_id"],r["entity_id"],r["group_id"],None,None,None,r["source_id"]])
    for r in fixture["attributes"]:
        con.execute("INSERT INTO AttributeFact VALUES (?,?,?,?,?,?,?,?)",[r["player_index"],r["record_id"],r["attribute_id"],r["attribute_type"],r["valid"],r["value"],None,r["source_id"]])
    for r in fixture["links"]:
        con.execute("INSERT INTO LinkFact VALUES (?,?,?,?,?,?,?)",[r["player_index"],r["record_id"],r["link_id"],r["entity_id"],r["attribute_id"],None,r["source_id"]])
    facts=fixture["entities"]+fixture["links"]+fixture["attributes"]
    rel=lambda r:"EntityFact" if r["player_id"].startswith("E") else ("LinkFact" if r["player_id"].startswith("L") else "AttributeFact")
    con.executemany("INSERT INTO PlayerRegistry VALUES (?,?,?,?,?,?)",[(r["player_index"],r["player_id"],r["record_id"],rel(r),True,fixture["player_version"]) for r in facts])
    con.executemany("INSERT INTO OwnerMapping VALUES (?,?,?)",[(m,p,o) for m,mp in fixture["owner_maps"].items() for p,o in mp.items()])
    return con


def python_counts(fixture,mask):
    selected=lambda r:bool(mask&(1<<r["player_index"]))
    entities={r["entity_id"]:r for r in fixture["entities"] if selected(r)}
    attrs={r["attribute_id"]:r for r in fixture["attributes"] if selected(r) and r["valid"]}
    qualified=set()
    for link in fixture["links"]:
        if selected(link) and link["entity_id"] in entities and link["attribute_id"] in attrs:
            qualified.add((link["entity_id"],entities[link["entity_id"]]["group_id"]))
    return tuple(sum(group==g for _,group in qualified) for g in ("A","B"))


def all_sql_counts(connection,n):
    rows=connection.execute(f"""
      WITH masks AS (SELECT range::BIGINT mask FROM range({1<<n})),
      Qualified AS (
        SELECT DISTINCT m.mask,e.entity_id,e.group_id
        FROM masks m JOIN EntityFact e ON ((m.mask>>e.player_index)&1)=1
        JOIN LinkFact l ON e.entity_id=l.entity_id AND ((m.mask>>l.player_index)&1)=1
        JOIN AttributeFact a ON l.attribute_id=a.attribute_id AND ((m.mask>>a.player_index)&1)=1
        WHERE a.valid=TRUE
      )
      SELECT m.mask,g.group_id,COUNT(DISTINCT q.entity_id)::INTEGER
      FROM masks m CROSS JOIN GroupDimension g
      LEFT JOIN Qualified q ON q.mask=m.mask AND q.group_id=g.group_id
      WHERE g.group_id IN ('A','B') GROUP BY m.mask,g.group_id ORDER BY m.mask,g.group_id
    """).fetchall()
    out=defaultdict(dict)
    for mask,g,count in rows:out[mask][g]=count
    return [(out[m]["A"],out[m]["B"]) for m in range(1<<n)]
