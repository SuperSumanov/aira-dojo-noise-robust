"""Read original image package metadata/signatures; no task, fitting or GPU.

The returned facts may support a separately versioned generator context. They do
not repair previous runs, validate an entire generated program, or prove benefit.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

IMAGE = Path('/research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif')
EXPECTED = (19717783552, 1784638286000000000)
CODE = '''
import importlib.metadata as md, inspect, json
import lightgbm as lgb
from sklearn.preprocessing import OneHotEncoder
versions={}
for name in ('numpy','pandas','scikit-learn','lightgbm','catboost','xgboost','torch'):
    try: versions[name]=md.version(name)
    except md.PackageNotFoundError: versions[name]=None
functions={'lightgbm.train':lgb.train,'lightgbm.LGBMClassifier.fit':lgb.LGBMClassifier.fit,
    'lightgbm.early_stopping':lgb.early_stopping,'lightgbm.log_evaluation':lgb.log_evaluation,
    'sklearn.preprocessing.OneHotEncoder':OneHotEncoder}
signatures={name:str(inspect.signature(fn)) for name,fn in functions.items()}
cases=[]
for name,kw,fn,base in [
    ('train','verbose_eval',lgb.train,{'params':{},'train_set':object()}),
    ('train','early_stopping_rounds',lgb.train,{'params':{},'train_set':object()}),
    ('classifier.fit','verbose',lgb.LGBMClassifier.fit,{'self':object(),'X':object(),'y':object()}),
    ('classifier.fit','early_stopping_rounds',lgb.LGBMClassifier.fit,{'self':object(),'X':object(),'y':object()})]:
    try: inspect.signature(fn).bind(**base,**{kw:False}); accepted=True
    except TypeError: accepted=False
    cases.append({'function':name,'keyword':kw,'signature_accepts':accepted})
print(json.dumps({'versions':versions,'signatures':signatures,'binding_checks':cases,
    'model_fits':0,'task_executions':0,'gpu_computations':0}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    before = IMAGE.stat()
    if (before.st_size, before.st_mtime_ns) != EXPECTED:
        raise ValueError('original image metadata changed')
    env = {k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('KEY','TOKEN','SECRET','PASSWORD'))}
    env.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    command = [shutil.which('singularity') or 'singularity', 'exec', '--containall', '--cleanenv',
        '--no-home', str(IMAGE), 'python', '-c', CODE]
    proc = subprocess.run(command, capture_output=True, text=True, env=env, timeout=45)
    after = IMAGE.stat()
    if proc.returncode != 0 or (after.st_size, after.st_mtime_ns) != EXPECTED:
        raise RuntimeError('bounded image API metadata inspection failed')
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    result = dict(role='original_image_api_facts_not_runtime_repair',
        observed_utc=dt.datetime.now(dt.timezone.utc).isoformat(), image=str(IMAGE),
        image_size=after.st_size, image_mtime_ns=after.st_mtime_ns,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), facts=data)
    with args.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2); f.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
