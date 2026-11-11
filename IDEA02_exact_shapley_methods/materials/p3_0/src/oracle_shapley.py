from __future__ import annotations

import math
from fractions import Fraction


def subset_shapley(values,n):
    result=[]
    for i in range(n):
        bit=1<<i;total=Fraction(0)
        for mask in range(1<<n):
            if not mask&bit:
                total+=Fraction(values[mask|bit]-values[mask],n*math.comb(n-1,mask.bit_count()))
        result.append(total)
    return result


def mobius_shapley(values,n):
    d=list(map(Fraction,values))
    for i in range(n):
        bit=1<<i
        for mask in range(1<<n):
            if mask&bit:d[mask]-=d[mask^bit]
    result=[Fraction(0) for _ in range(n)]
    for mask,value in enumerate(d):
        if not mask:continue
        share=value/mask.bit_count()
        for i in range(n):
            if mask&(1<<i):result[i]+=share
    return result

