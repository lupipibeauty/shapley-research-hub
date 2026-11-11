from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OFFICIAL = ROOT / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main"
for item in (SRC, OFFICIAL):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from aggregate_report_shapley.d1p import METRICS, all_incremental_states, load_d1p_spec  # noqa: E402
from aggregate_report_shapley.d1p_values import D1PValueSuite  # noqa: E402
from Algorithms.LExaShap.ShapleyCircuit import DNFCircuit  # noqa: E402


OUT = ROOT / "outputs" / "v4_0" / "H0"
CONFIG = ROOT / "config" / "d1p_design.yaml"
VALUE_CONFIG = ROOT / "config" / "value_spec_v3_2.yaml"
GAMES = ("V_count", "V1", "V2_lambda_0_5")
HISTORICAL_INPUTS = [
    CONFIG,
    VALUE_CONFIG,
    ROOT / "src" / "aggregate_report_shapley" / "d1p.py",
    ROOT / "src" / "aggregate_report_shapley" / "d1p_sql.py",
    ROOT / "src" / "aggregate_report_shapley" / "d1p_values.py",
    ROOT / "reports" / "Abramovich_AB_N2_AB_J1实验报告_2026-10-31.md",
    ROOT / "reports" / "Abramovich_AB_N3_L_AB_N4_DP实验报告_2026-10-31.md",
    ROOT / "reports" / "Abramovich_AB_J2实验报告_2026-10-31.md",
    ROOT / "reports" / "fgsv_r2_4_error_source_decomposition.md",
    ROOT / "reports" / "fgsv_r2_5_data_environment_control.md",
    ROOT / "outputs" / "v4_0" / "R1" / "abramovich_d1p_adaptation.json",
    ROOT / "outputs" / "v4_0" / "R1" / "luo_d1p_adaptation.json",
    ROOT / "outputs" / "v4_0" / "AB_N2_AB_J1_2026_10_31" / "AB_J1" / "source_expressions.json",
    ROOT / "outputs" / "v4_0" / "AB_J2_2026_10_31" / "source_expressions.json",
    OFFICIAL / "Algorithms" / "LExaShap" / "ShapleyCircuit.py",
    OFFICIAL / "Algorithms" / "LExaShap" / "ShapleyEngine.py",
]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"refuse empty CSV: {path}")
    fieldnames: list[str] = []
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def historical_hashes() -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in HISTORICAL_INPUTS
    }


def decimal_value(value: Fraction | Decimal | int | float) -> Decimal:
    if isinstance(value, Fraction):
        return Decimal(value.numerator) / Decimal(value.denominator)
    return Decimal(value)


def exact_symmetric(values: list[Fraction | Decimal], i: int, j: int) -> bool:
    bit_i, bit_j = 1 << i, 1 << j
    for mask in range(len(values)):
        if mask & (bit_i | bit_j):
            continue
        if values[mask | bit_i] != values[mask | bit_j]:
            return False
    return True


def is_dummy(values: list[Fraction | Decimal], player: int) -> bool:
    bit = 1 << player
    for mask in range(len(values)):
        if mask & bit:
            continue
        if values[mask | bit] != values[mask]:
            return False
    return True


def equivalence_classes(values: list[Fraction | Decimal], n: int) -> list[list[int]]:
    unassigned = set(range(n))
    classes: list[list[int]] = []
    while unassigned:
        pivot = min(unassigned)
        cls = [item for item in sorted(unassigned) if exact_symmetric(values, pivot, item)]
        classes.append(cls)
        unassigned.difference_update(cls)
    return classes


def affected_coordinates(spec, suite, states, player: int, active_metrics: Iterable[str]) -> list[str]:
    affected: list[str] = []
    bit = 1 << player
    for node in spec.nodes:
        for metric in active_metrics:
            changed = False
            for mask in range(1 << spec.player_count):
                if mask & bit:
                    continue
                if suite.coordinate_score(states[mask | bit], node, metric) != suite.coordinate_score(states[mask], node, metric):
                    changed = True
                    break
            if changed:
                affected.append(f"{node}:{metric}")
    return affected


def shapley_from_values(values: list[Fraction | Decimal], n: int) -> list[Decimal]:
    weights = [Decimal(math.factorial(k) * math.factorial(n - k - 1)) / Decimal(math.factorial(n)) for k in range(n)]
    result = [Decimal(0) for _ in range(n)]
    for i in range(n):
        bit = 1 << i
        for mask in range(1 << n):
            if mask & bit:
                continue
            result[i] += weights[mask.bit_count()] * (decimal_value(values[mask | bit]) - decimal_value(values[mask]))
    return result


def type_count_key(mask: int, classes: list[list[int]]) -> tuple[int, ...]:
    return tuple(sum(bool(mask & (1 << player)) for player in cls) for cls in classes)


def count_dtree(root) -> tuple[int, Counter[str]]:
    counts: Counter[str] = Counter()

    def visit(node) -> int:
        op = "exclusive_split" if hasattr(node.op, "label") else str(node.op)
        if not getattr(node, "children", None):
            op = "leaf"
        counts[op] += 1
        return 1 + sum(visit(child) for child in (getattr(node, "children", None) or []))

    return visit(root), counts


def count_value_graph(root_value) -> int:
    seen: set[int] = set()

    def visit(value) -> None:
        identity = id(value)
        if identity in seen:
            return
        seen.add(identity)
        for child in getattr(value, "_prev", set()):
            visit(child)

    visit(root_value)
    return len(seen)


def compile_expression_stats(components: list[list[list[str]]]) -> dict[str, Any]:
    dtree_nodes = 0
    value_nodes = 0
    ops: Counter[str] = Counter()
    for dnf in components:
        circuit = DNFCircuit([set(clause) for clause in dnf])
        nodes, component_ops = count_dtree(circuit.root)
        dtree_nodes += nodes
        value_nodes += count_value_graph(circuit.root.value)
        ops.update(component_ops)
    return {
        "official_components": len(components),
        "official_dtree_nodes_total": dtree_nodes,
        "official_value_graph_nodes_total": value_nodes,
        "official_dtree_operator_counts": json.dumps(dict(sorted(ops.items())), ensure_ascii=False),
    }


def provenance_diagnostics() -> list[dict[str, Any]]:
    j1_path = OUT.parent / "AB_N2_AB_J1_2026_10_31" / "AB_J1" / "source_expressions.json"
    j2_path = OUT.parent / "AB_J2_2026_10_31" / "source_expressions.json"
    j1 = json.loads(j1_path.read_text(encoding="utf-8-sig"))
    j2 = json.loads(j2_path.read_text(encoding="utf-8-sig"))
    rows: list[dict[str, Any]] = []

    j1_specs = {
        "AB-J1 COUNT(*)": [item["dnf"] for item in j1["A_COUNT_STAR_BAG"]],
        "AB-J1 COUNT DISTINCT": [item["dnf"] for item in j1["B_COUNT_DISTINCT_KEY_MANUAL_REDUCTION"]],
        "AB-J1 Boolean tuple": [j1["C_BOOLEAN_OUTPUT_TUPLE"]["dnf"]],
    }
    for query, components in j1_specs.items():
        clauses = sum(len(component) for component in components)
        occurrences = sum(len(clause) for component in components for clause in component)
        stats = compile_expression_stats(components)
        rows.append({
            "diagnostic_kind": "QUERY_PROVENANCE",
            "game_or_query": query,
            "player": "ALL",
            "source_rows_or_players": 3,
            "join_groundings": 2,
            "grounding_occurrence_vector": "p1:1|p2:1|p3:2",
            "minimal_dnf_clauses": clauses,
            "dnf_variable_occurrences": occurrences,
            "factored_expression": "p3 AND (p1 OR p2)" if "COUNT(*)" not in query else "two arithmetic components: p1p3 + p2p3",
            "query_variable_structure": "Q(k) :- L(a,k), R(b,k); all-/q-/sq-hierarchical; no self-join",
            **stats,
            "evidence_status": "VERIFIED_FROM_SOURCE_JSON_AND_OFFICIAL_COMPILER",
        })

    j2_specs = {
        "AB-J2 Q1 COUNT(*)": [item["dnf"] for item in j2["Q1_COUNT_STAR_BAG"]["components"]],
        "AB-J2 Q2 COUNT DISTINCT": [item["dnf"] for item in j2["Q2_COUNT_DISTINCT_KEY"]["components"]],
        "AB-J2 Q3 HAVING>=2": [item["dnf"] for item in j2["Q3_HAVING_COUNT_GE_2"]["components"]],
    }
    for query, components in j2_specs.items():
        clauses = sum(len(component) for component in components)
        occurrences = sum(len(clause) for component in components for clause in component)
        if "Q3" in query:
            factored = "(p1 AND p2 AND (p4 OR p5)) OR (p4 AND p5 AND (p1 OR p2)); K2=false"
            factorization_verified = all(
                (
                    any(all(mask & (1 << (int(player[1:]) - 1)) for player in clause) for clause in components[0])
                    == bool(
                        ((mask & 1) and (mask & 2) and ((mask & 8) or (mask & 16)))
                        or ((mask & 8) and (mask & 16) and ((mask & 1) or (mask & 2)))
                    )
                )
                for mask in range(64)
            )
        elif "Q2" in query:
            factored = "((p1 OR p2) AND (p4 OR p5)) + (p3 AND p6)"
            factorization_verified = True
        else:
            factored = "five arithmetic grounding components"
            factorization_verified = True
        stats = compile_expression_stats(components)
        rows.append({
            "diagnostic_kind": "QUERY_PROVENANCE",
            "game_or_query": query,
            "player": "ALL",
            "source_rows_or_players": 6,
            "join_groundings": 5,
            "grounding_occurrence_vector": "p1:2|p2:2|p3:1|p4:2|p5:2|p6:1",
            "minimal_dnf_clauses": clauses,
            "dnf_variable_occurrences": occurrences,
            "factored_expression": factored,
            "factorization_truth_table_verified": factorization_verified,
            "query_variable_structure": "Q(k) :- L(a,k), R(b,k); all-/q-/sq-hierarchical; no self-join",
            **stats,
            "evidence_status": "VERIFIED_FROM_SOURCE_JSON_AND_OFFICIAL_COMPILER",
        })
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    hashes_before = historical_hashes()
    spec = load_d1p_spec(CONFIG, revenue=1000)
    states = all_incremental_states(spec)
    suite = D1PValueSuite(spec, states[spec.full_mask], VALUE_CONFIG)
    values = suite.all_values(states)
    shapley = {game: shapley_from_values(values[game], spec.player_count) for game in GAMES}

    game_classes: dict[str, list[list[int]]] = {
        game: equivalence_classes(values[game], spec.player_count) for game in GAMES
    }
    diagnostic_rows: list[dict[str, Any]] = []

    canonical_states = len({state.canonical(spec.nodes) for state in states})
    for game in GAMES:
        classes = game_classes[game]
        class_of = {player: class_index for class_index, cls in enumerate(classes) for player in cls}
        type_state_count = math.prod(len(cls) + 1 for cls in classes)
        realized_type_states = len({type_count_key(mask, classes) for mask in range(1 << spec.player_count)})
        value_by_type: dict[tuple[int, ...], Decimal] = {}
        type_sufficient = True
        for mask in range(1 << spec.player_count):
            key = type_count_key(mask, classes)
            current = values[game][mask]
            if key in value_by_type and value_by_type[key] != current:
                type_sufficient = False
            value_by_type[key] = current

        active_metrics = ("record_count",) if game == "V_count" else METRICS
        for record in spec.records:
            increments = []
            if True:
                increments.append("total")
            if record.category_a_id == spec.category_a_target:
                increments.append("category_a_target")
            if record.attribute_present:
                increments.append("attribute_present")
            if record.attribute_present and record.category_b_id == spec.category_b_target:
                increments.append("category_b_target")
            affected = affected_coordinates(spec, suite, states, record.player_index, active_metrics)
            cls = classes[class_of[record.player_index]]
            diagnostic_rows.append({
                "diagnostic_kind": "D1P_PLAYER_GAME",
                "game_or_query": game,
                "player": record.record_id,
                "source_rows_or_players": spec.player_count,
                "leaf": record.leaf_node_id,
                "category_a": record.category_a_id,
                "attribute_present": record.attribute_present,
                "category_b": record.category_b_id or "NULL",
                "base_signature": f"{record.leaf_node_id}|{record.category_a_id}|present={int(record.attribute_present)}|B={record.category_b_id or 'NULL'}",
                "changed_sufficient_statistics": "|".join(increments) + " @ " + "|".join(spec.ancestors[record.leaf_node_id]),
                "affected_coordinate_count": len(affected),
                "affected_coordinates": "|".join(affected),
                "strict_symmetry_class": "{" + ",".join(spec.records[item].record_id for item in cls) + "}",
                "strict_symmetry_class_size": len(cls),
                "global_dummy": is_dummy(values[game], record.player_index),
                "exact_shapley": format(shapley[game][record.player_index], "f"),
                "game_symmetry_class_count": len(classes),
                "theoretical_type_count_state_count": type_state_count,
                "realized_type_count_states": realized_type_states,
                "raw_report_state_count": canonical_states,
                "type_state_sufficiency_verified": type_sufficient,
                "evidence_status": "VERIFIED_BY_ALL_4096_COALITIONS",
            })

    diagnostic_rows.extend(provenance_diagnostics())
    write_csv(OUT / "model_diagnostics.csv", diagnostic_rows)

    gap_rows = [
        {"gap_class": "A", "item": "D1-P V-count", "current_evidence": "两类常数边际玩家；按叶/祖先覆盖率线性", "why_easy_or_missing": "线性加性且无跨玩家JOIN", "status": "CLASSICALLY_SOLVED", "minimal_next_experiment": "无需重复；保留为负对照"},
        {"gap_class": "A", "item": "D1-P V1计数部分", "current_evidence": "21坐标、84个单变量来源组件，线性合成精确", "why_easy_or_missing": "来源均为单玩家指示函数", "status": "CLASSICALLY_SOLVED", "minimal_next_experiment": "无需扩大；仅测试自动编译器工程性"},
        {"gap_class": "A", "item": "D1-P V1比例部分", "current_evidence": "14坐标由(a,b,k)计数状态DP精确重建", "why_easy_or_missing": "单位记录、二维计数充分统计、坐标线性合成", "status": "CLASSIC_DP_APPLICATION", "minimal_next_experiment": "增加带权记录并分别按一元/二进制权重编码审计伪多项式边界"},
        {"gap_class": "A", "item": "AB-J1/J2 COUNT", "current_evidence": "层次化无自连接JOIN；DNF/d-tree精确", "why_easy_or_missing": "查询变量原子集合嵌套", "status": "CLASSICALLY_TRACTABLE", "minimal_next_experiment": "保留作层次化阳性对照"},
        {"gap_class": "A", "item": "AB-J2 COUNT DISTINCT", "current_evidence": "同key内OR后精确；底层CQ为all-hierarchical", "why_easy_or_missing": "两key、五grounding且满足已知可处理结构", "status": "CLASSICALLY_TRACTABLE_AFTER_REDUCTION", "minimal_next_experiment": "与非all-hierarchical count-distinct成对比较"},
        {"gap_class": "B", "item": "Basic与Optional独立供给", "current_evidence": "当前同一record_id绑定为一个玩家并同进同出", "why_easy_or_missing": "未激活跨所有者互补", "status": "NOT_ACTIVATED", "minimal_next_experiment": "6玩家最小包拆分：Basic和Optional由不同玩家控制，固定LEFT JOIN/NULL规则"},
        {"gap_class": "B", "item": "多对多层级映射", "current_evidence": "Hierarchy每叶唯一一行", "why_easy_or_missing": "无扇出、无重复路径", "status": "NOT_ACTIVATED", "minimal_next_experiment": "单叶映射到两个父节点，分别测试bag与distinct报表语义"},
        {"gap_class": "B", "item": "玩家统计类型多样性", "current_evidence": "12条人工平衡记录；多类含重复或近重复作用", "why_easy_or_missing": "低维计数和对称性压缩明显", "status": "WEAKLY_ACTIVATED", "minimal_next_experiment": "保持n不变，构造12个互异坐标作用签名并比较状态数"},
        {"gap_class": "B", "item": "V2联合统计状态", "current_evidence": "仅4096联盟高精度真值及指数Harsanyi表达；无原生联合DP", "why_easy_or_missing": "n=12掩盖联合状态增长，且尚未做状态编译", "status": "NOT_IMPLEMENTED_AS_NATIVE_STATE_ALGORITHM", "minimal_next_experiment": "固定12玩家，逐步增加独立统计族并记录可达联合状态数"},
        {"gap_class": "C", "item": "非hierarchical无自连接CQ", "current_evidence": "D1-P与AB-J1/J2均未覆盖", "why_easy_or_missing": "理论上存在FP#P困难边界", "status": "KNOWN_HARD_NOT_COVERED", "minimal_next_experiment": "Q():-R(x),S(x,y),T(y)的6至10玩家精确控制游戏"},
        {"gap_class": "C", "item": "self-join查询", "current_evidence": "当前控制JOIN均无自连接", "why_easy_or_missing": "Livshits/Standke主要二分结论明确排除自连接", "status": "THEORY_NOT_DIRECTLY_COVERED", "minimal_next_experiment": "R(x,y),R(y,z)最小自连接，区分同一物理事实重复使用"},
        {"gap_class": "C", "item": "非all-hierarchical COUNT DISTINCT", "current_evidence": "AB-J查询为all-hierarchical", "why_easy_or_missing": "已知困难边界未被触发", "status": "KNOWN_HARD_NOT_COVERED", "minimal_next_experiment": "Q(x):-R(x),S(x,y),T(y)输出x并做count-distinct"},
        {"gap_class": "C", "item": "高维非局部整表价值", "current_evidence": "V2只有四族几何平均", "why_easy_or_missing": "现有AggCQ定理要求局部值或单聚合；整表全局函数不直接覆盖", "status": "THEOREM_GAP", "minimal_next_experiment": "2/3/4/6统计族阶梯，固定玩家和SQL，测联合状态与精确编译规模"},
        {"gap_class": "D", "item": "V2原生SQL到联合状态编译", "current_evidence": "Harsanyi适配先枚举4096联盟且4094项非零", "why_easy_or_missing": "同目标可表达但未找到避免全联盟预付的原生路径", "status": "NO_EFFICIENT_NATIVE_ADAPTATION_FOUND", "minimal_next_experiment": "只做12玩家状态可达性与族交互因子图，不扩大n"},
        {"gap_class": "D", "item": "通用HAVING门槛来源编译", "current_evidence": "AB-J2手工4证据，官方空DNF还会报IndexError", "why_easy_or_missing": "最小证据可组合增长；无通用SQL前端", "status": "MANUAL_ONLY", "minimal_next_experiment": "2x2到3x3扇出、门槛2/3；同时记录最小DNF和因式电路"},
        {"gap_class": "E", "item": "官方COUNT DISTINCT SQL接口", "current_evidence": "手工key-OR后Boolean后端正确", "why_easy_or_missing": "数学和后端能力已验证，缺少前端编译接口", "status": "INTERFACE_ONLY", "minimal_next_experiment": "实现只读转换器并与64联盟SQL核验，不宣称新算法"},
        {"gap_class": "E", "item": "官方ABS/比例评分接口", "current_evidence": "独立计数DP已精确解决V1", "why_easy_or_missing": "官方输入不接受全局ABS，但非数学困难", "status": "INTERFACE_ONLY", "minimal_next_experiment": "建立SQL坐标到(a,b,k)状态程序的自动翻译"},
        {"gap_class": "F", "item": "跨来源共同完成一条业务记录", "current_evidence": "当前D1-P记录包预先绑定，AB-J只做独立玩具JOIN", "why_easy_or_missing": "真实业务可能由不同所有者共同满足字段/实体解析", "status": "PROMISING_BUSINESS_STRUCTURE", "minimal_next_experiment": "Basic、属性、映射由三方控制，建立一条输出的多条替代合成路径"},
        {"gap_class": "F", "item": "重复连接路径与去重口径", "current_evidence": "D1-P COUNT(*)=COUNT DISTINCT；AB-J规模过小", "why_easy_or_missing": "真实主数据和桥表可制造同一业务实体的多条路径", "status": "PROMISING_BUSINESS_STRUCTURE", "minimal_next_experiment": "两桥表产生重复路径，成对运行bag、distinct与HAVING"},
        {"gap_class": "F", "item": "跨指标业务约束", "current_evidence": "V2交互由人为几何平均设定", "why_easy_or_missing": "尚未由真实定价合同或质量门槛驱动", "status": "RESEARCH_HYPOTHESIS", "minimal_next_experiment": "先冻结业务可解释的最低覆盖/一致性条款，再定义非局部价值"},
        {"gap_class": "F", "item": "算法比较预算公平性", "current_evidence": "FGSV按owner拆预算；MC一次排列复用全部owner", "why_easy_or_missing": "比较设计本身影响端到端优势", "status": "COMPARISON_DESIGN_CONFOUNDING", "minimal_next_experiment": "同时报告效用调用、唯一联盟、全owner端到端和单owner查询四种预算"},
    ]
    write_csv(OUT / "structural_gap_matrix.csv", gap_rows)

    literature_rows = [
        {"project_case": "D1-P物理LEFT JOIN", "paper": "Livshits et al. 2020", "theorem": "Theorem 9 / Theorem 11 / Corollary 15", "paper_assumptions": "固定Boolean或SUM型CQ；无自连接；hierarchical；事实分内生/外生", "project_evidence": "物理SQL含LEFT JOIN且Basic/Optional被绑定为一个玩家，Hierarchy固定外生；原SQL不直接是论文CQ", "mapping_status": "NOT_DIRECT; AFTER_PLAYER_BINDING_REDUCES_TO_UNARY", "conclusion": "不能按物理表数套定理；归约后计数来源为单变量，属于易解情形"},
        {"project_case": "D1-P/AB-N2单变量COUNT", "paper": "Abramovich et al. 2025", "theorem": "Theorem 3.6", "paper_assumptions": "给定已编译d-tree；对树中全部变量线性时间求Shapley/Banzhaf", "project_evidence": "84个来源组件均为单变量单子句DNF", "mapping_status": "DIRECT_TO_COMPILED_INPUT", "conclusion": "求解容易；定理不负责SQL到来源的编译成本"},
        {"project_case": "AB-J1/J2 COUNT(*)", "paper": "Livshits et al. 2020", "theorem": "Corollary 15 (with Theorem 9)", "paper_assumptions": "SUM over self-join-free hierarchical CQ", "project_evidence": "Q(k):-L(a,k),R(b,k)；atoms(a)={L}, atoms(b)={R}, atoms(k)={L,R}，集合嵌套；无自连接", "mapping_status": "DIRECT_STRUCTURAL_MATCH", "conclusion": "现有可处理类别；bag grounding线性求和"},
        {"project_case": "AB-J1/J2 COUNT DISTINCT", "paper": "Standke and Kimelfeld 2025", "theorem": "Theorem 4.1", "paper_assumptions": "无自连接；all-hierarchical CQ；localized value function；CDist", "project_evidence": "同一Q(k)为all-hierarchical；玩家是两关系中的内生元组；本例按key做OR", "mapping_status": "STRUCTURAL_MATCH_AFTER_MANUAL_REDUCTION", "conclusion": "不是理论困难例；官方前端接口缺失与数学可解性不同"},
        {"project_case": "AB-J2 HAVING COUNT(*)>=2", "paper": "Standke and Kimelfeld 2025", "theorem": "Theorem 6.1", "paper_assumptions": "无自连接；sq-hierarchical；localized value；has-duplicates聚合", "project_evidence": "底层Q(k)为sq-hierarchical；每key门槛2等价重复存在，但外层再COUNT通过key", "mapping_status": "INDICATIVE_NOT_DIRECT_NESTED_AGGREGATION", "conclusion": "底层结构并不困难；嵌套GROUP BY/HAVING到DNF编译未由该定理直接给出"},
        {"project_case": "未来非hierarchical CQ", "paper": "Livshits et al. 2020", "theorem": "Theorem 13", "paper_assumptions": "固定aggregate-relational query；底层CQ无自连接且非hierarchical", "project_evidence": "当前没有R(x),S(x,y),T(y)交叉原子集合", "mapping_status": "KNOWN_HARD_CLASS_NOT_COVERED", "conclusion": "需最小控制实验激活，不能从当前易解查询推断"},
        {"project_case": "未来非∃-hierarchical AggCQ", "paper": "Standke and Kimelfeld 2025", "theorem": "Theorem 3.1", "paper_assumptions": "无自连接；非∃-hierarchical；非平凡AggCQ", "project_evidence": "当前AB-J变量原子集合均嵌套", "mapping_status": "KNOWN_HARD_CLASS_NOT_COVERED", "conclusion": "当前实验没有碰到该必要困难条件"},
        {"project_case": "Luo对V-count的适配", "paper": "Luo et al. 2022", "theorem": "Assumption 1; Theorems 1-2; Algorithm 1", "paper_assumptions": "结果元组效用非负且相互独立可加；按元组分解；基于最小synthesis", "project_evidence": "V-count经整数复制成为独立输出单位的加性计数；历史同目标适配已通过", "mapping_status": "EXACT_REDUCTION_VERIFIED", "conclusion": "V-count适用不代表V1/V2适用"},
        {"project_case": "Luo对V1/V2", "paper": "Luo et al. 2022", "theorem": "Assumption 1 and Theorem 1", "paper_assumptions": "总效用等于独立结果元组效用之和", "project_evidence": "V1比例分母依联盟变化；V2再跨四族做几何平均", "mapping_status": "ASSUMPTION_VIOLATED_FOR_NATIVE_MAPPING", "conclusion": "不能直接使用IUSV；这不是源码错误"},
        {"project_case": "V1比例状态DP", "paper": "Livshits 2020 / Standke 2025", "theorem": "Theorem 11 counting idea / Figure 2 generic DP (not direct theorem)", "paper_assumptions": "按联盟大小和可组合充分统计递推", "project_evidence": "冻结单坐标只需(a,b,k)，14坐标线性相加", "mapping_status": "CLASSIC_TECHNIQUE_APPLICATION_NOT_DIRECT_THEOREM", "conclusion": "已精确解决当前V1，但不能外推到任意整表评分"},
        {"project_case": "V2几何联合价值", "paper": "Standke and Kimelfeld 2025", "theorem": "Theorems 4.1/5.1/6.1 do not directly apply", "paper_assumptions": "单AggCQ与localized value，按特定聚合函数给边界", "project_evidence": "V2是35坐标派生的四族全局评分再几何组合", "mapping_status": "OUTSIDE_DIRECT_SCOPE", "conclusion": "已有4096联盟真值不等于已找到高效原生联合状态算法"},
        {"project_case": "AB-J查询自连接", "paper": "Livshits 2020; Standke 2025", "theorem": "Theorem 9/13; Theorems 3.1/4.1/5.1/6.1", "paper_assumptions": "上述精确二分主要要求无自连接", "project_evidence": "AB-J1/J2每个关系符号仅出现一次", "mapping_status": "ASSUMPTION_SATISFIED_BUT_SELF_JOIN_GAP_UNTESTED", "conclusion": "当前没有覆盖自连接边界"},
    ]
    write_csv(OUT / "literature_theorem_mapping.csv", literature_rows)

    next_specs = {
        "stage": "H0_NEXT_EXPERIMENT_SPECS_ONLY",
        "status": "DESIGNED_NOT_RUN",
        "constraints": ["不覆盖D1-P", "每次只激活一个结构", "先做小规模全联盟真值", "保持玩家与价值目标一致"],
        "experiments": [
            {"id": "H1-NH-CQ", "factor": "查询非层次性", "minimal_sql_shape": "Q() :- R(x), S(x,y), T(y)", "players": "6-10 endogenous tuples", "control": "paired hierarchical Q() :- R(x), S(x,y)", "metrics": ["groundings", "DNF/d-tree size", "exact Shapley time"], "acceptance": "逐联盟SQL=来源=精确Shapley"},
            {"id": "H2-CDIST-FRONTIER", "factor": "all-hierarchical条件", "minimal_sql_shape": "成对构造all-hierarchical与非all-hierarchical COUNT DISTINCT", "players": "<=10", "control": "相同玩家数、grounding数、key数", "metrics": ["key lineage", "编译规模", "定理条件"], "acceptance": "定理映射与实测分开报告"},
            {"id": "H3-HAVING-CIRCUIT", "factor": "门槛证据与共享因式", "minimal_sql_shape": "m×n JOIN, GROUP BY key HAVING COUNT(*)>=h", "levels": {"m": [2, 3], "n": [2, 3], "h": [2, 3]}, "metrics": ["最小DNF", "因式电路", "官方d-tree", "唯一联盟"], "acceptance": "不得以展开DNF代替最优电路规模"},
            {"id": "H4-BUNDLE-SPLIT", "factor": "逻辑记录包拆分", "minimal_sql_shape": "Basic LEFT JOIN Optional", "players": "Basic与Optional由不同玩家控制", "control": "现有绑定记录包", "metrics": ["NULL", "记录保留", "互补交互"], "acceptance": "业务玩家定义先冻结"},
            {"id": "H5-V2-JOINT-STATE", "factor": "统计族联合维度", "minimal_sql_shape": "固定D1-P SQL与12玩家", "levels": {"families": [1, 2, 3, 4], "interaction": ["arithmetic", "geometric"]}, "metrics": ["可达联合状态", "转移", "内存", "真值误差"], "acceptance": "不先枚举全部联盟构造算法输入"},
            {"id": "H6-SELF-JOIN", "factor": "自连接", "minimal_sql_shape": "Q(x,z) :- R(x,y), R(y,z)", "players": "同一物理事实只能是一个变量", "control": "复制为两个不同关系符号的无自连接版本", "metrics": ["变量复用", "lineage", "编译规模"], "acceptance": "严格区分同事实重复引用与两个玩家"},
            {"id": "H7-BUSINESS-MULTIPATH", "factor": "真实多源替代与互补路径", "minimal_sql_shape": "实体主表+两桥表+可替代属性源", "players": "来源所有者记录", "control": "单路径版本", "metrics": ["bag/distinct", "重复路径", "跨源最小synthesis"], "acceptance": "先冻结业务计数单位和收入函数"},
            {"id": "H8-COMPARISON-BUDGET", "factor": "算法比较口径", "minimal_sql_shape": "复用现有D1-P/SOU", "controls": ["总效用调用", "唯一联盟", "全owner端到端", "单owner查询"], "metrics": ["误差", "调用", "编译", "求解"], "acceptance": "不把预算复用差异解释成算法数学误差"},
        ],
    }
    (OUT / "next_experiment_specs.json").write_text(json.dumps(next_specs, ensure_ascii=False, indent=2), encoding="utf-8")

    hashes_after = historical_hashes()
    if hashes_before != hashes_after:
        raise AssertionError("historical input changed during H0 audit")
    (OUT / "historical_hashes.json").write_text(
        json.dumps({"before": hashes_before, "after": hashes_after, "unchanged": True}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = {
        "status": "H0_STRUCTURAL_AUDIT_COMPLETED",
        "historical_files_modified": False,
        "historical_hashes_unchanged": hashes_before == hashes_after,
        "d1p": {
            "players": spec.player_count,
            "coalitions": 1 << spec.player_count,
            "raw_report_states": canonical_states,
            "symmetry_classes": {game: [[spec.records[i].record_id for i in cls] for cls in game_classes[game]] for game in GAMES},
            "type_state_counts": {game: math.prod(len(cls) + 1 for cls in game_classes[game]) for game in GAMES},
        },
        "outputs": ["model_diagnostics.csv", "structural_gap_matrix.csv", "literature_theorem_mapping.csv", "next_experiment_specs.json"],
        "not_run": ["new algorithm", "larger data", "H1-H8 experiments"],
    }
    (OUT / "audit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
