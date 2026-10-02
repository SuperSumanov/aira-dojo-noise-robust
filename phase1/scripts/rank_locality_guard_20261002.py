"""Experimental label-free, cross-group-order-preserving proposal projection.

This is a narrowly constrained ranking operator, not a guarantee of better AUC.
It preserves the parent's score multiset and all comparisons between groups.
Mixed-group ties are locked. Within each maximal single-group run of score
levels, assign the parent's sorted scores in the child's order. Child ties
retain parent order. Group definitions must be fixed without queried labels.
"""
import itertools
import math


def blocks(parent, groups):
    if len(parent) != len(groups) or not all(math.isfinite(x) for x in parent):
        raise ValueError('invalid arrays')
    order = sorted(range(len(parent)), key=lambda i: (parent[i], i))
    result=[]; current=[]; current_group=None
    for _, level_it in itertools.groupby(order, key=lambda i:parent[i]):
        level=list(level_it); kinds={groups[i] for i in level}
        if len(kinds)!=1:
            if current: result.append(current)
            current=[]; current_group=None
            # A mixed-group tied level cannot be changed while preserving
            # *all* cross-group equalities. Leave every member unchanged.
            continue
        group=next(iter(kinds))
        if current and group != current_group:
            result.append(current); current=[]
        current.extend(level); current_group=group
    if current:result.append(current)
    return result


def project(parent, child, groups):
    if len(parent)!=len(child) or not all(math.isfinite(x) for x in child):
        raise ValueError('invalid proposal')
    output=list(parent)
    for block in blocks(parent,groups):
        child_order=sorted(block, key=lambda i:(child[i], parent[i], i))
        for index,value in zip(child_order, sorted(parent[i] for i in block)):
            output[index]=value
    return output


def compare(x,y):return (x>y)-(x<y)


def certificate(parent, repaired, groups):
    if sorted(parent)!=sorted(repaired):return False
    return all(compare(parent[i],parent[j])==compare(repaired[i],repaired[j])
               for i in range(len(parent)) for j in range(i) if groups[i]!=groups[j])
