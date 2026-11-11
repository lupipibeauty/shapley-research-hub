from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
import tempfile
import time
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aggregate_report_shapley.d1p import all_incremental_states, load_d1p_spec  # noqa: E402
from aggregate_report_shapley.d1p_values import D1PValueSuite, count_closed_form  # noqa: E402


LUO_EXE = ROOT / "external" / "luo" / "build" / "windows-gnu" / "shapley-value.exe"
R1 = ROOT / "outputs" / "v4_0" / "R1"


def fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def construct_join_count_encoding(
    csv_dir: Path,
    meta_dir: Path,
    scaled_payments: list[int],
) -> dict[str, object]:
    """Encode an additive record game in Luo's fixed three-table world join.

    Each replicated join chain has a unique key and all three physical rows are
    owned by the same D1-P record player. Selecting that player therefore creates
    exactly one independent output tuple per replica.
    """
    csv_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    city_rows: list[dict[str, str]] = []
    country_rows: list[dict[str, str]] = []
    language_rows: list[dict[str, str]] = []
    seller_by_row: list[int] = []
    row_id = 0
    for player, replicas in enumerate(scaled_payments):
        for replica in range(replicas):
            key = f"P{player:02d}_R{replica:04d}"
            city_rows.append({"CountryCode": key, "city_payload": key})
            country_rows.append({"Code": key, "country_payload": key})
            language_rows.append({"CountryCode": key, "language_payload": key})
            seller_by_row.append(player)
            row_id += 1

    write_csv(csv_dir / "city.csv", ["CountryCode", "city_payload"], city_rows)
    write_csv(csv_dir / "country.csv", ["Code", "country_payload"], country_rows)
    write_csv(
        csv_dir / "countrylanguage.csv",
        ["CountryCode", "language_payload"],
        language_rows,
    )

    row_ids = list(range(row_id))
    seller_file = {
        "index": {str(index): index for index in row_ids},
        "seller": {str(index): seller_by_row[index] for index in row_ids},
    }
    for table in ("city", "country", "countrylanguage"):
        (meta_dir / f"{table}-index.json").write_text(
            json.dumps(row_ids, separators=(",", ":")), encoding="utf-8"
        )
        (meta_dir / f"{table}-seller.json").write_text(
            json.dumps(seller_file, separators=(",", ":")), encoding="utf-8"
        )

    return {
        "join_output_rows": row_id,
        "physical_csv_rows": row_id * 3,
        "seller_assignments": row_id * 3,
    }


def run_luo(
    csv_dir: Path,
    meta_dir: Path,
    output: Path,
    scheme: str,
    timeout_seconds: int,
) -> dict[str, object]:
    command = [
        str(LUO_EXE),
        "-i",
        str(csv_dir),
        "-m",
        str(meta_dir),
        "-d",
        "world",
        "-o",
        str(output),
        "-s",
        scheme,
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )
    duration = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(
            f"Luo {scheme} failed with exit code {completed.returncode}: {completed.stderr}"
        )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "wall_seconds": duration,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "raw": json.loads(output.read_text(encoding="utf-8")),
    }


def compare_payments(
    raw_values: dict[str, float],
    exact: list[Fraction],
    integer_scale: int,
) -> dict[str, object]:
    rows = []
    maximum_absolute_error = 0.0
    for player, expected in enumerate(exact):
        raw = float(raw_values[str(player)])
        adapted = raw / integer_scale
        error = abs(adapted - float(expected))
        maximum_absolute_error = max(maximum_absolute_error, error)
        rows.append(
            {
                "player": f"p{player + 1}",
                "luo_raw": raw,
                "integer_scale": integer_scale,
                "adapted_payment": adapted,
                "exact_payment": fraction_text(expected),
                "absolute_error": error,
            }
        )
    return {"rows": rows, "maximum_absolute_error": maximum_absolute_error}


def main() -> None:
    if not LUO_EXE.is_file():
        raise FileNotFoundError(f"Missing Luo executable: {LUO_EXE}")
    R1.mkdir(parents=True, exist_ok=True)

    spec = load_d1p_spec(ROOT / "config" / "d1p_design.yaml")
    states = all_incremental_states(spec)
    suite = D1PValueSuite(spec, states[-1], ROOT / "config" / "value_spec_v3_2.yaml")
    exact = count_closed_form(spec, suite)
    integer_scale = math.lcm(*(value.denominator for value in exact))
    scaled_payments = [int(value * integer_scale) for value in exact]

    coalition_maximum_error = 0.0
    for mask, state in enumerate(states):
        encoded = sum(
            scaled_payments[player]
            for player in range(spec.player_count)
            if mask & (1 << player)
        ) / integer_scale
        coalition_maximum_error = max(
            coalition_maximum_error,
            abs(encoded - float(suite.v_count(state))),
        )

    with tempfile.TemporaryDirectory(prefix="ars_luo_d1p_ascii_") as temp:
        temp_root = Path(temp)
        csv_dir = temp_root / "csv"
        meta_dir = temp_root / "metadata"
        construction = construct_join_count_encoding(csv_dir, meta_dir, scaled_payments)

        proposed_output = temp_root / "d1p_vcount_proposed.json"
        proposed = run_luo(csv_dir, meta_dir, proposed_output, "proposed", 1800)
        proposed_comparison = compare_payments(
            proposed["raw"]["shapley_values"], exact, integer_scale
        )

        traditional_output = temp_root / "d1p_vcount_trad.json"
        traditional = run_luo(csv_dir, meta_dir, traditional_output, "trad", 1800)
        traditional_comparison = compare_payments(
            traditional["raw"]["shapley_values"], exact, integer_scale
        )

        (R1 / "luo_d1p_vcount_proposed_raw.json").write_text(
            json.dumps(proposed["raw"], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (R1 / "luo_d1p_vcount_trad_raw.json").write_text(
            json.dumps(traditional["raw"], ensure_ascii=False, indent=2), encoding="utf-8"
        )

    tolerance = 1e-10
    if coalition_maximum_error >= tolerance:
        raise AssertionError(f"V-count coalition encoding mismatch: {coalition_maximum_error}")
    if proposed_comparison["maximum_absolute_error"] >= tolerance:
        raise AssertionError("Luo proposed payment mismatch")
    if traditional_comparison["maximum_absolute_error"] >= tolerance:
        raise AssertionError("Luo traditional payment mismatch")

    result = {
        "stage": "R1",
        "algorithm": "Luo independent utility",
        "official_source_modified": False,
        "same_game_contract": {
            "players": [record.record_id for record in spec.records],
            "player_binding": "每个 seller id 对应一条 D1-P 逻辑记录，而不是原论文 world owner",
            "coalitions": 1 << spec.player_count,
            "target_value": "D1-P V-count",
            "report_reference": "完整 35 坐标报表中的分层 record_count 价值版本",
        },
        "construction": {
            "type": "utility-preserving integer replication into the fixed world join plan",
            "integer_scale": integer_scale,
            "exact_record_payments": [fraction_text(value) for value in exact],
            "replicas_per_player": scaled_payments,
            **construction,
            "details": (
                "每个复制单元由 city/country/countrylanguage 三行组成，连接键唯一，"
                "三行均绑定同一记录玩家；选择该玩家时产生一个独立连接输出元组。"
                "Luo 原始计数除以 9 后恢复 V-count。"
            ),
        },
        "coalition_equivalence": {
            "checked_coalitions": 1 << spec.player_count,
            "maximum_absolute_error": coalition_maximum_error,
        },
        "proposed": {**proposed, "comparison": proposed_comparison},
        "traditional": {**traditional, "comparison": traditional_comparison},
        "unsupported_targets": {
            "V1": (
                "包含比例一致性分数，联盟价值不是独立输出元组的固定效用和；"
                "官方 CLI 与 subset_utility 只接受连接结果基数。"
            ),
            "V2_lambda_0_5": (
                "包含跨指标族几何平均交互，不满足独立效用可加假设；"
                "保持同一游戏时不能直接映射为官方连接计数。"
            ),
        },
        "same_game_status": "PARTIAL_COVERAGE",
        "interpretation": (
            "V-count 可通过严格等价的整数复制使用 Luo 官方算法；"
            "V1/V2 的完整报表价值不能原生适配。该结果不是对 35 坐标完整价值函数的通用求解。"
        ),
    }
    (R1 / "luo_d1p_adaptation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "status": "completed",
        "proposed_max_error": proposed_comparison["maximum_absolute_error"],
        "traditional_max_error": traditional_comparison["maximum_absolute_error"],
        "coalition_max_error": coalition_maximum_error,
        "proposed_wall_seconds": proposed["wall_seconds"],
        "traditional_wall_seconds": traditional["wall_seconds"],
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
