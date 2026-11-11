from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class P2Instance:
    family: str
    entities: tuple[dict, ...]
    links: tuple[dict, ...]
    attributes: tuple[dict, ...]
    structural_role: str

    @property
    def n_players(self) -> int:
        return len(self.entities) + len(self.links) + len(self.attributes)


def _row(index: int, relation: str, rec_id: str, **values) -> dict:
    return {"player_index": index, "player_id": f"p{index+1}", "owner_id": f"o{index % 3 + 1}",
            f"{relation}_rec_id": rec_id, **values}


def _base_entities(groups=("A1", "A2", "B1", "B2")) -> tuple[dict, ...]:
    return tuple(_row(i, "entity", f"er{i+1}", entity_id=f"e{i+1}", group_id=g, amount=1.0)
                 for i, g in enumerate(groups))


def _base_attributes() -> tuple[dict, ...]:
    # Equal non-NULL values make the F2/F5 full H1/H2 reports exactly match.
    specs=(("a1",2.0,"C1"),("a2",None,"C2"),("a3",2.0,"C1"),("a4",2.0,"C1"))
    return tuple(_row(8+i,"attribute",f"ar{i+1}",attribute_id=a,value=v,category=c)
                 for i,(a,v,c) in enumerate(specs))


def _links(pairs: tuple[tuple[str,str], ...]) -> tuple[dict, ...]:
    return tuple(_row(4+i,"link",f"lr{i+1}",entity_id=e,attribute_id=a,link_value=1.0,
                      category=("C2" if a=="a2" else "C1")) for i,(e,a) in enumerate(pairs))


def build_instances() -> dict[str, P2Instance]:
    attrs=_base_attributes()
    return {
        "F0-DISJOINT": P2Instance("F0-DISJOINT",_base_entities(),_links((("e1","a1"),("e2","a2"),("e3","a3"),("e4","a4"))),attrs,
                                  "four independent one-witness outputs"),
        "F1-STAR": P2Instance("F1-STAR",_base_entities(),_links((("e1","a1"),("e1","a2"),("e1","a3"),("e1","a4"))),attrs,
                              "one entity player reused by four witnesses"),
        "F2-PATH-HIGH": P2Instance("F2-PATH-HIGH",_base_entities(),_links((("e1","a1"),("e2","a1"),("e2","a2"),("e3","a3"))),attrs,
                                   "attribute a1 shared across outputs and entity e2 has alternatives"),
        "F5-OUTPUT-MATCHED-LOW": P2Instance("F5-OUTPUT-MATCHED-LOW",_base_entities(("A2","A1","B1","B2")),
                                            _links((("e1","a1"),("e1","a2"),("e2","a3"),("e3","a4"))),attrs,
                                            "same facts, groundings and full H1/H2 output as F2; no attribute shared across outputs"),
    }


GROUP_CLOSURE=(
    ("ROOT","A1"),("ROOT","A2"),("ROOT","B1"),("ROOT","B2"),
    ("A","A1"),("A","A2"),("B","B1"),("B","B2"),
    ("A1","A1"),("A2","A2"),("B1","B1"),("B2","B2"),
)

HIERARCHIES={
    "H0-ONE": (("ROOT","ALL"),),
    "H1-TREE": tuple((node,"ALL") for node in ("ROOT","A","B","A1","A2","B1","B2")),
    "H2-CROSS": tuple((node,"ALL") for node in ("ROOT","A","B","A1","A2","B1","B2")) +
                tuple((node,cat) for node in ("ROOT","A","B") for cat in ("C1","C2")),
    "H2-MATCH7": (("ROOT","ALL"),("A","ALL"),("B","ALL"),("ROOT","C1"),("ROOT","C2"),("A","C1"),("A","C2")),
}

