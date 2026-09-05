"""Observed open/openat trace audit; not a sandbox or tar-member read proof."""
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path('/research/d7/spc/yzyang4')
CONTROL = Path('/tmp/historical-runtime-prefix-control-79164e0-yA8VCZ')
CODE_SHA = '8cb3ae6db049bfdd550ebfeb087934c3b2ad373efff61f20236c1726be266624'
BLOCK = re.compile(r'(?i)first[-_]?960|target[-_]?(?:300|522)|prospective_decision|label[_-]?vault|prediction[_-]?escrow|(?:^|/)\.env(?:$|/)|/\.ssh/')
SECRET = re.compile(rb'(?i)sk-[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9_.-]{20,}')
QUOTED = re.compile(r'"(?:[^"\\]|\\.)*"')


def h(raw):
    return hashlib.sha256(raw).hexdigest()


def run():
    os.umask(0o077)
    raw = (ROOT/'historical-pool-lineage-e7244fb-20260906-A/pool_lineage.private.json').read_bytes()
    assert h(raw) == 'fe05dddcd4fe8a3f2208652ce51c9b06df9b9b8f57a5fa655d2029caddcf9981'
    # Actual fixed input inventory, not an arbitrary allow-list of data paths.
    inventory = ROOT/'senior-true-batch-identity-support/a466888-v3/producer_1/archive_manifest.jsonl'
    payload = inventory.read_bytes()
    assert h(payload) == '72b74df7387254afc5ca3ec5d79029e74ae8371faa6216742e63be899419e8fd'
    prefix_raw = (ROOT/'historical-runtime-prefix-79164e0-20260906-A/runtime_prefix.private.json').read_bytes()
    assert h(prefix_raw) == 'fc13d25745c1c8ea408374741358137e9eb374b3b214e0c9f6d4b856b071464b'
    prefix = json.loads(prefix_raw)
    wanted = {a['archive_sha256'] for a in prefix['archives']}
    paths = {str(ROOT/'external/senior_data/mle'/r['relative_path']) for line in payload.splitlines()
             if (r := json.loads(line))['status'] == 'ok' and r['sha256'] in wanted}
    if '8ade376fb045aa47bffa63b493fa5e4b02d376815d7700c9c9f441c1848edfa4' in wanted:
        paths.add(str(ROOT/'historical-repair-candidate-0811-20260905/leaf-repair-8ade376f.tar.gz'))
    inputs = {str(inventory), str(ROOT/'historical-source-ledger-faf04cc-20260905/source_ledger.private.json'),
              str(ROOT/'historical-pool-lineage-e7244fb-20260906-A/pool_lineage.private.json')}
    assert h((CONTROL/'phase1/audit_historical_runtime_prefix.py').read_bytes()) == CODE_SHA
    outputs = [str(ROOT/('historical-runtime-prefix-79164e0-20260906-'+leg)) for leg in ('A','B')]
    records = []
    for leg in ('A','B'):
        trace = (CONTROL/('opens_'+leg+'.private.log')).read_bytes()
        assert not SECRET.search(trace)
        pending = {}; counts = Counter(); issues = Counter(); archives_seen = set()
        for line in trace.decode().splitlines():
            if '<unfinished ...>' in line:
                m = re.match(r'^(\d+)\s+(.*)<unfinished \.\.\.>$',line)
                assert m and m[1] not in pending
                pending[m[1]] = m[2]; continue
            if 'resumed>' in line:
                m = re.match(r'^(\d+)\s+<\.\.\. \w+ resumed>(.*)$',line)
                assert m and m[1] in pending
                line = m[1]+' '+pending.pop(m[1])+m[2]
            m = re.match(r'^\d+\s+(open|openat)\((.*)\)\s+=\s+(.+)$',line)
            if not m:
                if '--- ' in line or '+++ ' in line: continue
                issues['unparsed_line'] += 1; continue
            quoted = QUOTED.findall(m[2]); assert quoted
            path = ast.literal_eval(quoted[0])
            assert not BLOCK.search(path), 'protected_path_observed'
            if m[3].startswith('-1 '): counts['failed_open'] += 1; continue
            if not path.startswith('/'):
                assert m[1]=='open' or m[2].startswith('AT_FDCWD,'), 'unresolved_dirfd'
                path = os.path.normpath(str(CONTROL/'phase1')+'/'+path)
            if path in paths: category='fixed_archive'; archives_seen.add(path)
            elif path in inputs: category='fixed_structural_input'
            elif any(path == p or path.startswith(p+'/') for p in outputs): category='this_audit_output'
            elif path.startswith(str(CONTROL)+'/'): category='fixed_code_bundle'
            elif path.startswith(str(ROOT/'venvs/exp')+'/'): category='python_runtime'
            elif any(path == p or path.startswith(p+'/') for p in ('/usr','/lib','/lib64','/etc','/proc','/dev','/sys','/bin')): category='system_runtime'
            elif any(path.startswith(p) for p in ('/uac/y24/yzyang4/.local/share/uv/python/', '/data/d0/y24/yzyang4/.local/share/uv/python/')): category='python_backing'
            else: category='unknown_successful_open'; issues[category] += 1
            counts[category] += 1
            if any(flag in m[2] for flag in ('O_WRONLY','O_RDWR','O_CREAT')) and category not in ('this_audit_output','system_runtime'):
                issues['unexpected_write_open'] += 1
        assert not pending
        records.append({'leg':leg,'trace_sha256':h(trace),'successful_fixed_archive_paths':len(archives_seen),
                        'categories':dict(counts),'issues':dict(issues)})
    result = {'status':'OBSERVED_OPEN_TRACE_CHECK' if not any(r['issues'] for r in records) else 'FAIL_CLOSED_OPEN_TRACE_REVIEW_REQUIRED',
              'records':records,'source_sha256':h(Path(__file__).read_bytes()),
              'scope':'observed open/openat only; not OS isolation, tar-member byte tracing, or a proof of zero task-phase bytes',
              'producer_commit':'79164e047b46f7d76db38a89407d1b008c19221a'}
    out = ROOT/'historical-runtime-prefix-trace-20260906.json'
    with out.open('x') as f: json.dump(result,f,sort_keys=True); f.write('\n')
    out.chmod(0o400)
    print(json.dumps(result,sort_keys=True))
    assert not any(r['issues'] for r in records), 'trace_review_required'


if __name__=='__main__':
    run()
