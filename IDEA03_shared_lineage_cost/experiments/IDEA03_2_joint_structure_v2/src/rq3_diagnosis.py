from __future__ import annotations

import hashlib
import math
import sys
import time
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from rq3_core import (
    Fixture,
    PeakRSS,
    evidence_deltas,
    player_rows,
    report_python,
    witnesses,
)


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = Path(__file__).resolve().parents[4]
OFFICIAL_LEXASHAP = (
    WORKSPACE
    / "aggregate_report_shapley"
    / "external"
    / "abramovich"
    / "source"
    / "LExaBan-LExaShap-main"
)
if str(OFFICIAL_LEXASHAP) not in sys.path:
    sys.path.insert(0, str(OFFICIAL_LEXASHAP))

from Algorithms.LExaShap.ShapleyCircuit import DNFCircuit  # noqa: E402


Poly = dict[int, Fraction]
DNF = tuple[frozenset[int], ...]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_poly(poly: Poly) -> Poly:
    return {mask: value for mask, value in poly.items() if value}


def poly_add(*polys: Poly) -> Poly:
    result: defaultdict[int, Fraction] = defaultdict(Fraction)
    for poly in polys:
        for mask, coefficient in poly.items():
            result[mask] += coefficient
    return clean_poly(dict(result))


def poly_scale(poly: Poly, scale: Fraction) -> Poly:
    return clean_poly({mask: coefficient * scale for mask, coefficient in poly.items()})


def poly_multiply(left: Poly, right: Poly) -> Poly:
    result: defaultdict[int, Fraction] = defaultdict(Fraction)
    for left_mask, left_coefficient in left.items():
        for right_mask, right_coefficient in right.items():
            result[left_mask | right_mask] += left_coefficient * right_coefficient
    return clean_poly(dict(result))


def poly_value(poly: Poly, coalition_mask: int) -> Fraction:
    return sum(
        (coefficient for term, coefficient in poly.items() if coalition_mask & term == term),
        Fraction(0),
    )


def poly_shapley(poly: Poly, n: int) -> list[Fraction]:
    allocation = [Fraction(0) for _ in range(n)]
    for term, coefficient in poly.items():
        if term == 0:
            continue
        size = term.bit_count()
        share = coefficient / size
        for player in range(n):
            if term & (1 << player):
                allocation[player] += share
    return allocation


def _witness_by_sid(fixture: Fixture):
    return {witness.sid: witness for witness in witnesses(fixture)}


def indicator_dnf(fixture: Fixture, province: str, eid: str) -> DNF:
    clauses = [frozenset(w.players) for w in witnesses(fixture) if w.province == province and w.eid == eid]
    return minimize_dnf(clauses)


def witness_dnf(fixture: Fixture, sid: str) -> DNF:
    witness = _witness_by_sid(fixture)[sid]
    return (frozenset(witness.players),)


def minimize_dnf(clauses: Iterable[frozenset[int]]) -> DNF:
    unique = sorted(set(clauses), key=lambda clause: (len(clause), tuple(sorted(clause))))
    minimal: list[frozenset[int]] = []
    for clause in unique:
        if not any(existing <= clause for existing in minimal):
            minimal.append(clause)
    return tuple(minimal)


def and_dnf(left: DNF, right: DNF) -> DNF:
    return minimize_dnf(a | b for a in left for b in right)


def dnf_value(dnf: DNF, coalition_mask: int) -> int:
    selected = {player for player in range(coalition_mask.bit_length()) if coalition_mask & (1 << player)}
    return int(any(clause <= selected for clause in dnf))


def dnf_to_poly(dnf: DNF) -> Poly:
    """Monotone DNF to its exact multilinear inclusion-exclusion polynomial."""
    result: defaultdict[int, Fraction] = defaultdict(Fraction)
    clause_count = len(dnf)
    for subset in range(1, 1 << clause_count):
        union_mask = 0
        for index, clause in enumerate(dnf):
            if subset & (1 << index):
                for player in clause:
                    union_mask |= 1 << player
        result[union_mask] += Fraction(1 if subset.bit_count() % 2 else -1)
    return clean_poly(dict(result))


def coordinate_polynomials(fixture: Fixture) -> dict[str, Poly]:
    ws = witnesses(fixture)
    output: dict[str, Poly] = {}
    for province in ("PA", "PB"):
        indicators = []
        for eid in sorted({w.eid for w in ws if w.province == province}):
            indicators.append(dnf_to_poly(indicator_dnf(fixture, province, eid)))
        output[f"{province}.enterprise_count"] = poly_add(*indicators)
    mfg_terms: defaultdict[int, Fraction] = defaultdict(Fraction)
    for witness in ws:
        if witness.province == "PA" and witness.industry == "manufacturing":
            mfg_terms[witness.required_mask] += Fraction(witness.workers)
    output["PA.mfg_workers"] = clean_poly(dict(mfg_terms))
    return output


def paired_full_references(low: Fixture, high: Fixture) -> dict[str, Fraction]:
    reports = [report_python(fixture, (1 << fixture.n) - 1) for fixture in (low, high)]
    return {
        "PA.enterprise_count": Fraction(max(int(report[("PA", "enterprise_count")]) for report in reports)),
        "PB.enterprise_count": Fraction(max(int(report[("PB", "enterprise_count")]) for report in reports)),
        "PA.mfg_workers": Fraction(max(int(report[("PA", "mfg_workers")]) for report in reports)),
    }


def value_polynomials(
    fixture: Fixture, references: dict[str, Fraction], revenue: Fraction, lam: Fraction
) -> tuple[dict[str, Poly], list[dict[str, Any]]]:
    coordinates = coordinate_polynomials(fixture)
    pa_e = poly_scale(coordinates["PA.enterprise_count"], 1 / references["PA.enterprise_count"])
    pb_e = poly_scale(coordinates["PB.enterprise_count"], 1 / references["PB.enterprise_count"])
    pa_mfg = poly_scale(coordinates["PA.mfg_workers"], 1 / references["PA.mfg_workers"])
    local_product = poly_multiply(pa_e, pa_mfg)
    cross_product = poly_multiply(pa_e, pb_e)
    values = {
        "local_add": poly_scale(poly_add(pa_e, pa_mfg), revenue / 2),
        "local_joint": poly_add(
            poly_scale(poly_add(pa_e, pa_mfg), revenue * (1 - lam) / 2),
            poly_scale(local_product, revenue * lam),
        ),
        "cross_add": poly_scale(poly_add(pa_e, pb_e), revenue / 2),
        "cross_joint": poly_add(
            poly_scale(poly_add(pa_e, pb_e), revenue * (1 - lam) / 2),
            poly_scale(cross_product, revenue * lam),
        ),
    }
    diagnostics = []
    for name, poly in values.items():
        diagnostics.append(
            {
                "value_name": name,
                "coordinates_total": 35,
                "coordinates_used": 2,
                "coordinate_use_rate": 2 / 35,
                "nonzero_harsanyi_terms": len(poly),
                "maximum_term_degree": max((mask.bit_count() for mask in poly), default=0),
                "total_term_variable_occurrences": sum(mask.bit_count() for mask in poly),
                "positive_terms": sum(value > 0 for value in poly.values()),
                "negative_terms": sum(value < 0 for value in poly.values()),
            }
        )
    return values, diagnostics


def value_from_report(
    fixture: Fixture,
    coalition_mask: int,
    value_name: str,
    references: dict[str, Fraction],
    revenue: Fraction,
    lam: Fraction,
) -> Fraction:
    report = report_python(fixture, coalition_mask)
    pa_e = Fraction(int(report[("PA", "enterprise_count")])) / references["PA.enterprise_count"]
    pb_e = Fraction(int(report[("PB", "enterprise_count")])) / references["PB.enterprise_count"]
    pa_mfg = Fraction(int(report[("PA", "mfg_workers")])) / references["PA.mfg_workers"]
    if value_name == "local_add":
        return revenue * (pa_e + pa_mfg) / 2
    if value_name == "local_joint":
        return revenue * ((1 - lam) * (pa_e + pa_mfg) / 2 + lam * pa_e * pa_mfg)
    if value_name == "cross_add":
        return revenue * (pa_e + pb_e) / 2
    if value_name == "cross_joint":
        return revenue * ((1 - lam) * (pa_e + pb_e) / 2 + lam * pa_e * pb_e)
    raise KeyError(value_name)


def value_components(
    fixture: Fixture,
    references: dict[str, Fraction],
    revenue: Fraction,
    lam: Fraction,
) -> dict[str, list[tuple[Fraction, DNF, str]]]:
    ws = witnesses(fixture)
    enterprise_dnfs = {
        (province, eid): indicator_dnf(fixture, province, eid)
        for province in ("PA", "PB")
        for eid in sorted({w.eid for w in ws if w.province == province})
    }
    mfg = [(w, (frozenset(w.players),)) for w in ws if w.province == "PA" and w.industry == "manufacturing"]

    def linear(scope: str, factor: Fraction):
        rows: list[tuple[Fraction, DNF, str]] = []
        for (province, eid), dnf in enterprise_dnfs.items():
            if province == "PA" or (scope == "cross" and province == "PB"):
                ref = references[f"{province}.enterprise_count"]
                rows.append((revenue * factor / ref, dnf, f"{province}.enterprise:{eid}"))
        if scope == "local":
            for witness, dnf in mfg:
                rows.append((revenue * factor * witness.workers / references["PA.mfg_workers"], dnf, f"PA.mfg:{witness.sid}"))
        return rows

    output = {
        "local_add": linear("local", Fraction(1, 2)),
        "cross_add": linear("cross", Fraction(1, 2)),
        "local_joint": linear("local", (1 - lam) / 2),
        "cross_joint": linear("cross", (1 - lam) / 2),
    }
    for (province, eid), dnf in enterprise_dnfs.items():
        if province != "PA":
            continue
        for witness, witness_clause in mfg:
            output["local_joint"].append(
                (
                    revenue * lam * witness.workers
                    / (references["PA.enterprise_count"] * references["PA.mfg_workers"]),
                    and_dnf(dnf, witness_clause),
                    f"PA.enterprise:{eid}&PA.mfg:{witness.sid}",
                )
            )
    pa = [(eid, dnf) for (province, eid), dnf in enterprise_dnfs.items() if province == "PA"]
    pb = [(eid, dnf) for (province, eid), dnf in enterprise_dnfs.items() if province == "PB"]
    for eid_a, dnf_a in pa:
        for eid_b, dnf_b in pb:
            output["cross_joint"].append(
                (
                    revenue * lam
                    / (references["PA.enterprise_count"] * references["PB.enterprise_count"]),
                    and_dnf(dnf_a, dnf_b),
                    f"PA.enterprise:{eid_a}&PB.enterprise:{eid_b}",
                )
            )
    return output


def normalized_dnf_key(dnf: DNF) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(sorted(clause)) for clause in dnf)


def official_lexashap_boolean(dnf: DNF) -> dict[int, float]:
    circuit = DNFCircuit([set(str(player) for player in clause) for clause in dnf])
    n = len(circuit.vars)
    scale = (2**n) / math.factorial(n)
    output: dict[int, float] = {}
    for variable in circuit.vars:
        label = int(str(variable.label))
        grad = [float(item) for item in variable.grad]
        probability = [float(item) for item in variable.prob]
        output[label] = sum(g * p for g, p in zip(grad, probability, strict=True)) * scale
    return output


def lexashap_component_allocation(
    fixture: Fixture, components: list[tuple[Fraction, DNF, str]]
) -> tuple[np.ndarray, dict[str, Any]]:
    grouped: defaultdict[tuple[tuple[int, ...], ...], Fraction] = defaultdict(Fraction)
    dnf_by_key: dict[tuple[tuple[int, ...], ...], DNF] = {}
    raw_clause_count = 0
    for coefficient, dnf, _label in components:
        key = normalized_dnf_key(dnf)
        grouped[key] += coefficient
        dnf_by_key[key] = dnf
        raw_clause_count += len(dnf)
    grouped = defaultdict(Fraction, {key: value for key, value in grouped.items() if value})
    allocation = np.zeros(fixture.n, dtype=np.float64)
    started = time.perf_counter()
    with PeakRSS() as rss:
        for key, coefficient in grouped.items():
            for player, value in official_lexashap_boolean(dnf_by_key[key]).items():
                allocation[player] += float(coefficient) * value
    elapsed = time.perf_counter() - started
    return allocation, {
        "method": "OFFICIAL_LEXASHAP_BOOLEAN_COMPONENTS",
        "status": "VERIFIED",
        "raw_components": len(components),
        "unique_boolean_components": len(grouped),
        "raw_dnf_clauses": raw_clause_count,
        "unique_dnf_clauses": sum(len(dnf_by_key[key]) for key in grouped),
        "maximum_component_variables": max((len({p for clause in dnf_by_key[key] for p in clause}) for key in grouped), default=0),
        "compile_solve_seconds": elapsed,
        "peak_rss_bytes": rss.peak,
    }


def sparse_harsanyi_allocation(fixture: Fixture, poly: Poly) -> tuple[np.ndarray, dict[str, Any]]:
    started = time.perf_counter()
    with PeakRSS() as rss:
        allocation = np.asarray([float(value) for value in poly_shapley(poly, fixture.n)], dtype=np.float64)
    elapsed = time.perf_counter() - started
    return allocation, {
        "method": "SPARSE_HARSANYI_PROVENANCE",
        "status": "VERIFIED",
        "nonzero_harsanyi_terms": len(poly),
        "maximum_term_degree": max((mask.bit_count() for mask in poly), default=0),
        "compile_solve_seconds": elapsed,
        "peak_rss_bytes": rss.peak,
    }


def component_value(components: list[tuple[Fraction, DNF, str]], coalition_mask: int) -> Fraction:
    return sum(
        (coefficient * dnf_value(dnf, coalition_mask) for coefficient, dnf, _label in components),
        Fraction(0),
    )


def proof_profile_rows(fixture: Fixture) -> list[dict[str, Any]]:
    ws = witnesses(fixture)
    counts = Counter((w.eid, w.province) for w in ws)
    degree = Counter(w.eid for w in ws)
    rows = []
    for eid in sorted(degree):
        a = counts[(eid, "PA")]
        b = counts[(eid, "PB")]
        local_a = 2**a - 1 if a else 0
        local_b = 2**b - 1 if b else 0
        cross = local_a * local_b
        rows.append(
            {
                "pair_id": fixture.pair_id,
                "structure": fixture.structure,
                "eid": eid,
                "degree": degree[eid],
                "proofs_PA": a,
                "proofs_PB": b,
                "cross_province": bool(a and b),
                "local_or_terms_PA": local_a,
                "local_or_terms_PB": local_b,
                "same_entity_cross_product_terms": cross,
                "degree_identity_total": local_a + local_b + cross,
                "degree_identity_expected": 2 ** degree[eid] - 1,
                "alternative_proof_pairs_PA": math.comb(a, 2),
                "alternative_proof_pairs_PB": math.comb(b, 2),
                "shared_players_per_same_entity_proof_pair": 1,
            }
        )
    return rows


def lineage_structure_row(fixture: Fixture) -> dict[str, Any]:
    ws = witnesses(fixture)
    degree = Counter(w.eid for w in ws)
    e_count = len(fixture.e)
    incidence_nodes = fixture.n + len(ws)
    incidence_edges = 3 * len(ws)
    incidence_components = e_count
    cycle_rank = incidence_edges - incidence_nodes + incidence_components
    same_entity_pairs = sum(math.comb(value, 2) for value in degree.values())
    all_pairs = math.comb(len(ws), 2)
    component_state_sizes = {eid: 2 * (3 ** value) - (2 ** value) for eid, value in degree.items()}
    terminal_states = math.prod(component_state_sizes.values())
    return {
        "pair_id": fixture.pair_id,
        "structure": fixture.structure,
        "n": fixture.n,
        "enterprise_components": e_count,
        "witnesses": len(ws),
        "enterprise_degree_signature": ";".join(map(str, sorted(degree.values()))),
        "maximum_enterprise_degree": max(degree.values()),
        "h3_component_state_sizes": ";".join(
            f"{eid}:{component_state_sizes[eid]}" for eid in sorted(component_state_sizes)
        ),
        "h3_terminal_states_closed_form": terminal_states,
        "h3_terminal_state_formula": "product_e(2*3^degree_e-2^degree_e)",
        "incidence_nodes": incidence_nodes,
        "incidence_edges": incidence_edges,
        "incidence_cycle_rank": cycle_rank,
        "incidence_is_forest": cycle_rank == 0,
        "incidence_treewidth_exact": 1,
        "primal_treewidth_exact": 2,
        "same_entity_witness_pairs": same_entity_pairs,
        "different_entity_witness_pairs": all_pairs - same_entity_pairs,
        "same_entity_pair_shared_players": 1,
        "different_entity_pair_shared_players": 0,
        "structural_reason": "enterprise-centered 3-uniform hyperedge stars; triangles glued at E variables",
    }


def evidence_layer_profile(fixture: Fixture, cap: int) -> list[dict[str, Any]]:
    deltas = evidence_deltas(fixture)
    players = player_rows(fixture)
    states = {(0,) * len(witnesses(fixture))}
    rows = [{
        "pair_id": fixture.pair_id,
        "structure": fixture.structure,
        "layer": 0,
        "player_id": "START",
        "relation": "NONE",
        "states": 1,
        "status": "VERIFIED",
        "value_function_calls": 0,
    }]
    for layer, delta in enumerate(deltas, start=1):
        next_states = set(states)
        next_states.update(tuple(a + b for a, b in zip(state, delta, strict=True)) for state in states)
        count = len(next_states)
        evidence_hist = [0.0, 0.0, 0.0, 0.0]
        for state in next_states:
            for value in state:
                evidence_hist[value] += 1
        denominator = count * len(deltas[0])
        row = {
            "pair_id": fixture.pair_id,
            "structure": fixture.structure,
            "layer": layer,
            "player_id": players[layer - 1]["player_id"],
            "relation": players[layer - 1]["relation"],
            "states": count,
            "mean_witness_fraction_evidence_0": evidence_hist[0] / denominator,
            "mean_witness_fraction_evidence_1": evidence_hist[1] / denominator,
            "mean_witness_fraction_evidence_2": evidence_hist[2] / denominator,
            "mean_witness_fraction_evidence_3": evidence_hist[3] / denominator,
            "status": "RESOURCE_LIMIT" if count > cap else "VERIFIED",
            "value_function_calls": 0,
        }
        rows.append(row)
        if count > cap:
            break
        states = next_states
    return rows


def micro_control_rows() -> list[dict[str, Any]]:
    profiles = {
        "degree2_low": ((2, 0), (0, 2)),
        "degree2_cross": ((1, 1), (1, 1)),
        "q2_degree4_unbalanced": ((1, 3), (3, 1)),
        "q2_degree4_balanced": ((2, 2), (2, 2)),
        "fixed_LX_q1": ((0, 1), (0, 3), (3, 0), (3, 2)),
        "fixed_LX_q3": ((0, 1), (1, 2), (1, 2), (4, 1)),
    }
    rows = []
    for name, counts in profiles.items():
        degrees = [a + b for a, b in counts]
        local = sum((2**a - 1 if a else 0) + (2**b - 1 if b else 0) for a, b in counts)
        cross = sum((2**a - 1 if a else 0) * (2**b - 1 if b else 0) for a, b in counts)
        rows.append(
            {
                "control_id": name,
                "regional_counts": ";".join(f"{a}:{b}" for a, b in counts),
                "degree_signature": ";".join(map(str, sorted(degrees))),
                "cross_shared_enterprises": sum(bool(a and b) for a, b in counts),
                "local_or_terms": local,
                "same_entity_cross_product_terms": cross,
                "conserved_total": local + cross,
                "expected_from_degrees": sum(2**degree - 1 for degree in degrees),
            }
        )
    return rows


def official_source_manifest() -> dict[str, Any]:
    source = OFFICIAL_LEXASHAP / "Algorithms" / "LExaShap" / "ShapleyCircuit.py"
    return {
        "official_source_root": str(OFFICIAL_LEXASHAP),
        "official_source_file": str(source),
        "official_source_sha256": file_sha256(source),
        "adapter_contract": "weighted linear combination of exact Boolean DNF component Shapley values",
    }
