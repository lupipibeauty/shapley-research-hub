from __future__ import annotations

from .model import CellKey, Record, cell_key


D1_RECORDS: tuple[Record, ...] = (
    Record(0, "t1", "S", "S1", "X", 10),
    Record(1, "t2", "S", "S1", "Y", 10),
    Record(2, "t3", "S", "S2", "X", 20),
    Record(3, "t4", "S", "S2", "Y", 20),
    Record(4, "t5", "L", "L1", "X", 10),
    Record(5, "t6", "L", "L1", "Y", 10),
    Record(6, "t7", "L", "L1", "X", 20),
    Record(7, "t8", "L", "L1", "Y", 20),
    Record(8, "t9", "L", "L2", "X", 10),
    Record(9, "t10", "L", "L2", "Y", 10),
    Record(10, "t11", "L", "L2", "X", 20),
    Record(11, "t12", "L", "L2", "Y", 20),
)

D1_MODULE_CELLS: dict[str, tuple[CellKey, ...]] = {
    "all": (cell_key("all", "ALL"),),
    "region": tuple(cell_key("region", value) for value in ("S", "L")),
    "city": tuple(cell_key("city", value) for value in ("S1", "S2", "L1", "L2")),
    "category": tuple(cell_key("category", value) for value in ("X", "Y")),
    "region_category": tuple(
        cell_key("region_category", region, category)
        for region in ("S", "L")
        for category in ("X", "Y")
    ),
}

D1_CELLS: tuple[CellKey, ...] = tuple(
    cell for module_cells in D1_MODULE_CELLS.values() for cell in module_cells
)


def d1_membership(record: Record) -> tuple[CellKey, ...]:
    return (
        cell_key("all", "ALL"),
        cell_key("region", record.region_id),
        cell_key("city", record.city_id),
        cell_key("category", record.category_id),
        cell_key("region_category", record.region_id, record.category_id),
    )


D1_MEMBERSHIP: tuple[tuple[CellKey, ...], ...] = tuple(
    d1_membership(record) for record in D1_RECORDS
)


def group_masks(attribute: str) -> tuple[int, ...]:
    values: dict[str, int] = {}
    for record in D1_RECORDS:
        value = getattr(record, attribute)
        values[value] = values.get(value, 0) | (1 << record.player_index)
    return tuple(values[value] for value in sorted(values))


D1_CITY_BLOCKS = group_masks("city_id")
D1_REGION_BLOCKS = group_masks("region_id")

D1_LEVELS: tuple[tuple[int, ...], ...] = (
    tuple(1 << i for i in range(len(D1_RECORDS))),
    D1_CITY_BLOCKS,
    D1_REGION_BLOCKS,
    ((1 << len(D1_RECORDS)) - 1,),
)

