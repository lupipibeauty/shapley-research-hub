from __future__ import annotations

import math
from collections import Counter


def subset_shapley(values: list[float], n: int) -> list[float]:
    result=[0.0]*n
    weights=[1.0/(n*math.comb(n-1,k)) for k in range(n)]
    for i in range(n):
        bit=1<<i
        result[i]=sum(weights[mask.bit_count()]*(values[mask|bit]-values[mask])
                      for mask in range(1<<n) if not mask&bit)
    return result


def mobius_shapley(values: list[float], n: int) -> list[float]:
    dividends=list(map(float,values))
    for i in range(n):
        bit=1<<i
        for mask in range(1<<n):
            if mask&bit: dividends[mask]-=dividends[mask^bit]
    result=[0.0]*n
    for mask,d in enumerate(dividends):
        if not mask: continue
        share=d/mask.bit_count()
        for i in range(n):
            if mask&(1<<i): result[i]+=share
    return result


def state_key(report: dict) -> tuple:
    items=[]
    for coordinate,row in sorted(report.items()):
        items.extend((coordinate[0],coordinate[1],int(row["bag_count"]),int(row["distinct_entity_count"]),
                      None if row["raw_sum"] is None else float(row["raw_sum"]),float(row["value_sum_coalesced"])))
    return tuple(items)


def compile_state_transitions(reports: list[dict], n: int):
    keys=[state_key(r) for r in reports]
    transitions=[]
    for i in range(n):
        bit=1<<i; counter=Counter()
        for mask in range(1<<n):
            if not mask&bit: counter[(mask.bit_count(),keys[mask],keys[mask|bit])]+=1
        transitions.append(counter)
    return keys,transitions


def transition_shapley(transitions, state_values: dict[tuple,float], n: int) -> list[float]:
    weights=[1.0/(n*math.comb(n-1,k)) for k in range(n)]
    result=[]
    for counter in transitions:
        result.append(sum(count*weights[k]*(state_values[after]-state_values[before])
                          for (k,before,after),count in counter.items()))
    return result


def pair_interactions(values: list[float], n: int, tolerance=1e-12) -> dict:
    nonzero=0; maximum=0.0; l1=0.0
    for i in range(n):
        for j in range(i+1,n):
            bits=(1<<i)|(1<<j)
            for mask in range(1<<n):
                if mask&bits: continue
                delta=values[mask|bits]-values[mask|(1<<i)]-values[mask|(1<<j)]+values[mask]
                if abs(delta)>tolerance: nonzero+=1
                maximum=max(maximum,abs(delta)); l1+=abs(delta)
    return {"nonzero_pair_contexts":nonzero,"max_abs_second_difference":maximum,"l1_second_differences":l1}

