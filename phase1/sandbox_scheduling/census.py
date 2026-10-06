"""Outcome-blind syntactic resource census of an EXISTING frozen public sample.

No source execution or runtime inference. A missing hint is UNKNOWN, not CPU-only.
CPU/GPU settings can be conditional, unused, or inside dead code. Counts describe
source occurrences, not performance, demand bounds, representativeness or novelty.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import time


BASE = Path('/research/d7/spc/yzyang4')
ROOT = BASE / 'external-gome-structure-20261004-v1'
SAMPLE = BASE / 'collateral-sample-20261006-v1/sample.json'
STRUCTURE = BASE / 'collateral-sample-20261006-v1/structure.json'
STRUCTURE_SHA = '82bcbbfcb7f1022b246fce0703e81de4a788c67d5fc5d1b3fc0285f77fc077d5'
PINS = {
    'Trace_1.json': 'ee50756cd940a1add0e44bcbb04e710233709d81f823111d70846cfe6278afb0',
    'Trace_2.json': '5a451c60ead8ac85e8eca86502cd92efe3ff1d12949510ccec394ca44dfe4cbd',
    'Trace_3.json': '8977dd468ed50d22aa173cb0aec208286e9b73142b72568861b60d55b3243ae2',
}
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
BACKENDS = frozenset('sklearn torch torchvision transformers tensorflow keras xgboost lightgbm catboost cuml cupy'.split())
CPU_KNOBS = frozenset('n_jobs nthread num_threads thread_count'.split())
RESOURCE_KNOBS = CPU_KNOBS | frozenset('batch_size per_device_train_batch_size per_device_eval_batch_size num_workers max_length image_size img_size device task_type tree_method predictor'.split())
GPU_VALUES = frozenset(('gpu', 'cuda', 'gpu_hist', 'gpu_predictor'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def literal(node):
    if isinstance(node, ast.Constant) and type(node.value) in (str, int, float, bool, type(None)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = literal(node.operand)
        return -value if type(value) in (int, float) else None
    return None


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted(node.value)
        return prefix + '.' + node.attr if prefix else node.attr
    return ''


def resource_settings(tree):
    """Explicit literal settings only; indirect expansion remains unknown."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg in RESOURCE_KNOBS:
                    yield kw.arg, literal(kw.value)
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                name = literal(key) if key is not None else None
                if isinstance(name, str) and name in RESOURCE_KNOBS:
                    yield name, literal(value)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                name = target.id.lower() if isinstance(target, ast.Name) else None
                if name in RESOURCE_KNOBS and node.value is not None:
                    yield name, literal(node.value)


def inspect(code):
    try:
        tree = ast.parse(code)
    except (SyntaxError, RecursionError, ValueError, MemoryError):
        return dict(parsed=False, flags=None, backends=None, resource_setting_fingerprint=None)
    imports, aliases = set(), {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for value in node.names:
                imports.add(value.name.split('.')[0])
                aliases[value.asname or value.name.split('.')[0]] = value.name if value.asname else value.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            imports.add(module.split('.')[0])
            for value in node.names:
                aliases[value.asname or value.name] = module + '.' + value.name
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = dotted(node.func)
            prefix, sep, suffix = name.partition('.')
            resolved = aliases.get(prefix, prefix) + (sep + suffix if sep else '')
            calls.append((resolved, node))
    settings = list(resource_settings(tree))
    gpu_setting = any(name in {'device', 'task_type', 'tree_method', 'predictor'}
                      and isinstance(value, str) and (value.lower() in GPU_VALUES or value.lower().startswith('cuda:'))
                      for name, value in settings)
    gpu_calls = False
    for name, node in calls:
        if name.endswith('.cuda') or name == 'cuda':
            gpu_calls = True
        if name.endswith('.to') or name in {'torch.device', 'torch.tensor', 'torch.as_tensor'}:
            for arg in node.args:
                value = literal(arg)
                if isinstance(value, str) and (value.lower() == 'cuda' or value.lower().startswith('cuda:')):
                    gpu_calls = True
    flags = dict(
        explicit_gpu_hint=gpu_setting or gpu_calls,
        cuda_availability_branch_hint=any(name == 'torch.cuda.is_available' for name, _ in calls),
        gpu_backend_import=bool(imports & {'torch', 'tensorflow', 'keras', 'transformers', 'cuml', 'cupy'}),
        sklearn_import='sklearn' in imports,
        all_cpu_knob=any(name in CPU_KNOBS and type(value) is int and value == -1 for name, value in settings),
        fixed_positive_cpu_knob=any(name in CPU_KNOBS and type(value) is int and value > 0 for name, value in settings),
        cpu_count_query=any(name in {'os.cpu_count', 'multiprocessing.cpu_count', 'psutil.cpu_count'} for name, _ in calls),
        thread_setter=any(name in {'torch.set_num_threads', 'torch.set_num_interop_threads', 'threadpoolctl.threadpool_limits'} for name, _ in calls),
        dataloader_worker_hint=any(name == 'num_workers' and type(value) is int and value > 0 for name, value in settings),
        subprocess_hint=any(name.startswith('subprocess.') or name in {'os.system', 'os.popen'} for name, _ in calls),
        has_for_loop=any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree)),
        explicit_gpu_release_hint=any(name == 'torch.cuda.empty_cache' for name, _ in calls),
    )
    # Hash only recognized knobs/primitive literal values. Never export raw strings.
    normalized = sorted((key, json.dumps(value, sort_keys=True)) for key, value in settings)
    return dict(parsed=True, flags=flags, backends=sorted(imports & BACKENDS),
                resource_setting_fingerprint=sha(json.dumps(normalized).encode()))


def get_pair(obj, row):
    record = obj[row['task']][row['loop']]
    a, b = record['base_code'], record['code']
    if not isinstance(a, str) or not isinstance(b, str):
        raise ValueError('unexpected code type')
    if sha(a.encode()) != row['base_sha256'] or sha(b.encode()) != row['code_sha256']:
        raise ValueError('selected source hash mismatch')
    return a, b  # No score, feedback, scenario, runtime or intent field access.


def summarize(rows):
    parsed = [r for r in rows if r['parsed']]
    counts = Counter(k for r in parsed for k, value in r['flags'].items() if value)
    task_rows = []
    for task in sorted({r['task'] for r in rows}):
        subset = [r for r in rows if r['task'] == task]
        ok = [r for r in subset if r['parsed']]
        task_rows.append(dict(task=task, programs=len(subset), parsed=len(ok),
                              flags=dict(Counter(k for r in ok for k,v in r['flags'].items() if v))))
    return dict(programs=len(rows), parsed=len(parsed), parse_failed=len(rows)-len(parsed),
                tasks=len(task_rows), flag_counts=dict(counts), by_task=task_rows)


def read_pinned(path, expected=None):
    raw = path.read_bytes()
    if expected is not None and sha(raw) != expected:
        raise ValueError('source hash mismatch')
    if SECRET.search(raw):
        raise ValueError('credential-shaped source withheld')
    return raw


def save(path, value):
    with path.open('x', encoding='utf-8') as file:
        json.dump(value, file, indent=2, sort_keys=True, allow_nan=False)
        file.write('\n')


def main(output, commit):
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('exact base commit required')
    os.umask(0o077)
    def deadline(*_):
        raise TimeoutError('bounded census timeout')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(120)
    started = time.monotonic()
    old = json.loads(read_pinned(STRUCTURE, STRUCTURE_SHA))
    sample_bytes = read_pinned(SAMPLE, old['sample_sha256'])
    selected = json.loads(sample_bytes)['selected']
    output.mkdir(mode=0o700, exist_ok=False)
    plan = dict(source_commit=commit, script_sha256=sha(Path(__file__).read_bytes()), source_pins=PINS,
                frozen_sample_sha256=sha(sample_bytes), selection='unchanged prior public sample, both endpoints',
                primary_unit='unique task and exact source SHA; parents/children dependent',
                max_seconds=120, gpu_hours=0, api_calls=0, candidate_executions=0,
                claim='syntactic occurrences only; not runtime, resource bounds or an unbiased production census')
    save(output/'plan.json', plan)
    programs, pairs = {}, []
    for filename, pin in PINS.items():
        download = json.loads(read_pinned(ROOT/(filename+'.download.json')))
        if download['sha256'] != pin or download['credential_categories']:
            raise ValueError('prior download receipt not clean')
        obj = json.loads(read_pinned(ROOT/filename, pin))
        for row in selected:
            if row['file'] != filename:
                continue
            left, right = get_pair(obj, row)
            keys = []
            for code in (left, right):
                key = (row['task'], sha(code.encode()))
                keys.append(key)
                if key not in programs:
                    programs[key] = dict(task=key[0], source_sha256=key[1], **inspect(code))
            a, b = [programs[k] for k in keys]
            pairs.append(dict(task=row['task'], parsed=a['parsed'] and b['parsed'],
                setting_inventory_changed=(a['resource_setting_fingerprint'] != b['resource_setting_fingerprint'])
                    if a['parsed'] and b['parsed'] else None,
                hint_flags_changed=(a['flags'] != b['flags']) if a['parsed'] and b['parsed'] else None))
        del obj
    if len(pairs) != len(selected):
        raise ValueError('frozen sample coverage incomplete')
    summary = dict(**summarize(list(programs.values())), frozen_pairs=len(pairs),
                   pair_setting_inventory_changed=sum(p['setting_inventory_changed'] is True for p in pairs),
                   pair_hint_flags_changed=sum(p['hint_flags_changed'] is True for p in pairs),
                   pair_parse_failed=sum(not p['parsed'] for p in pairs),
                   source_sample_sha256=sha(sample_bytes), script_sha256=plan['script_sha256'],
                   elapsed_seconds=time.monotonic()-started, outcome_fields_accessed=False,
                   candidates_executed=False, actual_gpu_usage='unmeasured', actual_cpu_usage='unmeasured')
    save(output/'program_hints.json', list(programs.values()))
    save(output/'summary.json', summary)
    print(json.dumps({k:v for k,v in summary.items() if k != 'by_task'}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    config = parser.parse_args()
    main(config.output, config.commit)
