"""Outcome-free source-equality linkage check; no execution of trace code.

Numeric loop order is an exported index, not independently verified chronology.
Exact code matches do not prove parentage, independent runs, or equal model state.
"""
import collections
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import signal
import sys
import time

SOURCE = Path('/research/d7/spc/yzyang4/external_gome_structure_20261004.py')
SOURCE_SHA = '15761ca11604cea892be62804b5d4068918ad2bb09d36f011323a13203c10814'
ROOT = Path('/research/d7/spc/yzyang4/external-gome-structure-20261004-v1')
KEYS = ('loops', 'nonempty_pairs', 'base_matches_earlier_code',
        'base_matches_immediate_previous_loop_code', 'base_unmatched_earlier_code',
        'unique_code_pairs', 'repeated_code_pairs')


def rows_from(obj):
    """Only source fields and exported loop indices are accessed."""
    groups = []
    for task in obj.values():
        rows = []
        for name, loop in task.items():
            if name == 'scenario':
                continue
            assert name.startswith('loop_') and name[5:].isdigit()
            base, code = loop.get('base_code'), loop.get('code')
            rows.append((int(name[5:]), base if isinstance(base, str) else '',
                         code if isinstance(code, str) else ''))
        rows.sort(key=lambda x: x[0])
        assert len({r[0] for r in rows}) == len(rows)
        groups.append(rows)
    return groups


def count_hash(groups):
    c = collections.Counter({k: 0 for k in KEYS})
    pairs = set()
    for rows in groups:
        seen, previous = set(), None
        for _, base, code in rows:
            c['loops'] += 1
            b = hashlib.sha256(base.encode()).digest() if base.strip() else None
            d = hashlib.sha256(code.encode()).digest() if code.strip() else None
            if b is not None and d is not None:
                c['nonempty_pairs'] += 1
                c['base_matches_earlier_code'] += int(b in seen)
                c['base_matches_immediate_previous_loop_code'] += int(b == previous)
                c['base_unmatched_earlier_code'] += int(b not in seen)
                pairs.add((b, d))
            if d is not None:
                seen.add(d)
            previous = d
    c['unique_code_pairs'] = len(pairs)
    c['repeated_code_pairs'] = c['nonempty_pairs'] - len(pairs)
    return dict(c)


def count_exact(groups):
    """Second computation uses direct strings and list search, not hash lookup."""
    valid = [(rows, i, b, d) for rows in groups for i, (_, b, d) in enumerate(rows)
             if b.strip() and d.strip()]
    earlier = sum(any(b == old[2] for old in rows[:i]) for rows, i, b, _ in valid)
    immediate = sum(i > 0 and b == rows[i-1][2] for rows, i, b, _ in valid)
    unique = len({(b, d) for _, _, b, d in valid})
    return dict(zip(KEYS, [sum(map(len, groups)), len(valid), earlier, immediate,
                           len(valid)-earlier, unique, len(valid)-unique]))


def tests():
    class Forbidden:
        def __bool__(self):
            raise AssertionError('forbidden access')
        def __str__(self):
            raise AssertionError('forbidden access')
    f = Forbidden()
    row = lambda b, c: {'base_code': b, 'code': c, 'valid_score': f, 'test_report': f,
                        'feedback': f, 'final_hypothesis': f, 'task': f}
    obj = {'synthetic': {'scenario': f, 'loop_2': row('a', 'c'),
                         'loop_0': row('start', 'a'), 'loop_1': row('a', 'b'),
                         'loop_3': row('a', '')}}
    a = count_hash(rows_from(obj))
    assert a == count_exact(rows_from(obj))
    assert [a[k] for k in KEYS] == [4, 3, 2, 1, 1, 3, 0]
    duplicate = [[(0, 'a', 'b'), (1, 'a', 'b')]]
    assert count_hash(duplicate) == count_exact(duplicate)
    assert count_hash(duplicate)['repeated_code_pairs'] == 1
    separated = [[(0, '', 'a')], [(0, 'a', 'b')]]
    assert count_hash(separated) == count_exact(separated)
    assert count_hash(separated)['base_matches_earlier_code'] == 0
    return {'fixtures': 3, 'forbidden_value_sentinel': 'PASS', 'dual_implementation': 'PASS'}


def save(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')


def main():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA
    spec = importlib.util.spec_from_file_location('pinned_census', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    started = time.time()
    plan = {'schema': 'external-gome-linkage-plan-v1', 'tests': tests(),
            'source_pins': module.FILES, 'census_script_sha256': SOURCE_SHA,
            'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'start_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'max_seconds': 180, 'gpu_hours': 0, 'model_fits': 0, 'generator_calls': 0,
            'boundary': __doc__, 'selection': 'all three previously credential-scanned exact files'}
    save(ROOT / 'linkage-plan.json', plan)
    def timeout(signum, frame):
        raise TimeoutError('hard_wall_limit')
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(180)
    output, error = [], None
    try:
        for name, (size, sha) in module.FILES.items():
            raw = (ROOT / name).read_bytes()
            assert len(raw) == size and hashlib.sha256(raw).hexdigest() == sha
            receipt = json.loads((ROOT / (name + '.download.json')).read_text())
            assert receipt['sha256'] == sha and not receipt['credential_categories']
            groups = rows_from(json.loads(raw))
            del raw
            first, second = count_hash(groups), count_exact(groups)
            assert first == second, 'independent_count_mismatch'
            output.append({'file': name, 'counts': first, 'dual_implementation': 'PASS'})
            del groups
    except Exception as exc:
        error = type(exc).__name__
    finally:
        signal.alarm(0)
    result = {'schema': 'external-gome-linkage-v1', 'status': 'COMPLETE' if error is None else 'FAIL_CLOSED',
              'error_type': error, 'files': output, 'assigned_files': 3,
              'elapsed_seconds': time.time()-started, 'boundary': __doc__,
              'plan_sha256': hashlib.sha256((ROOT/'linkage-plan.json').read_bytes()).hexdigest(),
              'source_content_exported': False, 'outcome_values_accessed_by_counter': False}
    save(ROOT / 'linkage.json', result)
    print(json.dumps(result, sort_keys=True))
    return 0 if error is None else 2


if __name__ == '__main__':
    if sys.argv[1:] == ['--tests']:
        print(json.dumps(tests(), sort_keys=True))
    else:
        assert sys.argv[1:] == []
        raise SystemExit(main())
