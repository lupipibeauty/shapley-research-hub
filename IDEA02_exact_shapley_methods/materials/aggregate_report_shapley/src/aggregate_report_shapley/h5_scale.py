from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from typing import Callable, Iterable, Sequence


State = tuple[int, ...]


class StateLimitExceeded(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ScaleConfig:
    config_id: str
    group: str
    n: int
    leaves: int
    dimensions: int
    profile: str
    family_map: tuple[int, ...]
    score_modes: tuple[str, ...]
    exact_payments_expected: bool


@dataclass(frozen=True, slots=True)
class ScaleRecord:
    player: int
    leaf: int
    increments: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ScaleInstance:
    config: ScaleConfig
    seed: int
    records: tuple[ScaleRecord, ...]
    parents: tuple[int, ...]
    parent_count: int
    full_state: State

    @property
    def n(self) -> int:
        return len(self.records)

    @property
    def shape(self) -> tuple[int, int]:
        return self.config.leaves, self.config.dimensions


def zero_state(leaves: int, dimensions: int) -> State:
    return (0,) * (leaves * dimensions)


def add_state(left: State, right: State) -> State:
    return tuple(a + b for a, b in zip(left, right, strict=True))


def record_delta(record: ScaleRecord, leaves: int, dimensions: int) -> State:
    result = [0] * (leaves * dimensions)
    offset = record.leaf * dimensions
    result[offset : offset + dimensions] = record.increments
    return tuple(result)


def _base_patterns(leaf: int) -> tuple[tuple[int, int, int, int], ...]:
    pools = (
        ((1, 0, 1, 1), (1, 1, 1, 0)),
        ((1, 0, 1, 1), (1, 1, 0, 0)),
        ((1, 0, 1, 1), (1, 0, 1, 0), (1, 1, 1, 1), (1, 1, 0, 0)),
        ((1, 0, 1, 1), (1, 0, 1, 0), (1, 1, 1, 1), (1, 1, 1, 0)),
    )
    return pools[leaf % len(pools)]


def _extend_pattern(
    base: tuple[int, ...], dimensions: int, *, player: int, leaf: int, rng: random.Random
) -> tuple[int, ...]:
    values = list(base[:dimensions])
    while len(values) < dimensions:
        index = len(values)
        # Extra dimensions are actual binary statistics with player-dependent variation.
        values.append(int(((player + 1) * (index + 3) + leaf + rng.randrange(7)) % 5 < 2))
    return tuple(values)


def generate_instance(config: ScaleConfig, seed: int) -> ScaleInstance:
    if config.dimensions < 2:
        raise ValueError("at least two base dimensions are required")
    if config.leaves < 1 or config.n < config.leaves:
        raise ValueError("n must be at least the number of leaves")
    rng = random.Random(seed)
    leaf_assignment = [player % config.leaves for player in range(config.n)]
    rng.shuffle(leaf_assignment)
    records: list[ScaleRecord] = []
    leaf_seen: Counter[tuple[int, tuple[int, ...]]] = Counter()
    for player, leaf in enumerate(leaf_assignment):
        pool = _base_patterns(leaf)
        if config.profile == "balanced_templates":
            local_index = leaf_seen[(leaf, ())]
            base = pool[(local_index + seed) % len(pool)]
            leaf_seen[(leaf, ())] += 1
        elif config.profile == "diverse_effective":
            base = pool[rng.randrange(len(pool))]
        elif config.profile == "high_repeat":
            base = pool[seed % min(2, len(pool))]
        else:
            raise KeyError(config.profile)
        increments = _extend_pattern(base, config.dimensions, player=player, leaf=leaf, rng=rng)
        records.append(ScaleRecord(player=player, leaf=leaf, increments=increments))

    # Repair only degenerate extra statistics. Each repair changes an actual increment.
    for dimension in range(4, config.dimensions):
        positive = sum(record.increments[dimension] for record in records)
        if positive in (0, config.n):
            repaired: list[ScaleRecord] = []
            for index, record in enumerate(records):
                values = list(record.increments)
                if index == seed % config.n:
                    values[dimension] = 1 - values[dimension]
                repaired.append(ScaleRecord(record.player, record.leaf, tuple(values)))
            records = repaired

    parent_count = 1 if config.leaves == 1 else 2
    parents = tuple(min(parent_count - 1, leaf * parent_count // config.leaves) for leaf in range(config.leaves))
    full = zero_state(config.leaves, config.dimensions)
    for record in records:
        full = add_state(full, record_delta(record, config.leaves, config.dimensions))
    return ScaleInstance(
        config=config,
        seed=seed,
        records=tuple(records),
        parents=parents,
        parent_count=parent_count,
        full_state=full,
    )


def node_weights(instance: ScaleInstance) -> tuple[list[float], list[float], float]:
    leaf_weights = [1.0 / (3.0 * instance.config.leaves)] * instance.config.leaves
    parent_weights = [1.0 / (3.0 * instance.parent_count)] * instance.parent_count
    return leaf_weights, parent_weights, 1.0 / 3.0


def _node_counts(instance: ScaleInstance, state: State, dimension: int) -> tuple[list[int], list[int], int]:
    d = instance.config.dimensions
    leaves = [state[leaf * d + dimension] for leaf in range(instance.config.leaves)]
    parents = [0] * instance.parent_count
    for leaf, value in enumerate(leaves):
        parents[instance.parents[leaf]] += value
    return leaves, parents, sum(leaves)


def _weighted_coverage(instance: ScaleInstance, state: State, dimension: int) -> float:
    leaf_weights, parent_weights, root_weight = node_weights(instance)
    current = _node_counts(instance, state, dimension)
    full = _node_counts(instance, instance.full_state, dimension)
    pairs: list[tuple[float, int, int]] = []
    pairs.extend(zip(leaf_weights, current[0], full[0], strict=True))
    pairs.extend(zip(parent_weights, current[1], full[1], strict=True))
    pairs.append((root_weight, current[2], full[2]))
    valid = [(weight, value, reference) for weight, value, reference in pairs if reference > 0]
    total_weight = sum(weight for weight, _value, _reference in valid)
    return sum(weight * value / reference for weight, value, reference in valid) / total_weight


def _weighted_share(
    instance: ScaleInstance, state: State, denominator_dimension: int, target_dimension: int
) -> float:
    leaf_weights, parent_weights, root_weight = node_weights(instance)
    denominator = _node_counts(instance, state, denominator_dimension)
    target = _node_counts(instance, state, target_dimension)
    full_denominator = _node_counts(instance, instance.full_state, denominator_dimension)
    full_target = _node_counts(instance, instance.full_state, target_dimension)
    rows: list[tuple[float, int, int, int, int]] = []
    rows.extend(
        (weight, den, tar, full_den, full_tar)
        for weight, den, tar, full_den, full_tar in zip(
            leaf_weights, denominator[0], target[0], full_denominator[0], full_target[0], strict=True
        )
    )
    rows.extend(
        (weight, den, tar, full_den, full_tar)
        for weight, den, tar, full_den, full_tar in zip(
            parent_weights, denominator[1], target[1], full_denominator[1], full_target[1], strict=True
        )
    )
    rows.append((root_weight, denominator[2], target[2], full_denominator[2], full_target[2]))
    valid = [row for row in rows if row[3] > 0]
    total_weight = sum(row[0] for row in valid)
    score = 0.0
    for weight, den, tar, full_den, full_tar in valid:
        # Equivalent to den/F - |tar*F-den*C|/F^2, including den=0 -> 0.
        local = den / full_den - abs(tar * full_den - den * full_tar) / (full_den * full_den)
        score += weight * local
    return score / total_weight


def base_family_scores(instance: ScaleInstance, state: State) -> tuple[float, ...]:
    d = instance.config.dimensions
    scores: list[float] = []
    scores.append(_weighted_coverage(instance, state, 0))
    if d >= 2:
        scores.append(
            0.5 * _weighted_coverage(instance, state, 1)
            + 0.5 * _weighted_share(instance, state, 0, 1)
        )
    if d >= 3:
        scores.append(_weighted_coverage(instance, state, 2))
    if d >= 4:
        scores.append(_weighted_share(instance, state, 2, 3))
    for dimension in range(4, d):
        scores.append(_weighted_coverage(instance, state, dimension))
    return tuple(scores)


def make_value_function(instance: ScaleInstance, mode: str) -> Callable[[State], float]:
    mapping = instance.config.family_map

    def evaluate(state: State) -> float:
        base = base_family_scores(instance, state)
        scores = [base[index] for index in mapping]
        additive = sum(scores) / len(scores)
        if any(score <= 0.0 for score in scores):
            geometric = 0.0
        else:
            geometric = math.exp(sum(math.log(score) for score in scores) / len(scores))
        if mode == "additive":
            return additive
        if mode == "geometric":
            return geometric
        if mode == "v2":
            return 0.5 * additive + 0.5 * geometric
        raise KeyError(mode)

    return evaluate


def required_dimensions(config: ScaleConfig) -> tuple[int, ...]:
    required: set[int] = set()
    for family in config.family_map:
        if family == 0:
            required.add(0)
        elif family == 1:
            required.update((0, 1))
        elif family == 2:
            required.add(2)
        elif family == 3:
            required.update((2, 3))
        else:
            required.add(family)
    return tuple(sorted(required))


def project_state(state: State, leaves: int, dimensions: int, required: Sequence[int]) -> State:
    required_set = set(required)
    return tuple(
        value if index % dimensions in required_set else 0 for index, value in enumerate(state)
    )


def all_incremental_states(instance: ScaleInstance, required: Sequence[int] | None = None) -> list[State]:
    n = instance.n
    d = instance.config.dimensions
    leaves = instance.config.leaves
    deltas = [record_delta(record, leaves, d) for record in instance.records]
    if required is not None:
        deltas = [project_state(delta, leaves, d, required) for delta in deltas]
    states = [zero_state(leaves, d)]
    for mask in range(1, 1 << n):
        bit = mask & -mask
        player = bit.bit_length() - 1
        states.append(add_state(states[mask ^ bit], deltas[player]))
    return states


def shapley_from_values(values: Sequence[float], n: int) -> list[float]:
    result = [0.0] * n
    for player in range(n):
        bit = 1 << player
        total = 0.0
        for mask in range(1 << n):
            if mask & bit:
                continue
            k = mask.bit_count()
            total += (values[mask | bit] - values[mask]) / (n * math.comb(n - 1, k))
        result[player] = total
    return result


def b0_full_enumeration(instance: ScaleInstance, mode: str) -> tuple[list[float], dict[str, int]]:
    required = required_dimensions(instance.config)
    states = all_incremental_states(instance, required)
    value = make_value_function(instance, mode)
    values = [value(state) for state in states]
    allocation = shapley_from_values(values, instance.n)
    return allocation, {
        "actual_visited_states": len(states),
        "unique_value_states": len(set(states)),
        "state_transitions": instance.n * (1 << (instance.n - 1)),
        "maximum_frontier_states": 1 << instance.n,
    }


def _state_size(state: State, dimensions: int) -> int:
    return sum(state[index] for index in range(0, len(state), dimensions))


def b2_state_dp(
    instance: ScaleInstance, mode: str, *, state_cap: int
) -> tuple[list[float], dict[str, int]]:
    n = instance.n
    d = instance.config.dimensions
    leaves = instance.config.leaves
    required = required_dimensions(instance.config)
    deltas = [
        project_state(record_delta(record, leaves, d), leaves, d, required)
        for record in instance.records
    ]
    value = make_value_function(instance, mode)
    allocation: list[float] = []
    transitions = 0
    intermediate = 0
    terminal = 0
    maximum = 0
    value_states: set[State] = set()
    for focal in range(n):
        frontier: Counter[State] = Counter({zero_state(leaves, d): 1})
        for player, delta in enumerate(deltas):
            if player == focal:
                continue
            new: Counter[State] = Counter()
            for state, multiplicity in frontier.items():
                new[state] += multiplicity
                new[add_state(state, delta)] += multiplicity
                transitions += 2
            if len(new) > state_cap:
                raise StateLimitExceeded(f"B2 frontier {len(new)} exceeds cap {state_cap}")
            frontier = new
            intermediate += len(frontier)
            maximum = max(maximum, len(frontier))
        terminal += len(frontier)
        focal_delta = deltas[focal]
        phi = 0.0
        for state, multiplicity in frontier.items():
            after = add_state(state, focal_delta)
            value_states.update((state, after))
            k = _state_size(state, d)
            phi += multiplicity * (value(after) - value(state)) / (n * math.comb(n - 1, k))
        allocation.append(phi)
    return allocation, {
        "actual_visited_states": terminal,
        "unique_value_states": len(value_states),
        "intermediate_state_visits": intermediate,
        "state_transitions": transitions,
        "maximum_frontier_states": maximum,
    }


def _leaf_factor(
    deltas: Sequence[State], leaf: int, dimensions: int, state_cap: int
) -> tuple[Counter[tuple[int, ...]], int]:
    factor: Counter[tuple[int, ...]] = Counter({(0,) * dimensions: 1})
    transitions = 0
    for delta in deltas:
        local = delta[leaf * dimensions : (leaf + 1) * dimensions]
        if not any(local):
            continue
        new: Counter[tuple[int, ...]] = Counter()
        for state, multiplicity in factor.items():
            new[state] += multiplicity
            new[tuple(a + b for a, b in zip(state, local, strict=True))] += multiplicity
            transitions += 2
        if len(new) > state_cap:
            raise StateLimitExceeded(f"B3 local factor {len(new)} exceeds cap {state_cap}")
        factor = new
    return factor, transitions


def b3_leaf_factor(
    instance: ScaleInstance, mode: str, *, state_cap: int
) -> tuple[list[float], dict[str, int]]:
    n = instance.n
    d = instance.config.dimensions
    leaves = instance.config.leaves
    required = required_dimensions(instance.config)
    deltas = [
        project_state(record_delta(record, leaves, d), leaves, d, required)
        for record in instance.records
    ]
    value = make_value_function(instance, mode)
    allocation: list[float] = []
    transitions = 0
    intermediate = 0
    terminal = 0
    maximum = 0
    value_states: set[State] = set()
    for focal in range(n):
        others = [delta for player, delta in enumerate(deltas) if player != focal]
        factors: list[tuple[int, Counter[tuple[int, ...]]]] = []
        for leaf in range(leaves):
            factor, local_transitions = _leaf_factor(others, leaf, d, state_cap)
            factors.append((leaf, factor))
            transitions += local_transitions
        factors.sort(key=lambda item: len(item[1]))
        frontier: Counter[State] = Counter({zero_state(leaves, d): 1})
        for leaf, factor in factors:
            new: Counter[State] = Counter()
            for state, count in frontier.items():
                for local, local_count in factor.items():
                    combined = list(state)
                    combined[leaf * d : (leaf + 1) * d] = local
                    new[tuple(combined)] += count * local_count
                    transitions += 1
            if len(new) > state_cap:
                raise StateLimitExceeded(f"B3 frontier {len(new)} exceeds cap {state_cap}")
            frontier = new
            intermediate += len(frontier)
            maximum = max(maximum, len(frontier))
        terminal += len(frontier)
        focal_delta = deltas[focal]
        phi = 0.0
        for state, multiplicity in frontier.items():
            after = add_state(state, focal_delta)
            value_states.update((state, after))
            k = _state_size(state, d)
            phi += multiplicity * (value(after) - value(state)) / (n * math.comb(n - 1, k))
        allocation.append(phi)
    return allocation, {
        "actual_visited_states": terminal,
        "unique_value_states": len(value_states),
        "intermediate_state_visits": intermediate,
        "state_transitions": transitions,
        "maximum_frontier_states": maximum,
    }


def _type_factor(
    delta: State, multiplicity: int
) -> dict[State, int]:
    return {
        tuple(value * count for value in delta): math.comb(multiplicity, count)
        for count in range(multiplicity + 1)
    }


def b4_type_variable_elimination(
    instance: ScaleInstance, mode: str, *, state_cap: int
) -> tuple[list[float], dict[str, int]]:
    n = instance.n
    d = instance.config.dimensions
    leaves = instance.config.leaves
    required = required_dimensions(instance.config)
    deltas = [
        project_state(record_delta(record, leaves, d), leaves, d, required)
        for record in instance.records
    ]
    groups: dict[State, list[int]] = defaultdict(list)
    for player, delta in enumerate(deltas):
        groups[delta].append(player)
    value = make_value_function(instance, mode)
    allocation = [0.0] * n
    transitions = 0
    intermediate = 0
    terminal = 0
    maximum = 0
    value_states: set[State] = set()
    for focal_delta, players in groups.items():
        factors: list[dict[State, int]] = []
        for delta, members in groups.items():
            multiplicity = len(members) - int(delta == focal_delta)
            factors.append(_type_factor(delta, multiplicity))
        factors.sort(key=len)
        frontier: dict[State, int] = {zero_state(leaves, d): 1}
        for factor in factors:
            new: dict[State, int] = defaultdict(int)
            for state, count in frontier.items():
                for increment, increment_count in factor.items():
                    new[add_state(state, increment)] += count * increment_count
                    transitions += 1
            if len(new) > state_cap:
                raise StateLimitExceeded(f"B4 frontier {len(new)} exceeds cap {state_cap}")
            frontier = dict(new)
            intermediate += len(frontier)
            maximum = max(maximum, len(frontier))
        terminal += len(frontier)
        phi = 0.0
        for state, multiplicity in frontier.items():
            after = add_state(state, focal_delta)
            value_states.update((state, after))
            k = _state_size(state, d)
            phi += multiplicity * (value(after) - value(state)) / (n * math.comb(n - 1, k))
        for player in players:
            allocation[player] = phi
    return allocation, {
        "raw_type_count": len(groups),
        "actual_visited_states": terminal,
        "unique_value_states": len(value_states),
        "intermediate_state_visits": intermediate,
        "state_transitions": transitions,
        "maximum_frontier_states": maximum,
    }


def b5_shared_linear_closed_form(instance: ScaleInstance, mode: str) -> tuple[list[float], dict[str, int]]:
    if set(instance.config.family_map) != {0}:
        raise ValueError("B5 only applies when every family aliases P")
    if mode not in ("additive", "geometric", "v2"):
        raise KeyError(mode)
    value = make_value_function(instance, mode)
    empty = zero_state(instance.config.leaves, instance.config.dimensions)
    allocation: list[float] = []
    for record in instance.records:
        delta = record_delta(record, instance.config.leaves, instance.config.dimensions)
        allocation.append(value(delta) - value(empty))
    return allocation, {
        "actual_visited_states": instance.n + 1,
        "unique_value_states": instance.n + 1,
        "intermediate_state_visits": instance.n,
        "state_transitions": instance.n,
        "maximum_frontier_states": instance.n + 1,
    }


def rational_rank(columns: Sequence[Sequence[int]]) -> int:
    if not columns:
        return 0
    matrix = [[Fraction(columns[col][row]) for col in range(len(columns))] for row in range(len(columns[0]))]
    rank = 0
    for col in range(len(columns)):
        pivot = next((row for row in range(rank, len(matrix)) if matrix[row][col] != 0), None)
        if pivot is None:
            continue
        matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
        scale = matrix[rank][col]
        matrix[rank] = [value / scale for value in matrix[rank]]
        for row in range(len(matrix)):
            if row == rank or matrix[row][col] == 0:
                continue
            factor = matrix[row][col]
            matrix[row] = [a - factor * b for a, b in zip(matrix[row], matrix[rank], strict=True)]
        rank += 1
        if rank == len(matrix):
            break
    return rank


def structural_state_count(
    instance: ScaleInstance, *, enumeration_cap: int
) -> dict[str, int | str | float]:
    config = instance.config
    required = required_dimensions(config)
    d = config.dimensions
    projected_full = project_state(instance.full_state, config.leaves, d, required)
    box_bound = 1
    for leaf in range(config.leaves):
        for dimension in required:
            box_bound *= projected_full[leaf * d + dimension] + 1
    coalition_count = 1 << instance.n
    theoretical = min(coalition_count, box_bound)
    local_counts: list[int] = []
    status = "EXACT"
    for leaf in range(config.leaves):
        groups: Counter[tuple[int, ...]] = Counter()
        for record in instance.records:
            if record.leaf != leaf:
                continue
            local = tuple(record.increments[index] if index in required else 0 for index in range(d))
            groups[local] += 1
        types = list(groups)
        rank = rational_rank(types)
        type_grid = math.prod(groups[item] + 1 for item in types)
        if rank == len(types):
            local_counts.append(type_grid)
            continue
        if type_grid <= enumeration_cap:
            states = set()
            for counts in product(*(range(groups[item] + 1) for item in types)):
                states.add(tuple(sum(count * types[t][dimension] for t, count in enumerate(counts)) for dimension in range(d)))
            local_counts.append(len(states))
        else:
            status = "BOUNDED_NOT_ENUMERATED"
            local_counts.append(type_grid)
    factorized = math.prod(local_counts)
    actual = factorized if status == "EXACT" else "NA"
    ratio = float(actual / coalition_count) if isinstance(actual, int) else math.nan
    return {
        "required_dimension_count": len(required),
        "coalition_count": coalition_count,
        "coordinate_box_bound": box_bound,
        "theoretical_state_upper": theoretical,
        "factorized_type_grid_upper": factorized,
        "actual_reachable_states": actual,
        "state_count_status": status,
        "states_per_coalition": ratio,
        "coalition_merge_fraction": 1.0 - ratio if not math.isnan(ratio) else math.nan,
        "local_state_counts": "|".join(map(str, local_counts)),
    }


def exact_efficiency_error(instance: ScaleInstance, mode: str, allocation: Sequence[float]) -> float:
    value = make_value_function(instance, mode)
    empty = zero_state(instance.config.leaves, instance.config.dimensions)
    return abs(sum(allocation) - (value(instance.full_state) - value(empty)))


def max_abs_error(left: Sequence[float], right: Sequence[float]) -> float:
    return max((abs(a - b) for a, b in zip(left, right, strict=True)), default=0.0)
