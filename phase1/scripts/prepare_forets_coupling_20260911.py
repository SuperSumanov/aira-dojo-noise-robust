"""Apply the optional coupling patch to a temporary Git index, not the checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASE = 'bbd22e323d6321925a145c12bdc02445c1ad80f4'
PATCH = ROOT/'phase1/upstream_patches/0018-ForeTS-explicit-common-priority-20260911.patch'
ALLOWED = {'src/dojo/config_dataclasses/solver/fore_ts.py',
           'src/dojo/solvers/fore_ts/selection.py', 'src/dojo/solvers/fore_ts/batch_runtime.py'}


def prepare():
    with tempfile.TemporaryDirectory(prefix='forets-coupling-index-') as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp)/'index'))
        def git(*args):
            return subprocess.check_output(['git', '-c', 'core.autocrlf=false', *args],
                                           cwd=ROOT, env=env, timeout=30).decode().strip()
        git('read-tree', BASE)
        # Recount hunk lengths in this hand-maintained patch; context must still match.
        git('apply', '--recount', '--cached', '--check', '--whitespace=error', str(PATCH))
        git('apply', '--recount', '--cached', '--whitespace=error', str(PATCH))
        tree = git('write-tree')
        changed = git('diff', '--name-only', BASE, tree).splitlines()
        if set(changed) != ALLOWED: raise ValueError('unexpected_changed_paths')
        git('diff', '--check', BASE, tree)
    return {'status': 'ISOLATED_SOURCE_ONLY_NOT_DEPLOYED', 'base_tree': BASE, 'source_tree': tree,
            'patch_sha256': hashlib.sha256(PATCH.read_bytes()).hexdigest(), 'changed_paths': sorted(changed),
            'default_coupling': 'independent_subset_v2', 'optional_coupling': 'common_priority_v1',
            'production_files_changed': False, 'gpu_submissions': 0, 'api_requests': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    raw = json.dumps(prepare(), sort_keys=True, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8', newline='\n') as f: f.write(raw)
    print(raw)
