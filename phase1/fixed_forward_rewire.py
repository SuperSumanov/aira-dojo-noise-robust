"""Candidate loss-index planner, NOT a training adapter or an approved method.

Keep every original forward occurrence in place. Rewire two non-forest edges
within the SAME local microbatch; preserve the original spanning forest. Thus
each accepted swap joins two components without changing endpoint degrees.
No labels, utilities, model outputs, or cross-rank communication are inputs.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
import math


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def edge(a, b):
    require(a != b, 'self_edge')
    return tuple(sorted((a, b)))


class Union:
    def __init__(self, vertices):
        self.parents = {v: v for v in vertices}

    def find(self, v):
        while self.parents[v] != v:
            self.parents[v] = self.parents[self.parents[v]]
            v = self.parents[v]
        return v

    def join(self, a, b):
        a, b = self.find(a), self.find(b)
        if a == b:
            return False
        self.parents[max(a, b)] = min(a, b)
        return True


@dataclass(frozen=True)
class IndexPlan:
    # Each element contains pairs of indices into its UNCHANGED flat input.
    losses: tuple
    swaps: int
    forest: frozenset


def plan(batches, stratum):
    original = [edge(a, b) for batch in batches for a, b in batch]
    require(original and len(original) == len(set(original)), 'repeated_or_empty_edges')
    vertices = {v for e in original for v in e}
    require(vertices <= stratum.keys(), 'missing_metadata')
    union = Union(vertices)
    forest = set()
    for a, b in sorted(original):
        if union.join(a, b):
            forest.add((a, b))
    losses, swaps = [], 0
    for batch in batches:
        require(0 < len(batch) <= 8, 'unsupported_microbatch')
        flat = [v for e in batch for v in e]
        indices = [(2*i, 2*i+1) for i in range(len(batch))]
        used = set()
        for i, (a, b) in enumerate(batch):
            if i in used or edge(a, b) in forest:
                continue
            for j in range(i+1, len(batch)):
                c, d = batch[j]
                if j in used or edge(c, d) in forest:
                    continue
                if stratum[a] is None or not (stratum[a] == stratum[b] == stratum[c] == stratum[d]):
                    continue
                if union.find(a) == union.find(c):
                    continue
                # Distinct components imply four distinct endpoints and no
                # pre-existing cross edge. Original forest is never removed.
                require(len({a, b, c, d}) == 4, 'component_inconsistency')
                indices[i], indices[j] = (2*i, 2*j), (2*i+1, 2*j+1)
                require(union.join(a, c), 'failed_component_merge')
                used.update((i, j))
                swaps += 1
                break
        require(sorted(v for e in indices for v in e) == list(range(len(flat))), 'occurrence_loss')
        losses.append(tuple(indices))
    return IndexPlan(tuple(losses), swaps, frozenset(forest))


def bfs_components(edges):
    adjacency = defaultdict(set)
    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    todo, groups = set(adjacency), []
    while todo:
        pending, component = [min(todo)], set()
        while pending:
            v = pending.pop()
            if v not in component:
                component.add(v)
                pending.extend(adjacency[v] - component)
        todo -= component
        groups.append(component)
    return groups


def verify(batches, stratum, result):
    """Independent final-graph BFS and per-occurrence check, not DSU replay."""
    require(len(batches) == len(result.losses), 'batch_count')
    original, rewritten, by_stratum = [], [], Counter()
    for batch, indices in zip(batches, result.losses):
        flat = [v for e in batch for v in e]
        require(len(indices) == len(batch), 'loss_term_count')
        require(all(type(i) is int for e in indices for i in e), 'noninteger_index')
        require(sorted(i for e in indices for i in e) == list(range(len(flat))), 'slot_partition')
        before = {edge(*e) for e in batch}
        after = [edge(flat[i], flat[j]) for i, j in indices]
        for a, b in after:
            if (a, b) not in before:
                require(stratum[a] is not None and stratum[a] == stratum[b], 'cross_stratum')
                by_stratum[stratum[a]] += 1
        original.extend(before)
        rewritten.extend(after)
    require(len(original) == len(set(original)), 'duplicate_original')
    require(len(rewritten) == len(set(rewritten)), 'duplicate_rewritten')
    require(Counter(v for e in original for v in e) == Counter(v for e in rewritten for v in e), 'degree_change')
    require(result.forest <= set(original) & set(rewritten), 'forest_not_preserved')
    old_groups, new_groups = bfs_components(original), bfs_components(rewritten)
    membership = {v: i for i, group in enumerate(new_groups) for v in group}
    require(all(len({membership[v] for v in group}) == 1 for group in old_groups), 'old_component_split')
    changed = len(set(original) - set(rewritten))
    require(changed == 2*result.swaps == sum(by_stratum.values()), 'swap_count')
    require(len(old_groups) - len(new_groups) == result.swaps, 'component_accounting')
    return dict(pairs=len(original), endpoints=len(membership), swaps=result.swaps,
        changed_pairs=changed, changed_fraction=changed/len(original),
        original_components=len(old_groups), rewritten_components=len(new_groups),
        incidence_rank_gain=result.swaps,
        endpoint_degrees_exact=True, forward_occurrence_slots_exact=True,
        original_components_not_split=True, unique_edges=True)


def bce_reference(scores, indices, targets):
    """Scalar finite-difference reference only; not used with real data or fit.

Tie target=.5 keeps a loss term instead of dropping one arm's pair post hoc.
Future labels require verified scores; local binary directions cannot infer
cross-component order. This policy is not retroactively added to frozen v2.
"""
    require(len(indices) == len(targets) > 0, 'target_count')
    require(sorted(i for e in indices for i in e) == list(range(len(scores))), 'slot_partition')
    require(all(math.isfinite(s) for s in scores), 'nonfinite_score')
    gradient, loss = [0.0]*len(scores), 0.0
    for (a, b), target in zip(indices, targets):
        require(target in (0.0, 0.5, 1.0), 'invalid_target')
        d = scores[a] - scores[b]
        loss += max(d, 0) + math.log1p(math.exp(-abs(d))) - target*d
        sigmoid = 1/(1+math.exp(-d)) if d >= 0 else math.exp(d)/(1+math.exp(d))
        g = (sigmoid-target)/len(indices)
        gradient[a] += g
        gradient[b] -= g
    return loss/len(indices), gradient
