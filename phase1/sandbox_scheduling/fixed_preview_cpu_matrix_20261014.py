"""Run each native CPU input test in its own process; no outcome/body export."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def run(root, bundle, out):
    root, bundle, out=Path(root).resolve(),Path(bundle).resolve(),Path(out).resolve()
    plan=json.loads((root/'plan.json').read_text())
    rows=plan['schedule'];out.mkdir(mode=0o700)
    script=Path(__file__).with_name('fixed_preview_native_cpu_20261014.py')
    def one(row):
        index=row['index'];receipt=out/f'{index}.safe.json';log=out/f'{index}.private.log'
        with log.open('xb') as f:
            result=subprocess.run([sys.executable,'-B',str(script),str(root),str(bundle),str(index),str(receipt)],
                stdout=f,stderr=f,timeout=120)
        if result.returncode or not receipt.exists():
            return dict(index=index,passed=False,returncode=result.returncode)
        value=json.loads(receipt.read_text())
        assert all(value[k]==row[k] for k in ('index','arm','task','seed'))
        return dict(value,passed=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        result=list(pool.map(one,rows))
    groups=[]
    for task,seed in sorted({(r['task'],r['seed']) for r in rows}):
        expected=[r['index'] for r in rows if (r['task'],r['seed'])==(task,seed)]
        group=[r for r in result if r['index'] in expected]
        good=all(r['passed'] for r in group)
        groups.append(dict(task=task,seed=seed,indices=expected,
            identical=good and len({r['first_prompt_sha256'] for r in group})==1,
            same_preview=good and len({r['preview_sha256'] for r in group})==1,
            same_start=good and len({r['warm_sha256'] for r in group})==1))
    summary=dict(assigned=len(rows),passed=sum(r['passed'] for r in result),paired_groups=groups,
        exact_input_gate=all(g['identical'] and g['same_preview'] and g['same_start'] for g in groups),
        rows=result,donor_plan_sha256=hashlib.sha256((root/'plan.json').read_bytes()).hexdigest(),
        native_test_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
        old_batch_unchanged=True,no_gpu=True,no_model_calls=True,
        limitation='Real public input/native MCTS and transport serialization, but fake final response. Does not fix or reinterpret18253 and is not live performance evidence.')
    with (out/'summary.safe.json').open('x') as f:json.dump(summary,f,sort_keys=True,indent=2)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('rows','paired_groups')},sort_keys=True))
    if not summary['exact_input_gate']:raise SystemExit(1)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('bundle');ap.add_argument('out')
    a=ap.parse_args();run(a.root,a.bundle,a.out)
