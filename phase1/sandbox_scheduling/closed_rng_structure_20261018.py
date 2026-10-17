"""Read only three closed owned DEV batches; output AST structure, never source.

This is hypothesis qualification, not a scheduler retry or a quality readout.
No code is executed, no new labels or protected files are opened.
"""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import time

BASE = Path('/research/d7/spc/yzyang4')
NAMES = ('scheduling-pooling-20261016-v3', 'scheduling-colocation-20261016-v1',
         'scheduling-selective-20261017-v1')
SECRET = re.compile(r'(?i)(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def name(n):
    if isinstance(n, ast.Name): return n.id
    if isinstance(n, ast.Attribute):
        prefix = name(n.value)
        return prefix + '.' + n.attr if prefix else n.attr
    return ''

def shape(code):
    if SECRET.search(code): raise ValueError('credential shape: no source exported')
    tree = ast.parse(code)
    calls = Counter(name(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call))
    # Only a fixed allowlist of structural API categories leaves the machine.
    pats = {
        'dataloader': r'(?:^|\.)DataLoader$',
        'random_sampler': r'(?:^|\.)(?:RandomSampler|WeightedRandomSampler)$',
        'generator': r'(?:^|\.)Generator$',
        'seed': r'(?:^|\.)(?:seed|manual_seed|manual_seed_all|seed_everything)$',
        'torch_random': r'^(?:torch|th)\.(?:rand|randn|randint|randperm|multinomial|bernoulli)$',
        'numpy_random': r'^(?:np|numpy)\.random\.',
        'python_random': r'^random\.',
        'random_augmentation': r'(?:RandomCrop|RandomResizedCrop|RandomHorizontalFlip|RandomVerticalFlip|ColorJitter|RandomRotation)$',
        'optimizer': r'(?:^|\.)(?:Adam|AdamW|SGD|RMSprop)$',
        'checkpoint_save': r'^(?:torch\.save|joblib\.dump)$',
        'checkpoint_load': r'^(?:torch\.load|joblib\.load)$|(?:^|\.)load_state_dict$',
        'dropout': r'(?:^|\.)(?:Dropout|Dropout2d|dropout)$',
    }
    result = {k: sum(v for f,v in calls.items() if re.search(p,f)) for k,p in pats.items()}
    result['dataloader_explicit_generator'] = sum(
        name(n.func).endswith('DataLoader') and any(k.arg == 'generator' for k in n.keywords)
        for n in ast.walk(tree) if isinstance(n, ast.Call))
    result['dataloader_worker_init'] = sum(
        name(n.func).endswith('DataLoader') and any(k.arg == 'worker_init_fn' for k in n.keywords)
        for n in ast.walk(tree) if isinstance(n, ast.Call))
    result['module_classes'] = sum(any(name(b).endswith('Module') for b in n.bases)
                                   for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
    return result

def main():
    start = time.monotonic(); rows = []; inputs = {}
    for batch in NAMES:
        root = BASE/batch
        planpath = root/'plan.json'; inputs[str(planpath)] = sha(planpath)
        plan = json.loads(planpath.read_text())
        assert len(plan['schedule']) == 32
        for r in plan['schedule']:
            ep = root/f"episode-{r['index']}"
            for p in sorted(ep.glob('candidate-*.json')):
                if '.private.' in p.name: continue
                c = json.loads(p.read_text())
                if not(c['elapsed_seconds'] <= 1020 and c.get('valid') is True
                       and c.get('exit_code') == 0 and not c.get('timed_out')): continue
                raw = p.with_name(p.stem+'.private.json')
                code = json.loads(raw.read_text())['code']
                assert hashlib.sha256(code.encode()).hexdigest() == c['code_sha256']
                inputs[str(p)] = sha(p); inputs[str(raw)] = sha(raw)
                rows.append(dict(batch=batch, index=r['index'], task=r['task'],
                                 candidate=int(p.stem.split('-')[1]), code_sha256=c['code_sha256'],
                                 structure=shape(code)))
    grouped = []
    for task in sorted({r['task'] for r in rows}):
        rr = [r for r in rows if r['task']==task]
        keys = sorted(rr[0]['structure'])
        grouped.append(dict(task=task,valid_returns=len(rr),
                            programs_with={k:sum(r['structure'][k]>0 for r in rr) for k in keys}))
    out = dict(source_sha256=sha(Path(__file__)), rows=rows, grouped=grouped,
               inputs=inputs, elapsed_seconds=time.monotonic()-start,
               scope='Three already-closed owned DEV batches, timely valid return census.',
               limits=['AST API spelling only, may miss aliases/dynamic/library internals.',
                       'No measured randomness drift, covariance reduction, quality benefit, or novelty.'])
    dest = BASE/'quota-queue-source-20261017-ymOz45'/'rng-structure-20261018.safe.json'
    with dest.open('x') as f: json.dump(out,f,indent=2,sort_keys=True,allow_nan=False)
    print(json.dumps(dict(path=str(dest),sha256=sha(dest),groups=grouped)))

if __name__ == '__main__': main()
