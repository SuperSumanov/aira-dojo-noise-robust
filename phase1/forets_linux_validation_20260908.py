"""Offline directed tests using hash-pinned source blobs, not a producer checkout.

No Git repository is fabricated. The cache replaces only read-only Git source
retrieval. Model/operator/HTTP/task I/O remain synthetic as stated by the tests.
"""
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

from phase1 import forets_upstream_hotfix_20260908 as hotfix


def cached_source(path):
    cache = json.loads(Path(os.environ['FORETS_SOURCE_CACHE']).read_bytes())
    if cache['upstream'] != hotfix.UPSTREAM or path not in cache['sources']:
        raise ValueError('source cache binding')
    item = cache['sources'][path]
    raw = item['text'].encode()
    if len(raw) > 1024 * 1024 or hotfix.SECRET.search(raw):
        raise ValueError('source cache credential or size gate')
    if hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise ValueError('source cache content drift')
    return item['text']


def main():
    import pytest
    # Exact payload hashes must be verified externally before invoking this runner.
    cache_path = Path(os.environ['FORETS_SOURCE_CACHE'])
    before = hashlib.sha256(cache_path.read_bytes()).hexdigest()
    cache = json.loads(cache_path.read_bytes())
    for path in cache['sources']:
        cached_source(path)
    hotfix.source = cached_source
    # Import after patching only the source reader; all method bodies are unchanged.
    from phase1 import forets_state_patch_20260908 as state_patch
    state_patch.source = cached_source
    start = time.monotonic()
    rc = pytest.main(['phase1/tests/test_forets_candidate_state_20260908.py',
                      'phase1/tests/test_forets_upstream_hotfix_20260908.py',
                      '-q', '-p', 'no:cacheprovider', '--junitxml=linux_tests.xml'])
    after = hashlib.sha256(cache_path.read_bytes()).hexdigest()
    if before != after:
        raise RuntimeError('source cache changed during tests')
    print(json.dumps(dict(classification='LINUX_DIRECTED_SYNTHETIC_IO_NOT_E2E',
          exit_code=rc, seconds=time.monotonic()-start, python=platform.python_version(),
          platform=platform.system(), source_cache_sha256=after, upstream=hotfix.UPSTREAM,
          source_sha256={k: v['sha256'] for k,v in cache['sources'].items()},
          real_programs_executed=0, gpu_jobs=0, paid_api_calls=0, model_fits=0), sort_keys=True))
    return rc


if __name__ == '__main__':
    sys.exit(main())
