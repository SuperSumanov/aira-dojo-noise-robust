"""Read-only scoped metadata and credential-first source check, no model calls."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

B = Path('/research/d7/spc/yzyang4')
D = B/'policy9b-paired-20261005-gpu27-v1'
SECRET = re.compile(rb'(?i)(?<![a-z0-9_-])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def safe(path):
    raw = path.read_bytes()
    if SECRET.search(raw):
        raise ValueError('credential shape: refused')
    return raw

def main():
    p = json.loads(safe(D/'plan.json'))
    closed = json.loads(safe(D/'closed.json'))
    files = {}
    for rel in ('source/src/dojo/core/interpreters/jupyter/jupyter_client.py',
                'source/src/dojo/tasks/mlebench/task.py',
                'source/src/dojo/utils/experiment_deadline.py',
                'policy9b_paired_20261005.py','service_entry.py',
                'root_trial_step_supervisor_20260927.py'):
        raw = safe(D/rel)
        digest = hashlib.sha256(raw).hexdigest()
        if p['files'][rel] != digest:
            raise ValueError('donor drift')
        files[rel] = digest
    configs = []
    for i in (0,1):
        c = json.loads(safe(D/f'configs/{i}.json'))
        t = c['task']
        scorer = Path(t['search_only_dev_scorer_path'])
        configs.append(dict(task=t['name'], public_dir_exists=Path(t['public_dir']).is_dir(),
            private_dir_exists=Path(t['private_dir']).exists(), data_dir=t['data_dir'],
            scorer_sha_match=hashlib.sha256(safe(scorer)).hexdigest()==t['search_only_dev_scorer_sha256'],
            interpreter_name=c['interpreter'].get('name'),solver_name=c['solver'].get('name'),
            use_test_score=c['solver']['use_test_score']))
    paths = ('models/Qwen3.5-9B-c202236',
             'policy9b-adapter-20261005-b6jjvjwh/accepted_adapter',
             'local-qwen27b-20260914-zcx1k1dy/vllm.sif',
             'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif')
    result = dict(donor_plan_sha256=hashlib.sha256(safe(D/'plan.json')).hexdigest(),
        source_commit=p['source_commit'],files=files,configs=configs,
        paths_exist={v:(B/v).exists() for v in paths},service_closed=closed.get('service_closed'),
        available_bytes=shutil.disk_usage(B).free,no_model_calls=True,no_scoring=True)
    print(json.dumps(result,sort_keys=True))

if __name__ == '__main__':
    main()
