"""Label-free encoding diagnostics on a separately authorized historical scope.

No file IO, tokenizer/model loading, training, selection, or source admission.
Collisions detect complete indistinguishability, not semantic edit retention.
"""
from collections import defaultdict
from itertools import combinations
import statistics


LIMITS = (2048, 8192, 16384)


def truncate(ids, limit):
    if len(ids) <= limit:
        return tuple(ids)
    head = limit // 4
    return tuple(ids[:head]) + tuple(ids[-(limit-head):])


def summarize(runs):
    """Runs contain task, component, nodes; nodes have step/parents/code_sha/tokens.

    Every supplied node must have nonempty code. No result/label key is accepted.
    Counts retain all same-parent unordered pairs; no outcome-dependent filtering.
    """
    assert type(runs) is list and runs
    per_limit = {n: defaultdict(int) for n in LIMITS}
    task_counts = {n: defaultdict(lambda: defaultdict(int)) for n in LIMITS}
    run_lengths = []
    all_lengths = []
    pair_total = distinct_total = full_collisions = 0
    tasks = set()
    components = set()
    for run in runs:
        assert set(run) == {'task', 'component', 'nodes'}
        assert isinstance(run['task'], str) and run['task']
        assert isinstance(run['component'], str) and run['component']
        tasks.add(run['task']); components.add(run['component'])
        nodes = run['nodes']; assert isinstance(nodes, list)
        assert len({n['step'] for n in nodes}) == len(nodes)
        lengths = []
        for node in nodes:
            assert set(node) == {'step', 'parents', 'code_sha', 'tokens'}
            assert type(node['step']) is int and isinstance(node['parents'], list)
            assert len(node['parents']) == len(set(node['parents']))
            assert type(node['code_sha']) is str and len(node['code_sha']) == 64
            assert isinstance(node['tokens'], tuple) and node['tokens']
            assert all(type(t) is int and t >= 0 for t in node['tokens'])
            lengths.append(len(node['tokens']))
        if lengths:
            run_lengths.append(statistics.mean(lengths)); all_lengths.extend(lengths)
        for limit in LIMITS:
            c = per_limit[limit]; t = task_counts[limit][run['task']]
            for length in lengths:
                for dst in (c, t):
                    dst['programs'] += 1
                    dst['truncated_programs'] += length > limit
                    dst['full_tokens'] += length
                    dst['retained_tokens'] += min(length, limit)
        for a, b in combinations(nodes, 2):
            if not a['parents'] or sorted(a['parents']) != sorted(b['parents']):
                continue
            pair_total += 1
            if a['code_sha'] == b['code_sha']:
                continue
            distinct_total += 1
            full_equal = a['tokens'] == b['tokens']
            full_collisions += full_equal
            for limit in LIMITS:
                equal = truncate(a['tokens'], limit) == truncate(b['tokens'], limit)
                for dst in (per_limit[limit], task_counts[limit][run['task']]):
                    dst['byte_distinct_sibling_pairs'] += 1
                    dst['encoded_equal_sibling_pairs'] += equal
                    dst['truncation_induced_equal_pairs'] += equal and not full_equal
    assert all_lengths
    def finish(c):
        d = dict(c)
        for k in ('byte_distinct_sibling_pairs', 'encoded_equal_sibling_pairs', 'truncation_induced_equal_pairs'):
            d.setdefault(k, 0)
        d['truncated_program_fraction'] = d['truncated_programs']/d['programs'] if d['programs'] else None
        d['retained_token_fraction'] = d['retained_tokens']/d['full_tokens'] if d['full_tokens'] else None
        return d
    return {'classification': 'HISTORICAL_INPUT_OBSERVABILITY_NOT_MODEL_EFFECT_OR_SOURCE_ADMISSION',
            'runs': len(runs), 'components': len(components), 'tasks': len(tasks),
            'programs': len(all_lengths), 'median_full_tokens': statistics.median(all_lengths),
            'max_full_tokens': max(all_lengths), 'run_macro_mean_full_tokens': statistics.mean(run_lengths),
            'same_parent_nonempty_pairs': pair_total, 'byte_distinct_sibling_pairs': distinct_total,
            'full_token_equal_byte_distinct_sibling_pairs': full_collisions,
            'contexts': [{'max_len': n, **finish(per_limit[n]),
                          'task_counts': [{'task': task, **finish(c)} for task, c in sorted(task_counts[n].items())]}
                         for n in LIMITS],
            'labels_read': False, 'model_loaded_or_fit': False, 'source_admitted': False,
            'semantic_edit_retention_measured': False}
