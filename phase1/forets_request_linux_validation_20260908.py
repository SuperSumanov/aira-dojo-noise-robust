"""Bounded synthetic request-boundary tests; same source reader as prior validation."""
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path


def main():
    import pytest
    import jinja2
    from phase1 import forets_upstream_hotfix_20260908 as hotfix
    from phase1.forets_linux_validation_20260908 import cached_source
    cache_path = Path(os.environ['FORETS_SOURCE_CACHE'])
    before = hashlib.sha256(cache_path.read_bytes()).hexdigest()
    cache = json.loads(cache_path.read_bytes())
    for path in cache['sources']:
        cached_source(path)
    hotfix.source = cached_source
    from phase1 import forets_state_patch_20260908 as state_patch
    state_patch.source = cached_source
    from phase1 import forets_request_patch_20260908 as request_patch
    request_patch.upstream = cached_source
    from phase1.tests import test_forets_request_boundary_20260908 as request_tests
    request_tests.extra_source = cached_source
    start = time.monotonic()
    rc = pytest.main(['phase1/tests/test_forets_request_boundary_20260908.py',
                     'phase1/tests/test_forets_candidate_state_20260908.py',
                     'phase1/tests/test_forets_upstream_hotfix_20260908.py',
                     '-q', '-p', 'no:cacheprovider', '--junitxml=linux_tests.xml'])
    assert hashlib.sha256(cache_path.read_bytes()).hexdigest() == before
    print(json.dumps(dict(classification='REQUEST_BOUNDARY_SYNTHETIC_BACKEND_NOT_BILLING_OR_E2E',
        exit_code=rc, seconds=time.monotonic()-start, python=platform.python_version(),
        pytest=pytest.__version__, jinja2=jinja2.__version__, source_cache_sha256=before,
        upstream=hotfix.UPSTREAM, source_sha256={p: item['sha256'] for p,item in cache['sources'].items()},
        gpu_jobs=0, paid_api_calls=0, model_fits=0, real_programs_executed=0), sort_keys=True))
    return rc


if __name__ == '__main__':
    sys.exit(main())
