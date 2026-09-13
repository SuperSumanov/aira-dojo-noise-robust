"""Recover old observed validity, not scores, from a narrow pre-August run list.

No prospective roots, no archive extraction, no newer fallback. Journals must
have an old filesystem close time AND an identity in the immutable public v9.
"""
from collections import Counter
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import tempfile

from inspect_v9_validity_schema_20260914 import SOURCE, EXPECTED, SECRET
from validity_cpu_transfer_20260914 import validity, ast_key

BASE = Path('/research/d7/spc/yzyang4')
RUNS = BASE / 'aira-dojo-runs/aira-dojo'
SUFFIXES = ('tpsdec','s3e18','nomad','tpsmay','gen2A','gen2B','gen2C','gen2D','gen3A',
    'suiteA','suiteB','suiteC','suiteV1','suiteD','suiteE','suiteLP1','suiteLP2','suiteLP3','suiteLP4',
    'suiteLP1_burn20260725','suiteLP2_burn20260725','suiteLP3_burn20260725','suiteLP4_burn20260725',
    'gen2VAL','gen2VALb')
CUTOFF = dt.datetime(2026,8,12,tzinfo=dt.timezone.utc).timestamp()

def sha(b): return hashlib.sha256(b).hexdigest()
def write(path, value):
    raw = (json.dumps(value, sort_keys=True, allow_nan=False)+'\n').encode()
    with path.open('xb') as f: f.write(raw)
    return sha(raw)

def main(group_names=None, output_prefix='forets-legacy-validity-20260914-', required_task=None):
    os.umask(0o077)
    digest = hashlib.sha256()
    with SOURCE.open('rb') as f:
        for b in f:
            if SECRET.search(b): raise ValueError('credential-shaped released source')
            digest.update(b)
    if digest.hexdigest() != EXPECTED: raise ValueError('fixed old release changed')
    public_ids = {}
    with SOURCE.open('rb') as f:
        for b in f:
            c = json.loads(b)
            if c['id'] in public_ids: raise ValueError('duplicate public identity')
            public_ids[c['id']] = c['task']['name']
    skipped = Counter(); records = []; proofs = []; counts = Counter(); task_counts = {}
    names = list(group_names) if group_names is not None else ['user_yzyang4_issue_mcts_data_' + suffix for suffix in SUFFIXES]
    for name in names:
        if not name.startswith('user_yzyang4_issue_') or '/' in name or '\\' in name: raise ValueError('fixed old group basename')
        group = RUNS / name
        if not group.is_dir(): skipped['missing_named_group'] += 1; continue
        for run in sorted(group.iterdir()):
            if not run.is_dir() or run.name == 'srun_pool': continue
            candidates = [run/'checkpoint/journal.jsonl', run/'json/JOURNAL.jsonl']
            available = [p for p in candidates if p.is_file()]
            if not available: skipped['journal_absent'] += 1; continue
            # Prefer complete checkpoint journal. Do not read config or env dumps.
            path = available[0]
            before = path.stat()
            if path.is_symlink() or not path.resolve().is_relative_to(RUNS): raise ValueError('source path')
            if before.st_mtime >= CUTOFF: skipped['not_closed_before_cutoff'] += 1; continue
            raw = path.read_bytes()
            if SECRET.search(raw): skipped['credential_shape_entire_journal_withheld'] += 1; continue
            nodes = [json.loads(line) for line in raw.splitlines() if line.strip()]
            matches = set()
            for n in nodes:
                mi = n.get('metric_info') or {}; task = mi.get('competition_id')
                identity = f"{task}__{n.get('id', n.get('step'))}"
                if identity in public_ids: matches.add(public_ids[identity])
            if len(matches) != 1: skipped['no_unique_public_v9_run_anchor'] += 1; continue
            task = matches.pop()
            if required_task is not None and task != required_task:
                skipped['outside_requested_task'] += 1; continue
            seen = set(); local = []
            for n in nodes:
                if n.get('step') in seen: raise ValueError('duplicate step in old journal')
                seen.add(n.get('step'))
                label = validity(n)
                if label is None: skipped['node_validity_unknown_or_virtual'] += 1; continue
                code = n.get('code')
                if not isinstance(code,str) or not code.strip(): skipped['node_no_code'] += 1; continue
                local.append(dict(run=str(run.relative_to(RUNS)), step=n['step'], task=task, label=label,
                    code=code, code_sha256=sha(code.encode()), ast_key=ast_key(code)))
            after = path.stat()
            if (before.st_mtime_ns,before.st_size) != (after.st_mtime_ns,after.st_size) or sha(path.read_bytes()) != sha(raw):
                raise ValueError('legacy source changed')
            proofs.append(dict(path=str(path),sha256=sha(raw),mtime_utc=dt.datetime.fromtimestamp(before.st_mtime,dt.timezone.utc).isoformat(),
                task=task,observed_nodes=len(local),positive=sum(r['label'] for r in local)))
            records.extend(local); counts[task] += len(local)
    root = Path(tempfile.mkdtemp(prefix=output_prefix,dir=BASE))
    with (root/'nodes.private.jsonl').open('xb') as f:
        for row in records: f.write((json.dumps(row,sort_keys=True)+'\n').encode())
    for task in sorted(counts):
        rr = [r for r in records if r['task']==task]
        task_counts[task] = dict(nodes=len(rr),positive=sum(r['label'] for r in rr),runs=len({r['run'] for r in rr}))
    report = dict(role='legacy_development_validity_not_scores',public_anchor_sha256=EXPECTED,cutoff_utc='2026-08-12T00:00:00Z',
        allowlisted_groups=names,required_task=required_task,source_proofs=proofs,skipped=dict(skipped),nodes=len(records),
        runs=len({r['run'] for r in records}),task_counts=task_counts,script_sha256=sha(Path(__file__).read_bytes()),
        private_nodes_sha256=sha((root/'nodes.private.jsonl').read_bytes()),
        caveat='Requires a public graded-node anchor: all-failed runs without such an anchor are absent. Old heterogeneous environments; not a representative population or frozen confirmation cohort.')
    digest = write(root/'inventory.json',report)
    print(json.dumps(dict(root=str(root),inventory_sha256=digest,**{k:report[k] for k in ('nodes','runs','task_counts','skipped')})),flush=True)

if __name__ == '__main__': main()
