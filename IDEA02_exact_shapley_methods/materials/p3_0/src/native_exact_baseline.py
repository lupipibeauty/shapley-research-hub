from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction

from build_lineage import EntityLineage


FALSE=("F",); TRUE=("T",)


def canonical_dnf(clauses):
    unique={frozenset(c) for c in clauses}
    if frozenset() in unique:return TRUE
    if not unique:return FALSE
    minimal={c for c in unique if not any(other<c for other in unique)}
    return tuple(sorted((tuple(sorted(c)) for c in minimal),key=lambda x:(len(x),x)))


def restrict_formula(formula,var,value):
    if formula in (TRUE,FALSE):return formula
    if value:
        return canonical_dnf(tuple(tuple(x for x in clause if x!=var) for clause in formula))
    return canonical_dnf(tuple(clause for clause in formula if var not in clause))


@dataclass
class DiagramAudit:
    n_players: int
    nonterminal_nodes: int
    terminal_nodes: int
    layer_widths: dict[int,int]
    root_id: int


class LayeredJointDecisionDiagram:
    """Classic ordered multi-terminal decision diagram for (q_A,q_B).

    It is constructed from fact-level lineage. Every path has one layer per player,
    so conditional coalition-size model counts require no skipped-variable correction.
    """
    def __init__(self,lineage:tuple[EntityLineage,...],n_players:int):
        self.lineage=lineage;self.n=n_players;self.nodes={};self.terminals={};self._unique={};self._next=0
        self.groups=tuple(e.group_id for e in lineage)
        initial=tuple(canonical_dnf(e.clauses) for e in lineage)
        self.root=self._build(0,initial)

    def _new_id(self):
        value=self._next;self._next+=1;return value

    def _terminal(self,state):
        qa=sum(f==TRUE and g=="A" for f,g in zip(state,self.groups,strict=True))
        qb=sum(f==TRUE and g=="B" for f,g in zip(state,self.groups,strict=True))
        output=(int(qa),int(qb))
        for node,out in self.terminals.items():
            if out==output:return node
        node=self._new_id();self.terminals[node]=output;return node

    def _build(self,level,state):
        if level==self.n:return self._terminal(state)
        key=(level,state)
        if key in self._unique:return self._unique[key]
        low_state=tuple(restrict_formula(f,level,0) for f in state)
        high_state=tuple(restrict_formula(f,level,1) for f in state)
        low=self._build(level+1,low_state);high=self._build(level+1,high_state)
        node=self._new_id();self.nodes[node]=(level,low,high);self._unique[key]=node
        return node

    def audit(self):
        widths=Counter(level for level,_,_ in self.nodes.values())
        return DiagramAudit(self.n,len(self.nodes),len(self.terminals),dict(sorted(widths.items())),self.root)

    def distribution(self,focus:int|None=None,forced:int|None=None):
        if (focus is None)!=(forced is None):raise ValueError("focus and forced must be both set or both None")
        frontier=Counter({(self.root,0):1})
        for level in range(self.n):
            new=Counter()
            for (node,k),count in frontier.items():
                node_level,low,high=self.nodes[node]
                if node_level!=level:raise AssertionError("diagram is not layered")
                if focus==level:
                    new[(high if forced else low,k)]+=count
                else:
                    new[(low,k)]+=count;new[(high,k+1)]+=count
            frontier=new
        output=Counter()
        for (terminal,k),count in frontier.items():output[(k,*self.terminals[terminal])]+=count
        return output

    def all_conditional_distributions(self):
        return {(i,b):self.distribution(i,b) for i in range(self.n) for b in (0,1)}


def game_value(game_id,qa,qb):
    if game_id=="G0":return qa+qb
    if game_id=="G1":return min(qa,qb)
    raise KeyError(game_id)


def shapley_from_conditional(distributions,n,game_id):
    result=[]
    for i in range(n):
        total=Fraction(0)
        absent,present=distributions[(i,0)],distributions[(i,1)]
        for k in range(n):
            sum0=sum(count*game_value(game_id,qa,qb) for (size,qa,qb),count in absent.items() if size==k)
            sum1=sum(count*game_value(game_id,qa,qb) for (size,qa,qb),count in present.items() if size==k)
            total+=Fraction(sum1-sum0,n*math.comb(n-1,k))
        result.append(total)
    return result

