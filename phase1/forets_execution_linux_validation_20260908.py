"""Bounded new task-return tests, including one benign real CPU interpreter call."""
import hashlib
import json
import multiprocessing
import os
import platform
import sys
import time
from pathlib import Path


def main():
    import pytest
    from phase1 import forets_execution_patch_20260908 as build
    cache_path = Path(os.environ['FORETS_EXECUTION_CACHE'])
    before = hashlib.sha256(cache_path.read_bytes()).hexdigest()
    cache = json.loads(cache_path.read_bytes())
    for path in cache['sources']:
        build.source(path)
    assert not multiprocessing.active_children(), 'unexpected existing test children'
    start = time.monotonic()
    rc = pytest.main(['phase1/tests/test_forets_execution_witness_20260908.py',
                     '-q', '-p', 'no:cacheprovider', '--junitxml=linux_tests.xml'])
    assert hashlib.sha256(cache_path.read_bytes()).hexdigest() == before
    children = multiprocessing.active_children()
    receipt = dict(classification='TASK_RETURN_RECEIPTS_WITH_BENIGN_CPU_NOT_MODEL_OR_FULL_COST',
        exit_code=rc, seconds=time.monotonic()-start, python=platform.python_version(),
        pytest=pytest.__version__, source_tree=build.BASE_TREE, upstream=build.UPSTREAM,
        source_cache_sha256=before, source_sha256={p: i['sha256'] for p,i in cache['sources'].items()},
        active_test_children=len(children), gpu_jobs=0, paid_api_calls=0, model_fits=0,
        production_programs_executed=0)
    Path('test_summary.json').write_text(json.dumps(receipt, sort_keys=True), encoding='utf-8')
    print(json.dumps(receipt, sort_keys=True))
    assert not children, 'test child cleanup incomplete'
    return rc


if __name__ == '__main__':
    sys.exit(main())
