from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Iterable, Sequence


State = tuple[int, ...]
Key = tuple[State, int]


class SharedStateLimitExceeded(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StateGame:
    game_id: str
    player_ids: tuple[str, ...]
    deltas: tuple[State, ...]
    value: Callable[[State], float]
    player_leaves: tuple[int, ...]
    leaf_count: int
    leaf_width: int

    @property
    def n(self) -> int:
        return len(self.deltas)

    @property
    def zero(self) -> State:
        return (0,) * len(self.deltas[0])


def add_state(left: State, right: State) -> State:
    return tuple(a + b for a, b in zip(left, right, strict=True))


def subtract_state(left: State, right: State) -> State | None:
    values = tuple(a - b for a, b in zip(left, right, strict=True))
    return values if all(value >= 0 for value in values) else None


def _check_game(game: StateGame) -> None:
    if game.n == 0:
        raise ValueError("game must contain at least one player")
    if len(game.player_ids) != game.n or len(game.player_leaves) != game.n:
        raise ValueError("player metadata length mismatch")
    width = len(game.deltas[0])
    if width != game.leaf_count * game.leaf_width:
        raise ValueError("state width does not match leaf layout")
    if any(len(delta) != width for delta in game.deltas):
        raise ValueError("inconsistent delta width")


def _build_distribution(
    zero: State,
    deltas: Iterable[State],
    *,
    state_cap: int,
) -> tuple[Counter[Key], dict[str, int]]:
    frontier: Counter[Key] = Counter({(zero, 0): 1})
    transitions = 0
    intermediate = 1
    maximum = 1
    steps = 0
    for delta in deltas:
        new: Counter[Key] = Counter()
        for (state, size), count in frontier.items():
            new[(state, size)] += count
            new[(add_state(state, delta), size + 1)] += count
            transitions += 2
        if len(new) > state_cap:
            raise SharedStateLimitExceeded(f"frontier {len(new)} exceeds cap {state_cap}")
        frontier = new
        intermediate += len(frontier)
        maximum = max(maximum, len(frontier))
        steps += 1
    return frontier, {
        "state_transitions": transitions,
        "intermediate_state_visits": intermediate,
        "maximum_frontier_states": maximum,
        "state_build_steps": steps,
    }


def _convolve(
    left: Counter[Key] | dict[Key, int],
    right: Counter[Key] | dict[Key, int],
    *,
    state_cap: int,
) -> tuple[Counter[Key], int]:
    result: Counter[Key] = Counter()
    transitions = 0
    for (left_state, left_size), left_count in left.items():
        for (right_state, right_size), right_count in right.items():
            result[(add_state(left_state, right_state), left_size + right_size)] += left_count * right_count
            transitions += 1
    if len(result) > state_cap:
        raise SharedStateLimitExceeded(f"convolution frontier {len(result)} exceeds cap {state_cap}")
    return result, transitions


class ValueCache:
    def __init__(self, value: Callable[[State], float]):
        self.value = value
        self.cache: dict[State, float] = {}
        self.requests = 0
        self.hits = 0

    def __call__(self, state: State) -> float:
        self.requests += 1
        if state in self.cache:
            self.hits += 1
            return self.cache[state]
        result = float(self.value(state))
        self.cache[state] = result
        return result

    @property
    def hit_rate(self) -> float:
        return self.hits / self.requests if self.requests else 0.0


def _marginal_from_distribution(
    game: StateGame,
    distribution: Counter[Key] | dict[Key, int],
    focal_delta: State,
    value: ValueCache,
) -> tuple[float, int]:
    total = 0.0
    evaluated = 0
    for (state, size), multiplicity in distribution.items():
        after = add_state(state, focal_delta)
        weight = 1.0 / (game.n * math.comb(game.n - 1, size))
        total += multiplicity * weight * (value(after) - value(state))
        evaluated += 1
    return total, evaluated


def _result_diagnostics(
    *,
    value: ValueCache,
    terminal_states: int,
    transitions: int,
    intermediate: int,
    maximum: int,
    rebuilds: int,
    result_cache_hits: int = 0,
    result_cache_requests: int = 0,
    extra: dict[str, int | float | str] | None = None,
) -> dict[str, int | float | str]:
    result: dict[str, int | float | str] = {
        "terminal_state_visits": terminal_states,
        "state_transitions": transitions,
        "intermediate_state_visits": intermediate,
        "maximum_frontier_states": maximum,
        "state_rebuild_count": rebuilds,
        "value_cache_entries": len(value.cache),
        "value_cache_requests": value.requests,
        "value_cache_hits": value.hits,
        "value_cache_hit_rate": value.hit_rate,
        "result_cache_requests": result_cache_requests,
        "result_cache_hits": result_cache_hits,
        "result_cache_hit_rate": result_cache_hits / result_cache_requests if result_cache_requests else 0.0,
    }
    if extra:
        result.update(extra)
    return result


def s0_per_focus_b2(
    game: StateGame,
    players: Sequence[int],
    *,
    state_cap: int,
) -> tuple[dict[int, float], dict[str, int | float | str]]:
    _check_game(game)
    value = ValueCache(game.value)
    allocation: dict[int, float] = {}
    transitions = intermediate = terminal = maximum = 0
    for focal in players:
        distribution, diagnostics = _build_distribution(
            game.zero,
            (delta for player, delta in enumerate(game.deltas) if player != focal),
            state_cap=state_cap,
        )
        allocation[focal], _ = _marginal_from_distribution(game, distribution, game.deltas[focal], value)
        transitions += diagnostics["state_transitions"]
        intermediate += diagnostics["intermediate_state_visits"]
        maximum = max(maximum, diagnostics["maximum_frontier_states"])
        terminal += len(distribution)
    return allocation, _result_diagnostics(
        value=value,
        terminal_states=terminal,
        transitions=transitions,
        intermediate=intermediate,
        maximum=maximum,
        rebuilds=len(players),
    )


def _local_leaf_factor(
    game: StateGame,
    players: Sequence[int],
    leaf: int,
    state_cap: int,
) -> tuple[Counter[tuple[tuple[int, ...], int]], dict[str, int]]:
    zero = (0,) * game.leaf_width
    frontier: Counter[tuple[tuple[int, ...], int]] = Counter({(zero, 0): 1})
    transitions = 0
    intermediate = 1
    maximum = 1
    start = leaf * game.leaf_width
    end = start + game.leaf_width
    for player in players:
        if game.player_leaves[player] != leaf:
            continue
        local_delta = game.deltas[player][start:end]
        new: Counter[tuple[tuple[int, ...], int]] = Counter()
        for (state, size), count in frontier.items():
            new[(state, size)] += count
            new[(tuple(a + b for a, b in zip(state, local_delta, strict=True)), size + 1)] += count
            transitions += 2
        if len(new) > state_cap:
            raise SharedStateLimitExceeded(f"leaf factor {len(new)} exceeds cap {state_cap}")
        frontier = new
        intermediate += len(frontier)
        maximum = max(maximum, len(frontier))
    return frontier, {
        "state_transitions": transitions,
        "intermediate_state_visits": intermediate,
        "maximum_frontier_states": maximum,
    }


def s1_per_focus_b3(
    game: StateGame,
    players: Sequence[int],
    *,
    state_cap: int,
) -> tuple[dict[int, float], dict[str, int | float | str]]:
    _check_game(game)
    value = ValueCache(game.value)
    allocation: dict[int, float] = {}
    transitions = intermediate = terminal = maximum = 0
    for focal in players:
        others = [player for player in range(game.n) if player != focal]
        factors = []
        for leaf in range(game.leaf_count):
            factor, diagnostics = _local_leaf_factor(game, others, leaf, state_cap)
            factors.append((leaf, factor))
            transitions += diagnostics["state_transitions"]
            intermediate += diagnostics["intermediate_state_visits"]
            maximum = max(maximum, diagnostics["maximum_frontier_states"])
        factors.sort(key=lambda item: len(item[1]))
        frontier: Counter[Key] = Counter({(game.zero, 0): 1})
        for leaf, factor in factors:
            new: Counter[Key] = Counter()
            start = leaf * game.leaf_width
            end = start + game.leaf_width
            for (state, size), count in frontier.items():
                for (local, local_size), local_count in factor.items():
                    combined = list(state)
                    combined[start:end] = local
                    new[(tuple(combined), size + local_size)] += count * local_count
                    transitions += 1
            if len(new) > state_cap:
                raise SharedStateLimitExceeded(f"leaf convolution {len(new)} exceeds cap {state_cap}")
            frontier = new
            intermediate += len(frontier)
            maximum = max(maximum, len(frontier))
        terminal += len(frontier)
        allocation[focal], _ = _marginal_from_distribution(game, frontier, game.deltas[focal], value)
    return allocation, _result_diagnostics(
        value=value,
        terminal_states=terminal,
        transitions=transitions,
        intermediate=intermediate,
        maximum=maximum,
        rebuilds=len(players) * game.leaf_count,
    )


def _type_factor(delta: State, multiplicity: int) -> Counter[Key]:
    return Counter(
        {
            (tuple(value * count for value in delta), count): math.comb(multiplicity, count)
            for count in range(multiplicity + 1)
        }
    )


def s2_per_focus_b4(
    game: StateGame,
    players: Sequence[int],
    *,
    state_cap: int,
) -> tuple[dict[int, float], dict[str, int | float | str]]:
    _check_game(game)
    groups: dict[State, list[int]] = defaultdict(list)
    for player, delta in enumerate(game.deltas):
        groups[delta].append(player)
    requested_types = {game.deltas[player] for player in players}
    value = ValueCache(game.value)
    type_results: dict[State, float] = {}
    transitions = intermediate = terminal = maximum = 0
    for focal_delta in requested_types:
        factors = [
            _type_factor(delta, len(members) - int(delta == focal_delta))
            for delta, members in groups.items()
        ]
        factors.sort(key=len)
        frontier: Counter[Key] = Counter({(game.zero, 0): 1})
        for factor in factors:
            frontier, writes = _convolve(frontier, factor, state_cap=state_cap)
            transitions += writes
            intermediate += len(frontier)
            maximum = max(maximum, len(frontier))
        terminal += len(frontier)
        type_results[focal_delta], _ = _marginal_from_distribution(game, frontier, focal_delta, value)
    allocation = {player: type_results[game.deltas[player]] for player in players}
    return allocation, _result_diagnostics(
        value=value,
        terminal_states=terminal,
        transitions=transitions,
        intermediate=intermediate,
        maximum=maximum,
        rebuilds=len(requested_types),
        result_cache_requests=len(players),
        result_cache_hits=len(players) - len(requested_types),
        extra={"raw_type_count": len(groups), "queried_type_count": len(requested_types)},
    )


class S3SharedForward:
    def __init__(self, game: StateGame, *, state_cap: int):
        _check_game(game)
        self.game = game
        self.state_cap = state_cap
        started = perf_counter()
        self.global_distribution, self.preprocess_diagnostics = _build_distribution(
            game.zero, game.deltas, state_cap=state_cap
        )
        self.preprocess_seconds = perf_counter() - started
        self.value = ValueCache(game.value)
        self.result_cache: dict[State, float] = {}
        self.result_requests = self.result_hits = 0
        self.query_state_reads = self.query_terminal_states = 0

    def clear_query_cache(self) -> None:
        self.value = ValueCache(self.game.value)
        self.result_cache.clear()
        self.result_requests = self.result_hits = 0
        self.query_state_reads = self.query_terminal_states = 0

    def query(self, player: int) -> float:
        delta = self.game.deltas[player]
        self.result_requests += 1
        if delta in self.result_cache:
            self.result_hits += 1
            return self.result_cache[delta]
        quotient: dict[Key, int] = {}
        ordered = sorted(self.global_distribution.items(), key=lambda item: item[0][1])
        for (state, size), global_count in ordered:
            previous_state = subtract_state(state, delta)
            previous = quotient.get((previous_state, size - 1), 0) if previous_state is not None and size else 0
            count = global_count - previous
            if count < 0:
                raise ArithmeticError("negative coefficient in exact factor division")
            if count:
                quotient[(state, size)] = count
            self.query_state_reads += 1
        if sum(quotient.values()) != 1 << (self.game.n - 1):
            raise ArithmeticError("factor division did not recover all predecessor coalitions")
        self.query_terminal_states += len(quotient)
        result, _ = _marginal_from_distribution(self.game, quotient, delta, self.value)
        self.result_cache[delta] = result
        return result

    def solve_all(self) -> list[float]:
        return [self.query(player) for player in range(self.game.n)]

    def diagnostics(self) -> dict[str, int | float | str]:
        return _result_diagnostics(
            value=self.value,
            terminal_states=self.query_terminal_states,
            transitions=self.preprocess_diagnostics["state_transitions"] + self.query_state_reads,
            intermediate=self.preprocess_diagnostics["intermediate_state_visits"],
            maximum=self.preprocess_diagnostics["maximum_frontier_states"],
            rebuilds=1,
            result_cache_hits=self.result_hits,
            result_cache_requests=self.result_requests,
            extra={
                "shared_global_states": len(self.global_distribution),
                "query_state_reads": self.query_state_reads,
                "shared_preprocess_seconds": self.preprocess_seconds,
                "sharing_mechanism": "global generating function divided by each player factor",
            },
        )


class S4PrefixSuffix:
    def __init__(self, game: StateGame, *, state_cap: int):
        _check_game(game)
        self.game = game
        self.state_cap = state_cap
        started = perf_counter()
        self.prefix: list[Counter[Key]] = [Counter({(game.zero, 0): 1})]
        self.suffix: list[Counter[Key]] = [Counter() for _ in range(game.n + 1)]
        self.suffix[game.n] = Counter({(game.zero, 0): 1})
        transitions = 0
        maximum = 1
        for delta in game.deltas:
            factor = _type_factor(delta, 1)
            current, writes = _convolve(self.prefix[-1], factor, state_cap=state_cap)
            self.prefix.append(current)
            transitions += writes
            maximum = max(maximum, len(current))
        for player in range(game.n - 1, -1, -1):
            factor = _type_factor(game.deltas[player], 1)
            current, writes = _convolve(factor, self.suffix[player + 1], state_cap=state_cap)
            self.suffix[player] = current
            transitions += writes
            maximum = max(maximum, len(current))
        self.preprocess_seconds = perf_counter() - started
        self.preprocess_transitions = transitions
        self.maximum = maximum
        self.value = ValueCache(game.value)
        self.query_transitions = self.query_terminal_states = 0

    def clear_query_cache(self) -> None:
        self.value = ValueCache(self.game.value)
        self.query_transitions = self.query_terminal_states = 0

    def query(self, player: int) -> float:
        distribution, writes = _convolve(
            self.prefix[player], self.suffix[player + 1], state_cap=self.state_cap
        )
        self.query_transitions += writes
        self.query_terminal_states += len(distribution)
        result, _ = _marginal_from_distribution(self.game, distribution, self.game.deltas[player], self.value)
        return result

    def solve_all(self) -> list[float]:
        return [self.query(player) for player in range(self.game.n)]

    def diagnostics(self) -> dict[str, int | float | str]:
        cached_states = sum(len(item) for item in self.prefix) + sum(len(item) for item in self.suffix)
        return _result_diagnostics(
            value=self.value,
            terminal_states=self.query_terminal_states,
            transitions=self.preprocess_transitions + self.query_transitions,
            intermediate=cached_states,
            maximum=self.maximum,
            rebuilds=2,
            extra={
                "cached_factor_tables": len(self.prefix) + len(self.suffix),
                "cached_factor_states": cached_states,
                "factor_table_reuses": 2 * self.game.n,
                "shared_preprocess_seconds": self.preprocess_seconds,
                "sharing_mechanism": "prefix/suffix factors reused by every focal query",
            },
        )


class S5TypeMultiOutput:
    def __init__(self, game: StateGame, *, state_cap: int):
        _check_game(game)
        self.game = game
        self.state_cap = state_cap
        self.groups: dict[State, list[int]] = defaultdict(list)
        for player, delta in enumerate(game.deltas):
            self.groups[delta].append(player)
        self.types = sorted(self.groups, key=lambda state: (len(self.groups[state]), state))
        started = perf_counter()
        full_factors = [_type_factor(delta, len(self.groups[delta])) for delta in self.types]
        self.reduced_factors = [_type_factor(delta, len(self.groups[delta]) - 1) for delta in self.types]
        self.prefix: list[Counter[Key]] = [Counter({(game.zero, 0): 1})]
        self.suffix: list[Counter[Key]] = [Counter() for _ in range(len(self.types) + 1)]
        self.suffix[len(self.types)] = Counter({(game.zero, 0): 1})
        transitions = 0
        maximum = 1
        for factor in full_factors:
            current, writes = _convolve(self.prefix[-1], factor, state_cap=state_cap)
            self.prefix.append(current)
            transitions += writes
            maximum = max(maximum, len(current))
        for index in range(len(self.types) - 1, -1, -1):
            current, writes = _convolve(full_factors[index], self.suffix[index + 1], state_cap=state_cap)
            self.suffix[index] = current
            transitions += writes
            maximum = max(maximum, len(current))
        self.preprocess_seconds = perf_counter() - started
        self.preprocess_transitions = transitions
        self.maximum = maximum
        self.value = ValueCache(game.value)
        self.result_cache: dict[State, float] = {}
        self.result_requests = self.result_hits = 0
        self.query_transitions = self.query_terminal_states = 0

    def clear_query_cache(self) -> None:
        self.value = ValueCache(self.game.value)
        self.result_cache.clear()
        self.result_requests = self.result_hits = 0
        self.query_transitions = self.query_terminal_states = 0

    def query(self, player: int) -> float:
        delta = self.game.deltas[player]
        self.result_requests += 1
        if delta in self.result_cache:
            self.result_hits += 1
            return self.result_cache[delta]
        index = self.types.index(delta)
        partial, writes_a = _convolve(
            self.prefix[index], self.reduced_factors[index], state_cap=self.state_cap
        )
        distribution, writes_b = _convolve(
            partial, self.suffix[index + 1], state_cap=self.state_cap
        )
        self.query_transitions += writes_a + writes_b
        self.query_terminal_states += len(distribution)
        result, _ = _marginal_from_distribution(self.game, distribution, delta, self.value)
        self.result_cache[delta] = result
        return result

    def solve_all(self) -> list[float]:
        return [self.query(player) for player in range(self.game.n)]

    def diagnostics(self) -> dict[str, int | float | str]:
        cached_states = sum(len(item) for item in self.prefix) + sum(len(item) for item in self.suffix)
        return _result_diagnostics(
            value=self.value,
            terminal_states=self.query_terminal_states,
            transitions=self.preprocess_transitions + self.query_transitions,
            intermediate=cached_states,
            maximum=self.maximum,
            rebuilds=2,
            result_cache_hits=self.result_hits,
            result_cache_requests=self.result_requests,
            extra={
                "raw_type_count": len(self.types),
                "cached_factor_tables": len(self.prefix) + len(self.suffix) + len(self.reduced_factors),
                "cached_factor_states": cached_states + sum(len(item) for item in self.reduced_factors),
                "shared_preprocess_seconds": self.preprocess_seconds,
                "sharing_mechanism": "type-factor prefix/suffix elimination with one output per type",
            },
        )


def gauss_legendre_unit_interval(order: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    if order < 1:
        raise ValueError("quadrature order must be positive")
    roots = [0.0] * order
    weights = [0.0] * order
    half = (order + 1) // 2
    for index in range(half):
        root = math.cos(math.pi * (index + 0.75) / (order + 0.5))
        for _ in range(100):
            p0, p1 = 1.0, root
            for degree in range(2, order + 1):
                p0, p1 = p1, ((2 * degree - 1) * root * p1 - (degree - 1) * p0) / degree
            polynomial = p1 if order > 1 else root
            previous = p0 if order > 1 else 1.0
            derivative = order * (root * polynomial - previous) / (root * root - 1.0)
            update = polynomial / derivative
            root -= update
            if abs(update) < 1e-15:
                break
        weight = 2.0 / ((1.0 - root * root) * derivative * derivative)
        left, right = index, order - 1 - index
        roots[left] = -root
        roots[right] = root
        weights[left] = weight
        weights[right] = weight
    unit_roots = tuple((root + 1.0) / 2.0 for root in roots)
    unit_weights = tuple(weight / 2.0 for weight in weights)
    if abs(sum(unit_weights) - 1.0) > 1e-13:
        raise ArithmeticError("quadrature weights do not integrate the constant polynomial")
    return unit_roots, unit_weights


class S6ReverseMultilinearAD:
    def __init__(self, game: StateGame, *, state_cap: int):
        _check_game(game)
        self.game = game
        self.state_cap = state_cap
        started = perf_counter()
        self.layers: list[tuple[State, ...]] = [(game.zero,)]
        transitions = 0
        maximum = 1
        for delta in game.deltas:
            next_states = set(self.layers[-1])
            next_states.update(add_state(state, delta) for state in self.layers[-1])
            if len(next_states) > state_cap:
                raise SharedStateLimitExceeded(f"AD layer {len(next_states)} exceeds cap {state_cap}")
            self.layers.append(tuple(next_states))
            transitions += 2 * len(self.layers[-2])
            maximum = max(maximum, len(next_states))
        self.value = ValueCache(game.value)
        self.terminal_values = {state: self.value(state) for state in self.layers[-1]}
        self.preprocess_seconds = perf_counter() - started
        self.preprocess_transitions = transitions
        self.maximum = maximum
        self.solve_transitions = 0
        self.solve_calls = 0
        self.cached_allocation: list[float] | None = None

    def clear_query_cache(self) -> None:
        self.cached_allocation = None
        self.solve_transitions = 0
        self.solve_calls = 0

    def solve_all(self) -> list[float]:
        if self.cached_allocation is not None:
            return list(self.cached_allocation)
        order = (self.game.n + 1) // 2
        nodes, weights = gauss_legendre_unit_interval(order)
        allocation = [0.0] * self.game.n
        transitions = 0
        for probability, quadrature_weight in zip(nodes, weights, strict=True):
            forward: list[dict[State, float]] = [{self.game.zero: 1.0}]
            for player, delta in enumerate(self.game.deltas):
                current: dict[State, float] = defaultdict(float)
                for state, mass in forward[-1].items():
                    current[state] += (1.0 - probability) * mass
                    current[add_state(state, delta)] += probability * mass
                    transitions += 2
                forward.append(dict(current))
            adjoint = dict(self.terminal_values)
            for player in range(self.game.n - 1, -1, -1):
                delta = self.game.deltas[player]
                previous_adjoint: dict[State, float] = {}
                gradient = 0.0
                for state, mass in forward[player].items():
                    excluded = adjoint[state]
                    included = adjoint[add_state(state, delta)]
                    gradient += mass * (included - excluded)
                    previous_adjoint[state] = (1.0 - probability) * excluded + probability * included
                    transitions += 2
                allocation[player] += quadrature_weight * gradient
                adjoint = previous_adjoint
        self.solve_transitions += transitions
        self.solve_calls += 1
        self.cached_allocation = allocation
        return list(allocation)

    def query(self, player: int) -> float:
        return self.solve_all()[player]

    def diagnostics(self) -> dict[str, int | float | str]:
        cached_states = sum(len(layer) for layer in self.layers)
        order = (self.game.n + 1) // 2
        return _result_diagnostics(
            value=self.value,
            terminal_states=len(self.layers[-1]),
            transitions=self.preprocess_transitions + self.solve_transitions,
            intermediate=cached_states,
            maximum=self.maximum,
            rebuilds=1,
            result_cache_requests=self.solve_calls,
            result_cache_hits=0,
            extra={
                "cached_factor_tables": len(self.layers),
                "cached_factor_states": cached_states,
                "quadrature_order": order,
                "shared_preprocess_seconds": self.preprocess_seconds,
                "single_player_query_scope": "all_outputs_inseparable_reverse_pass",
                "sharing_mechanism": "reverse AD of multilinear expectation circuit; terminal nonlinear value is constant",
            },
        )


def exact_b0(game: StateGame) -> tuple[list[float], dict[str, int]]:
    _check_game(game)
    states = [game.zero]
    for mask in range(1, 1 << game.n):
        bit = mask & -mask
        player = bit.bit_length() - 1
        states.append(add_state(states[mask ^ bit], game.deltas[player]))
    values = [float(game.value(state)) for state in states]
    allocation = [0.0] * game.n
    transitions = 0
    for player in range(game.n):
        bit = 1 << player
        for mask in range(1 << game.n):
            if mask & bit:
                continue
            size = mask.bit_count()
            allocation[player] += (values[mask | bit] - values[mask]) / (
                game.n * math.comb(game.n - 1, size)
            )
            transitions += 1
    return allocation, {
        "coalition_count": len(states),
        "unique_state_count": len(set(states)),
        "state_transitions": transitions,
    }


def max_abs_error(left: Sequence[float], right: Sequence[float]) -> float:
    return max((abs(a - b) for a, b in zip(left, right, strict=True)), default=0.0)


def efficiency_error(game: StateGame, allocation: Sequence[float]) -> float:
    full = game.zero
    for delta in game.deltas:
        full = add_state(full, delta)
    return abs(sum(allocation) - (float(game.value(full)) - float(game.value(game.zero))))
