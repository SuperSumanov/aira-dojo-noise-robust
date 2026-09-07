"""Diagnose projected historical journal roles; never select or repair nodes.

Canonical checkpoint role predates this diagnostic (source ledger faf04cc).
Live journals are event streams, not interchangeable copies of checkpoints.
Conflicts remain represented; no role is merged, admitted or executed here.
"""
from collections import Counter, defaultdict
import json

ROLES = {'checkpoint', 'live'}
FIELDS = ('parents', 'code_sha256', 'code_bytes', 'nonempty_code', 'node_id_sha256')


def signature(node):
    return json.dumps(node, sort_keys=True, separators=(',', ':'))


def diagnose(projected):
    if set(projected) != ROLES:
        raise ValueError('exact_journal_roles_required')
    groups = {}
    role_counts = {}
    for role in sorted(ROLES):
        p = projected[role]
        by_step = defaultdict(list)
        for node in p['nodes']:
            by_step[node['step']].append(node)
        groups[role] = by_step
        distinct = {s: len({signature(n) for n in nodes}) for s, nodes in by_step.items()}
        role_counts[role] = {
            'rows': len(p['nodes']), 'unsupported_lines': p['unsupported_lines'],
            'unique_steps': len(by_step),
            'duplicate_step_rows': len(p['nodes']) - len(by_step),
            'conflicting_steps': sum(n > 1 for n in distinct.values()),
            'identical_repeated_rows': sum(len(by_step[s]) - n for s, n in distinct.items()),
        }
    a, b = groups['checkpoint'], groups['live']
    common = set(a) & set(b)
    different = Counter({k: 0 for k in FIELDS})
    unequal = 0
    for s in common:
        unequal += {signature(n) for n in a[s]} != {signature(n) for n in b[s]}
        for field in FIELDS:
            encode = lambda rows: {json.dumps(n[field], sort_keys=True) for n in rows}
            different[field] += encode(a[s]) != encode(b[s])
    return {
        'roles': role_counts,
        'cross_role': {'shared_steps': len(common), 'unequal_projected_steps': unequal,
                       'checkpoint_only_steps': len(set(a) - set(b)),
                       'live_only_steps': len(set(b) - set(a)),
                       'field_difference_steps': dict(different)},
        'canonical_role_prior_source': 'checkpoint',
        'nodes_selected': 0, 'source_admitted': False, 'executability_verified': False,
    }
