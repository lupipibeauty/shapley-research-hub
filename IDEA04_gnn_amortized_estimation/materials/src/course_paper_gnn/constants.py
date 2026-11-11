from __future__ import annotations

NUMERIC_FEATURE_DIM = 8
VALUE_DESCRIPTOR_DIM = 14

NODE_TYPES = (
    "player",
    "witness",
    "coordinate",
    "value_factor",
    "report",
)

NODE_TYPE_TO_ID = {name: index for index, name in enumerate(NODE_TYPES)}

SUBTYPES = (
    "player_order",
    "player_customer",
    "player_lineitem",
    "player_supplier",
    "player_nation",
    "witness_join",
    "coordinate_order_valid",
    "coordinate_line_count",
    "coordinate_quantity_sum",
    "coordinate_supplier_count",
    "coordinate_nation_count",
    "value_additive",
    "value_threshold",
    "value_joint",
    "report",
)

SUBTYPE_TO_ID = {name: index for index, name in enumerate(SUBTYPES)}

EDGE_TYPES = (
    "player_in_witness",
    "witness_supports_coordinate",
    "coordinate_to_value_factor",
    "value_factor_to_report",
)

EDGE_TYPE_TO_ID = {name: index for index, name in enumerate(EDGE_TYPES)}

VALUE_TYPES = ("additive", "threshold", "joint")
SHARING_LEVELS = ("independent", "shared")
HIERARCHY_LEVELS = ("tree", "cross")

CONDITION_ORDER = (
    ("independent", "tree", "additive"),
    ("independent", "tree", "joint"),
    ("independent", "cross", "additive"),
    ("independent", "cross", "joint"),
    ("shared", "tree", "additive"),
    ("shared", "tree", "joint"),
    ("shared", "cross", "additive"),
    ("shared", "cross", "joint"),
)

OOD_CONDITION = ("shared", "cross", "joint")
