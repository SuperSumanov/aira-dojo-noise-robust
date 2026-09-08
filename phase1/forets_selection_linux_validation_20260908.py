"""Run only the NEW selection contract matrix, with no model or program execution."""
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path


def main():
    import pytest
    from phase1 import forets_selection_patch_20260908 as build
    cache_path = Path(os.environ['FORETS_SELECTION_CACHE'])
    before = hashlib.sha256(cache_path.read_bytes()).hexdigest()
    cache = json.loads(cache_path.read_bytes())
    for path in cache['sources']:
        build.source(path)
    start = time.monotonic()
    rc = pytest.main(['phase1/tests/test_forets_selection_20260908.py',
                     '-q', '-p', 'no:cacheprovider', '--basetemp=pytest-temp', '--junitxml=linux_tests.xml'])
    assert hashlib.sha256(cache_path.read_bytes()).hexdigest() == before
    receipt = dict(classification='FROZEN_SYNTHETIC_POOL_SELECTION_CONTRACT_NOT_MODEL_GAIN',
        exit_code=rc, seconds=time.monotonic()-start, python=platform.python_version(),
        pytest=pytest.__version__, source_tree=build.BASE_TREE, upstream=build.UPSTREAM,
        source_cache_sha256=before, source_sha256={p: i['sha256'] for p,i in cache['sources'].items()},
        gpu_jobs=0, paid_api_calls=0, model_fits=0, production_programs_executed=0)
    Path('test_summary.json').write_text(json.dumps(receipt, sort_keys=True), encoding='utf-8')
    print(json.dumps(receipt, sort_keys=True))
    return rc


if __name__ == '__main__':
    sys.exit(main())
