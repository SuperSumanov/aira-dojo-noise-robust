"""Pinned public-source availability census, not a model/effect experiment.

Raw third-party traces stay in a mode-0700 remote directory. Never print source,
hypotheses, feedback, validation/test values, URLs after redirects, or credentials.
Only field types/presence and exact source-byte equality are summarized. No source
is imported, compiled, or executed. No predictive fit or evaluator is called.
"""
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys
import time
import urllib.request

ROOT = Path('/research/d7/spc/yzyang4/external-gome-structure-20261004-v1')
REPO = 'amstrongzyf/Gome-GPT5-Traces'
REVISION = '35fc17013ab0ded2f578eacb1f606b0b9e45a1d3'
FILES = {
    'Trace_1.json': (219029856, 'ee50756cd940a1add0e44bcbb04e710233709d81f823111d70846cfe6278afb0'),
    'Trace_2.json': (204593757, '5a451c60ead8ac85e8eca86502cd92efe3ff1d12949510ccec394ca44dfe4cbd'),
    'Trace_3.json': (121081711, '8977dd468ed50d22aa173cb0aec208286e9b73142b72568861b60d55b3243ae2'),
}
PATTERNS = {
    'provider_token': rb'(?<![A-Za-z0-9_-])sk-(?:or-v1-|proj-)?[A-Za-z0-9_-]{20,}',
    'aws_access': rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'private_key': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'assigned_secret': rb'''(?i)(?:api[_-]?key|access[_-]?token|secret[_-]?key)[\s\\]*["']?\s*[:=]\s*["'][A-Za-z0-9+/_.=-]{24,}["']''',
}


def save(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write('\n')


def census(obj):
    """No score/feedback accessor; only enumerate loop containers and code fields."""
    assert isinstance(obj, dict)
    counts = collections.Counter()
    tasks = []
    for task_name, task in obj.items():
        assert isinstance(task_name, str) and isinstance(task, dict)
        assert re.fullmatch(r'[A-Za-z0-9_-]+', task_name)
        tasks.append(task_name)
        counts['tasks'] += 1
        for loop_name, loop in task.items():
            if loop_name == 'scenario':
                counts['scenario_containers'] += 1
                continue
            assert re.fullmatch(r'loop_\d+', loop_name), 'unexpected_container'
            assert isinstance(loop, dict)
            counts['loops'] += 1
            base = loop.get('base_code')
            code = loop.get('code')
            counts['base_code_present'] += int('base_code' in loop)
            counts['code_present'] += int('code' in loop)
            counts['base_code_is_string'] += int(isinstance(base, str))
            counts['code_is_string'] += int(isinstance(code, str))
            paired = isinstance(base, str) and bool(base.strip()) and isinstance(code, str) and bool(code.strip())
            counts['nonempty_code_pairs'] += int(paired)
            counts['byte_equal_code_pairs'] += int(paired and base == code)
            counts['has_final_hypothesis'] += int(isinstance(loop.get('final_hypothesis'), dict))
            counts['has_task_specification'] += int(isinstance(loop.get('task'), dict))
            counts['paired_with_intent_and_task'] += int(paired and isinstance(loop.get('final_hypothesis'), dict) and isinstance(loop.get('task'), dict))
    return {'counts': dict(counts), 'task_names': sorted(tasks)}


def tests():
    class Forbidden:
        def __str__(self):
            raise AssertionError('forbidden_value_rendered')
        def __bool__(self):
            raise AssertionError('forbidden_value_used')
    hidden = Forbidden()
    row = {'base_code': 'a', 'code': 'a', 'final_hypothesis': {}, 'task': {},
           'valid_score': hidden, 'test_report': hidden, 'feedback': hidden,
           'sota_hypothesis': hidden, 'running_time': hidden}
    result = census({'synthetic-task': {'scenario': hidden, 'loop_0': row}})
    assert result['counts']['paired_with_intent_and_task'] == 1
    assert result['counts']['byte_equal_code_pairs'] == 1
    missing = census({'synthetic-task': {'loop_0': {'base_code': '', 'code': 'x'}, 'loop_1': {}}})
    assert missing['counts']['loops'] == 2 and missing['counts']['nonempty_code_pairs'] == 0
    different = census({'synthetic-task': {'loop_0': {**row, 'code': 'b'}}})
    assert different['counts']['nonempty_code_pairs'] == 1 and different['counts']['byte_equal_code_pairs'] == 0
    assert not re.search(PATTERNS['provider_token'], b'task-feedback-generated-code-abcdefghijklmnop')
    return {'structural_fixtures': 3, 'forbidden_value_sentinel': 'PASS', 'path_false_positive_control': 'PASS'}


def download_and_scan(name, expected_size, expected_sha):
    path = ROOT / name
    digest = hashlib.sha256()
    hits = set()
    seen = 0
    overlap = b''
    request = urllib.request.Request(
        f'https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{name}',
        headers={'User-Agent': 'MLE-research-source-metadata/1.0'})
    with path.open('xb') as out, urllib.request.urlopen(request, timeout=45) as response:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            seen += len(chunk)
            assert seen <= expected_size, 'size_limit'
            digest.update(chunk)
            out.write(chunk)
            scan = overlap + chunk
            for category, pattern in PATTERNS.items():
                if re.search(pattern, scan):
                    hits.add(category)
            overlap = scan[-4096:]
    receipt = {'file': name, 'bytes': seen, 'sha256': digest.hexdigest(),
               'size_pass': seen == expected_size, 'hash_pass': digest.hexdigest() == expected_sha,
               'credential_categories': sorted(hits)}
    save(ROOT / (name + '.download.json'), receipt)
    assert receipt['size_pass'] and receipt['hash_pass'], 'source_identity_failure'
    assert not hits, 'credential_shape_hit_quarantined'
    return receipt


def main():
    os.umask(0o077)
    ROOT.mkdir(mode=0o700, exist_ok=False)
    started = time.time()
    plan = {'schema': 'external-gome-structure-plan-v1', 'repo': REPO, 'revision': REVISION,
            'files': {k: {'size': v[0], 'sha256': v[1]} for k, v in FILES.items()},
            'license_metadata': 'apache-2.0', 'source_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'start_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'max_wall_seconds': 900, 'gpu_hours': 0, 'model_fits': 0, 'generator_calls': 0,
            'protocol': 'All three exact files; credential scan before JSON decode. Ignore outcome/feedback/scenario values. No source export or execution, no selection of successful trajectories.',
            'boundary': 'Author-selected published traces, missing final multi-seed selection. Availability census only; not independent task trials, faithful reproduction, effect measurement or novelty evidence.',
            'tests': tests()}
    save(ROOT / 'plan.json', plan)
    def timeout(signum, frame):
        raise TimeoutError('hard_wall_limit')
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(900)
    rows = []
    status = 'COMPLETE'
    error_type = None
    try:
        for name, (size, sha) in FILES.items():
            receipt = download_and_scan(name, size, sha)
            print(json.dumps({'stage': 'download_verified', 'file': name, 'bytes': size}), flush=True)
            with (ROOT / name).open(encoding='utf-8') as f:
                obj = json.load(f)
            structure = census(obj)
            del obj
            row = {**receipt, **structure}
            save(ROOT / (name + '.structure.json'), row)
            rows.append(row)
            print(json.dumps({'stage': 'structure_complete', 'file': name, 'counts': row['counts']}), flush=True)
    except Exception as error:
        status = 'FAIL_CLOSED'
        error_type = type(error).__name__
    finally:
        signal.alarm(0)
    aggregate = {'schema': 'external-gome-structure-v1', 'status': status,
                 'error_type': error_type, 'revision': REVISION, 'assigned_files': len(FILES),
                 'completed_files': len(rows), 'files': rows,
                 'unique_task_names': sorted({t for row in rows for t in row['task_names']}),
                 'elapsed_seconds': time.time()-started, 'end_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 'plan_sha256': hashlib.sha256((ROOT/'plan.json').read_bytes()).hexdigest(),
                 'boundary': plan['boundary'], 'score_values_exported': False, 'source_content_exported': False}
    save(ROOT / 'structure.json', aggregate)
    print(json.dumps({'status': status, 'completed_files': len(rows), 'error_type': error_type}), flush=True)
    return 0 if status == 'COMPLETE' else 2


if __name__ == '__main__':
    if sys.argv[1:] == ['--tests']:
        print(json.dumps(tests(), sort_keys=True))
    else:
        assert sys.argv[1:] == []
        raise SystemExit(main())
