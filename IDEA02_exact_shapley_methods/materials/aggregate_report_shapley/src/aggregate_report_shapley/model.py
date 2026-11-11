from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Record:
    player_index: int
    record_id: str
    region_id: str
    city_id: str
    category_id: str
    amount: int


CellKey = str


def cell_key(module: str, *parts: str) -> CellKey:
    return ":".join((module, *parts))


def cell_module(key: CellKey) -> str:
    return key.split(":", 1)[0]

