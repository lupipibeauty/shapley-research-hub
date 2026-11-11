"""从冻结 P3-0 fixture/JOIN witness 构造 H1/H2 DNF，不读取联盟真值。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
P3_1C = HERE.parents[1]
P3_1B = P3_1C.parent / "P3_1B"
P3_0 = P3_1C.parent / "P3_0"
sys.path.insert(0, str(P3_1B / "src"))
from threshold_lineage import entity_witnesses, load_fixture, minimal_winning_coalitions  # noqa: E402


def build_games(fixture_path: Path | None = None) -> dict:
    fixture_path = fixture_path or P3_0 / "fixtures" / "anchor_13_players.json"
    fixture = load_fixture(fixture_path)
    rows = fixture["entities"] + fixture["links"] + fixture["attributes"]
    index_to_id = {int(row["player_index"]): row["player_id"] for row in rows}
    groups, witnesses = entity_witnesses(fixture)
    games = {}
    for threshold in (1, 2):
        winners = minimal_winning_coalitions(groups, witnesses, threshold)
        clauses = [[index_to_id[i] for i in sorted(winner)] for winner in winners]
        games[f"H{threshold}"] = {
            "threshold": threshold,
            "clauses": clauses,
            "clause_count": len(clauses),
            "variable_occurrences": sum(map(len, clauses)),
        }
    return {
        "source": str(fixture_path),
        "oracle_used": False,
        "players": [index_to_id[i] for i in sorted(index_to_id)],
        "player_index": {index_to_id[i]: i for i in sorted(index_to_id)},
        "games": games,
    }


def write_games(path: Path) -> dict:
    payload = build_games()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
