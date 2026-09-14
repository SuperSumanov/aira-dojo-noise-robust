"""Export only completed derived followups; never modify readers or run outcomes."""
import hashlib, io, json, re, tarfile
from pathlib import Path

BASE = Path('/research/d7/spc/yzyang4')
CASES = {
    'class-gate-s48': ('forets-wallclock-20260912-9uosb6me', {
        'cheap-selector-summary.json': 'aa9c4610c0c6bc91011fca4e0edc8a6f6a8f7459351978bc73298d1a70258609',
        'cheap-selector-independent.json': '84e607b0199823f46debfbf8a0e1cbdb4e20b172556da7410fcb47949ed2eb47'}),
    'first-pool-replay': ('forets-first-pool-replay-20260914-12xoscfq', {
        'summary.json': 'e1a07d80bf396d2f02c81f22f4dbd4e8b534a02f79ae2870fc29e0fa380aef28',
        'independent.json': '4ff04b12c4f1622646b72728436600ab0fa67c6f89868e21530ecbf7a0b2db51'})}
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def sha(raw): return hashlib.sha256(raw).hexdigest()
def checked(path, expected=None):
    if path.is_symlink(): raise ValueError('symlink')
    raw = path.read_bytes()
    if SECRET.search(raw) or (expected and sha(raw) != expected): raise ValueError('security/hash gate')
    return raw

def main():
    for label, (suffix, fixed) in CASES.items():
        root = BASE / suffix
        finish_raw = checked(root / 'readout-finished.json')
        finish = json.loads(finish_raw)
        if label == 'class-gate-s48':
            if finish['status'] != 'verified': raise ValueError('readout first')
            names = {**finish['files'], **fixed}
        else:
            names = {'runs.csv': finish['csv_sha256'], **fixed}
        data = {n: checked(root / n, h) for n, h in names.items()}
        data['readout-finished.json'] = finish_raw
        data['manifest.json'] = (json.dumps({n: {'sha256': sha(v), 'bytes': len(v)} for n, v in data.items()}, sort_keys=True) + '\n').encode()
        target = root / (label + '-public.tar')
        with target.open('xb') as f, tarfile.open(fileobj=f, mode='w') as archive:
            for n, raw in sorted(data.items()):
                info = tarfile.TarInfo(n); info.size = len(raw); info.mode = 0o600; info.mtime = 0
                archive.addfile(info, io.BytesIO(raw))
        print(json.dumps({'label': label, 'path': str(target), 'sha256': sha(target.read_bytes()), 'members': len(data)-1}))
        if label == 'class-gate-s48':
            s = json.loads(data['cheap-selector-summary.json'])
            print(json.dumps({'rows': [{k: r[k] for k in ('task', 'seed', 'arm', 'technical_eligible', 'termination_reason', 'action_score', 'iteration_score', 'pools', 'candidate_executions')} for r in s['rows']], 'secondary': s['secondary_short_code']}))
        else:
            s = json.loads(data['summary.json'])
            print(json.dumps({'pools': [{k: r[k] for k in ('source_run_id', 'task', 'choices', 'labels', 'grades', 'original_initial_labels', 'original_known_retest', 'original_validity_disagreements')} for r in s['pairs']], 'gpu_hours': s['allocation_gpu_hours']}))

if __name__ == '__main__': main()
