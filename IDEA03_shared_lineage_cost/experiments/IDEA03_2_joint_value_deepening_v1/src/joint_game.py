from __future__ import annotations

import itertools
import math
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable


NODES = ("NAT", "PA", "PB", "A1", "A2", "B1", "B2")
CITY_PROVINCE = {"A1": "PA", "A2": "PA", "B1": "PB", "B2": "PB"}
METRICS = ("enterprise_count", "site_count", "workers", "mfg_workers", "mfg_share")
DNF = tuple[frozenset[int], ...]


@dataclass(frozen=True)
class Player:
    index: int
    player_id: str
    relation: str
    key: str


@dataclass(frozen=True)
class Site:
    sid: str
    eid: str
    city: str | None
    industry: str
    workers: int
    e_player: int
    b_player: int
    h_player: int


@dataclass(frozen=True)
class RegionLink:
    rid: str
    object_id: str
    city: str
    player: int


@dataclass(frozen=True)
class Game:
    game_id: str
    query_version: str
    players: tuple[Player, ...]
    sites: tuple[Site, ...]
    links: tuple[RegionLink, ...]
    thresholds: tuple[int, int] = (1, 1)

    @property
    def n(self) -> int:
        return len(self.players)


def _add_player(players: list[Player], relation: str, key: str) -> int:
    index = len(players)
    players.append(Player(index, f"{relation}:{key}", relation, key))
    return index


def build_game(query_version: str, distribution: str = "base") -> Game:
    """Small frozen fixtures. F1/F2 use the same business facts but distinct Q versions."""
    if query_version not in {"F0_EBH", "F1_SITE_LINK", "F2_ENTITY_LINK"}:
        raise ValueError(query_version)
    players: list[Player] = []
    e_players = {eid: _add_player(players, "E", eid) for eid in ("E1", "E2")}
    rows = (
        ("S1", "E1", "A1", "manufacturing", 8),
        ("S2", "E1", "A2", "service", 12),
        ("S3", "E2", "B1", "manufacturing", 15),
        ("S4", "E2", "B2", "service", 5),
    )
    b_players = {sid: _add_player(players, "B", sid) for sid, *_ in rows}
    h_players = {sid: _add_player(players, "H", sid) for sid, *_ in rows}
    sites = tuple(
        Site(
            sid=sid,
            eid=eid,
            city=city if query_version == "F0_EBH" else None,
            industry=industry,
            workers=workers,
            e_player=e_players[eid],
            b_player=b_players[sid],
            h_player=h_players[sid],
        )
        for sid, eid, city, industry, workers in rows
    )
    links: list[RegionLink] = []
    if query_version == "F1_SITE_LINK":
        base = [("S1", "A1"), ("S2", "A2"), ("S3", "B1"), ("S4", "B2")]
        extras = {
            "balanced": [("S1", "A1"), ("S3", "B1")],
            "concentrated": [("S1", "A1"), ("S1", "A1")],
            "base": [("S1", "A1"), ("S3", "B1")],
        }[distribution]
        for serial, (sid, city) in enumerate(base + extras, 1):
            rid = f"R{serial}"
            links.append(RegionLink(rid, sid, city, _add_player(players, "R1", rid)))
    elif query_version == "F2_ENTITY_LINK":
        entries = {
            "balanced": [("E1", "A1"), ("E1", "A1"), ("E2", "B1"), ("E2", "B1")],
            "concentrated": [("E1", "A1"), ("E1", "A1"), ("E1", "A1"), ("E2", "B1")],
            "base": [("E1", "A1"), ("E1", "A1"), ("E2", "B1"), ("E2", "B1")],
        }[distribution]
        for serial, (eid, city) in enumerate(entries, 1):
            rid = f"R{serial}"
            links.append(RegionLink(rid, eid, city, _add_player(players, "R2", rid)))
    return Game(f"{query_version}_{distribution}", query_version, tuple(players), sites, tuple(links))


def site_city_dnf(game: Game, site: Site, city: str) -> DNF:
    common = {site.e_player, site.b_player, site.h_player}
    if game.query_version == "F0_EBH":
        return (frozenset(common),) if site.city == city else ()
    if game.query_version == "F1_SITE_LINK":
        candidates = [link for link in game.links if link.object_id == site.sid and link.city == city]
    else:
        candidates = [link for link in game.links if link.object_id == site.eid and link.city == city]
    return minimize_dnf(frozenset(common | {link.player}) for link in candidates)


def minimize_dnf(clauses: Iterable[frozenset[int]]) -> DNF:
    ordered = sorted(set(clauses), key=lambda item: (len(item), tuple(sorted(item))))
    result: list[frozenset[int]] = []
    for clause in ordered:
        if not any(existing <= clause for existing in result):
            result.append(clause)
    return tuple(result)


def or_dnf(*dnfs: DNF) -> DNF:
    return minimize_dnf(clause for dnf in dnfs for clause in dnf)


def and_dnf(*dnfs: DNF) -> DNF:
    if any(not dnf for dnf in dnfs):
        return ()
    clauses: Iterable[frozenset[int]] = (frozenset(),)
    for dnf in dnfs:
        clauses = (left | right for left in clauses for right in dnf)
        clauses = minimize_dnf(clauses)
    return minimize_dnf(clauses)


def dnf_value(dnf: DNF, mask: int) -> int:
    return int(any(all(mask & (1 << player) for player in clause) for clause in dnf))


def active_rows(game: Game, mask: int) -> list[tuple[str, str, str, str, int]]:
    rows: set[tuple[str, str, str, str, int]] = set()
    for site in game.sites:
        for city in CITY_PROVINCE:
            if dnf_value(site_city_dnf(game, site, city), mask):
                rows.add((site.sid, site.eid, city, site.industry, site.workers))
    return sorted(rows)


def report_python(game: Game, mask: int) -> dict[tuple[str, str], int | Fraction | None]:
    by_node: dict[str, list[tuple[str, str, str, str, int]]] = {node: [] for node in NODES}
    for row in active_rows(game, mask):
        city = row[2]
        for node in ("NAT", CITY_PROVINCE[city], city):
            by_node[node].append(row)
    output: dict[tuple[str, str], int | Fraction | None] = {}
    for node, rows in by_node.items():
        enterprise = len({row[1] for row in rows})
        site_count = len({row[0] for row in rows})
        workers = sum(row[4] for row in rows)
        mfg = sum(row[4] for row in rows if row[3] == "manufacturing")
        output[(node, "enterprise_count")] = enterprise
        output[(node, "site_count")] = site_count
        output[(node, "workers")] = workers
        output[(node, "mfg_workers")] = mfg
        output[(node, "mfg_share")] = None if workers == 0 else Fraction(mfg, workers)
    return output


def sufficient_statistics(game: Game, mask: int) -> tuple[int, int, int, int, int, int]:
    report = report_python(game, mask)
    return tuple(
        int(report[(province, metric)] or 0)
        for province in ("PA", "PB")
        for metric in ("enterprise_count", "mfg_workers", "workers")
    )  # C_A,M_A,W_A,C_B,M_B,W_B


def value(game: Game, mask: int, value_name: str) -> Fraction:
    ca, ma, wa, cb, mb, wb = sufficient_statistics(game, mask)
    ta, tb = int(ca >= game.thresholds[0]), int(cb >= game.thresholds[1])
    ra = Fraction(ma, wa) if wa else Fraction(0)
    rb = Fraction(mb, wb) if wb else Fraction(0)
    if value_name == "G0":
        return Fraction(ta + tb, 4) + (ra + rb) / 4
    if value_name == "G1":
        return (ta * ra + tb * rb) / 2
    if value_name == "G2":
        return Fraction(ta * tb, 2) * (ra + rb)
    raise KeyError(value_name)


def exact_shapley(game: Game, value_name: str) -> tuple[list[Fraction], list[Fraction]]:
    n = game.n
    values = [value(game, mask, value_name) for mask in range(1 << n)]
    factorial = [math.factorial(i) for i in range(n + 1)]
    denom = factorial[n]
    allocation = [Fraction(0) for _ in range(n)]
    for player in range(n):
        bit = 1 << player
        for mask in range(1 << n):
            if mask & bit:
                continue
            k = mask.bit_count()
            weight = Fraction(factorial[k] * factorial[n - k - 1], denom)
            allocation[player] += weight * (values[mask | bit] - values[mask])
    return allocation, values


def _object_indicator_dnfs(game: Game, province: str, kind: str) -> list[tuple[str, int, DNF]]:
    rows: list[tuple[str, int, DNF]] = []
    if kind == "enterprise":
        for eid in sorted({site.eid for site in game.sites}):
            dnfs = [site_city_dnf(game, site, city) for site in game.sites for city, prov in CITY_PROVINCE.items()
                    if site.eid == eid and prov == province]
            dnf = or_dnf(*dnfs)
            if dnf:
                rows.append((eid, 1, dnf))
    elif kind in {"workers", "mfg"}:
        for site in game.sites:
            if kind == "mfg" and site.industry != "manufacturing":
                continue
            dnf = or_dnf(*(site_city_dnf(game, site, city) for city, prov in CITY_PROVINCE.items() if prov == province))
            if dnf:
                rows.append((site.sid, site.workers, dnf))
    else:
        raise KeyError(kind)
    return rows


def threshold_dnf(items: list[tuple[str, int, DNF]], threshold: int) -> DNF:
    if threshold <= 0:
        return (frozenset(),)
    minimal_subsets: list[tuple[int, ...]] = []
    for size in range(1, len(items) + 1):
        for indexes in itertools.combinations(range(len(items)), size):
            if sum(items[index][1] for index in indexes) < threshold:
                continue
            if any(set(previous).issubset(indexes) for previous in minimal_subsets):
                continue
            minimal_subsets.append(indexes)
    return or_dnf(*(and_dnf(*(items[index][2] for index in indexes)) for indexes in minimal_subsets))


def _attainable(items: list[tuple[str, int, DNF]]) -> list[int]:
    result = {0}
    for _label, weight, _dnf in items:
        result |= {value + weight for value in list(result)}
    return sorted(result)


def ratio_components(game: Game, province: str) -> list[tuple[Fraction, DNF, str]]:
    m_items = _object_indicator_dnfs(game, province, "mfg")
    w_items = _object_indicator_dnfs(game, province, "workers")
    m_levels, w_levels = _attainable(m_items), _attainable(w_items)
    result: list[tuple[Fraction, DNF, str]] = []
    def h(m: int, w: int) -> Fraction:
        return Fraction(m, w) if w else Fraction(0)
    for i in range(1, len(m_levels)):
        for j in range(1, len(w_levels)):
            m, w = m_levels[i], w_levels[j]
            pm, pw = m_levels[i - 1], w_levels[j - 1]
            coefficient = h(m, w) - h(pm, w) - h(m, pw) + h(pm, pw)
            if not coefficient:
                continue
            dnf = and_dnf(threshold_dnf(m_items, m), threshold_dnf(w_items, w))
            if dnf:
                result.append((coefficient, dnf, f"{province}:M>={m}&W>={w}"))
    return result


def value_components(game: Game, value_name: str) -> list[tuple[Fraction, DNF, str]]:
    ta = threshold_dnf(_object_indicator_dnfs(game, "PA", "enterprise"), game.thresholds[0])
    tb = threshold_dnf(_object_indicator_dnfs(game, "PB", "enterprise"), game.thresholds[1])
    ratios = {"PA": ratio_components(game, "PA"), "PB": ratio_components(game, "PB")}
    if value_name == "G0":
        return [(Fraction(1, 4), ta, "T_A"), (Fraction(1, 4), tb, "T_B")] + [
            (coefficient / 4, dnf, label) for province in ("PA", "PB") for coefficient, dnf, label in ratios[province]
        ]
    if value_name == "G1":
        return [
            (coefficient / 2, and_dnf(ta if province == "PA" else tb, dnf), f"T_{province[-1]}&{label}")
            for province in ("PA", "PB") for coefficient, dnf, label in ratios[province]
        ]
    if value_name == "G2":
        gate = and_dnf(ta, tb)
        return [
            (coefficient / 2, and_dnf(gate, dnf), f"T_A&T_B&{label}")
            for province in ("PA", "PB") for coefficient, dnf, label in ratios[province]
        ]
    raise KeyError(value_name)


def component_value(components: list[tuple[Fraction, DNF, str]], mask: int) -> Fraction:
    return sum((coefficient * dnf_value(dnf, mask) for coefficient, dnf, _ in components), Fraction(0))


def dnf_to_poly(dnf: DNF) -> dict[int, Fraction]:
    result: defaultdict[int, Fraction] = defaultdict(Fraction)
    for subset in range(1, 1 << len(dnf)):
        mask = 0
        for index, clause in enumerate(dnf):
            if subset & (1 << index):
                for player in clause:
                    mask |= 1 << player
        result[mask] += 1 if subset.bit_count() % 2 else -1
    return {mask: coefficient for mask, coefficient in result.items() if coefficient}


def components_to_poly(components: list[tuple[Fraction, DNF, str]]) -> dict[int, Fraction]:
    result: defaultdict[int, Fraction] = defaultdict(Fraction)
    for scale, dnf, _label in components:
        for mask, coefficient in dnf_to_poly(dnf).items():
            result[mask] += scale * coefficient
    return {mask: coefficient for mask, coefficient in result.items() if coefficient}


def poly_shapley(poly: dict[int, Fraction], n: int) -> list[Fraction]:
    output = [Fraction(0) for _ in range(n)]
    for mask, coefficient in poly.items():
        share = coefficient / mask.bit_count()
        for player in range(n):
            if mask & (1 << player):
                output[player] += share
    return output


def structure_metrics(game: Game) -> dict[str, int | str | float]:
    clauses = [site_city_dnf(game, site, city) for site in game.sites for city in CITY_PROVINCE]
    clauses = [dnf for dnf in clauses if dnf]
    proof_sets = [clause for dnf in clauses for clause in dnf]
    overlaps = [len(a & b) for i, a in enumerate(proof_sets) for b in proof_sets[i + 1 :]]
    occurrences: defaultdict[int, int] = defaultdict(int)
    for clause in proof_sets:
        for player in clause:
            occurrences[player] += 1
    return {
        "game_id": game.game_id,
        "query_version": game.query_version,
        "n": game.n,
        "logical_site_city_objects": len(clauses),
        "join_witnesses": len(proof_sets),
        "source_variable_occurrences": sum(map(len, proof_sets)),
        "maximum_variable_occurrences": max(occurrences.values(), default=0),
        "overlapping_proof_pairs": sum(value > 0 for value in overlaps),
        "maximum_proof_overlap": max(overlaps, default=0),
        "mean_proof_overlap": sum(overlaps) / len(overlaps) if overlaps else 0.0,
    }
