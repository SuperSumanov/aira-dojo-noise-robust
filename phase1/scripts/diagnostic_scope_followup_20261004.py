"""Post-outcome fixed-blend sensitivity and safe export; no fits or generator.

The original source already checked all weights .5/.6/.7 with text-LGB.
Recompute all of them, not a newly tuned or selected winning blend. Never change
the primary gate. Original arrays, labels, code and replies stay remote.
"""
import argparse
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess

import numpy as np
from sklearn.metrics import roc_auc_score

R = Path('/research/d7/spc/yzyang4/diagnostic-scope-20261004-v1')
D = Path('/research/d7/spc/yzyang4/executable-evidence-20261004-v1')
PLAN = 'eb42a6df8f8358dc611ba2c1d31c653c92dffe51ec87c0b33b2bfe6d643f65a0'
SOURCE = '3cc81fc7232144bdd910920f26ff0de1f346c95c021de9792d260f50e4c65a58'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{10,}|hf_[a-z0-9]{15,}|gh[pousr]_[a-z0-9]{15,}|Bearer\s+\S{12,})')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    raw = path.read_bytes()
    assert not SECRET.search(raw), 'credential shape: output withheld'
    return json.loads(raw)


def encode(x):
    raw = (json.dumps(x, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()
    assert not SECRET.search(raw)
    return raw


def write(path, obj):
    with path.open('xb') as f:
        f.write(encode(obj))


def auc_literal(y, p):
    positives, negatives = p[y == 1], p[y == 0]
    # An actual pair-comparison implementation, independent of the rank formula.
    return float(np.mean((positives[:, None] > negatives[None, :]) +
                         .5*(positives[:, None] == negatives[None, :])))


def checked():
    assert sha(R/'plan.json') == PLAN
    assert (R/'closed.json').exists()
    primary = read(R/'readout-v1/summary.json')
    assert primary['plan_sha256'] == PLAN and primary['status'] == 'COMPLETE'
    assert primary['assigned'] == primary['complete'] == 10
    plan = read(R/'plan.json')
    for rel, expected in plan['files'].items():
        assert sha(R/rel) == expected
    return plan, primary


def posthoc():
    plan, primary = checked()
    source = D/'episode-0/action-1/node.private.json'
    assert sha(source) == SOURCE
    obj = read(source)
    tree = ast.parse(obj['code'])
    loops = [x for x in tree.body if isinstance(x, ast.For) and
             'oof_lgb_txt' in ast.unparse(x) and 'blend' in ast.unparse(x)]
    assert len(loops) == 1
    loop = loops[0]
    assert ast.literal_eval(loop.iter) == [.5, .6, .7]
    assert ast.unparse(loop.body[0]) == 'b = w * oof_lgb + (1 - w) * oof_lgb_txt'
    # Supplementary analysis selected after primary results: no confirmatory p.
    out = R/'posthoc-blend-direction.json'
    assert not out.exists()
    rows, controls, errors = [], [], []
    for slot in plan['schedule']:
        if slot['case'] != 'component_check':
            continue
        ep = R/f'episode-{slot["index"]}/action-0'
        receipt = read(ep/'result.json')
        assert receipt['complete']
        for filename, expected in receipt['artifacts'].items():
            assert sha(ep/filename) == expected
        with np.load(ep/'diagnostic_oof.npz', allow_pickle=False) as saved:
            y, num, txt = saved['y'], saved['numeric'], saved['text_lgb']
        for w in [.5, .6, .7]:
            blend = w*num+(1-w)*txt
            value = float(roc_auc_score(y, blend))
            independent = auc_literal(y, blend)
            assert abs(value-independent) < 1e-12
            errors.append(abs(value-independent))
            row = dict(seed=slot['seed'], arm=slot['arm'], numeric_weight=w,
                       blend_auc=value, numeric_auc=float(roc_auc_score(y,num)),
                       blend_minus_numeric=value-float(roc_auc_score(y,num)))
            rows.append(row)
            if slot['seed'] == 42 and slot['arm'] == 'all_numeric':
                matches = [line for line in obj['terminal'].splitlines()
                           if line.startswith(f'blend num{w}/txt')]
                assert len(matches) == 1
                prior = float(matches[0].split('AUC:')[1])
                assert abs(value-prior) <= .0000005
                controls.append(dict(numeric_weight=w, original_rounded_auc=prior,
                                     new_auc=value, rounded_reproduction=True))
    contrasts = []
    for seed in (42,173):
        for w in (.5,.6,.7):
            a = next(x for x in rows if x['seed']==seed and x['numeric_weight']==w and x['arm']=='all_numeric')
            b = next(x for x in rows if x['seed']==seed and x['numeric_weight']==w and x['arm']=='deployment_scope')
            contrasts.append(dict(seed=seed,numeric_weight=w,
                all_blend_minus_numeric=a['blend_minus_numeric'],
                deployment_blend_minus_numeric=b['blend_minus_numeric'],
                sign_reversal=a['blend_minus_numeric']*b['blend_minus_numeric'] < 0))
    result = dict(status='POSTHOC_COMPLETE', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        plan_sha256=PLAN, primary_summary_sha256=sha(R/'readout-v1/summary.json'),
        source_node_sha256=SOURCE, script_sha256=sha(Path(__file__)),
        scope='Zero-fit post-outcome sensitivity. All3 actual pre-existing blend weights, both seeds/scopes. No new weights selected; not six independent experiments. Does not alter the frozen primary gate.',
        source_reproduction=controls, comparisons=contrasts, scores=rows,
        numeric_checks=len(errors), numeric_max_abs_error=max(errors),
        interpretation='Changes to this measured blend choice do not establish subsequent LLM behavior, D_search benefit, or automatic method gain.')
    write(out, result)
    print(json.dumps(result))


def export():
    plan, primary = checked()
    supplement = read(R/'posthoc-blend-direction.json')
    assert supplement['primary_summary_sha256'] == sha(R/'readout-v1/summary.json')
    job = read(R/'launch.json')['job']
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    lines = subprocess.check_output(['sacct','-j',job,'-n','-P',
        '--format=JobIDRaw,State,ElapsedRaw,AllocTRES,NodeList,ExitCode'],env=env,text=True,timeout=25).splitlines()
    line = next(x for x in lines if x.split('|')[0] == job)
    jobid, state, elapsed, resources, node, rc = line.split('|')[:6]
    assert state == 'COMPLETED' and rc == '0:0' and 'gres/gpu=1' in resources
    seconds = int(elapsed)
    assert seconds <= plan['allocation_seconds'] and node == 'gpu3'
    costs = dict(job=job, state=state, elapsed_seconds=seconds,gpus=1,
        allocated_gpu_hours=seconds/3600,gpu_hours_cap=plan['gpu_hours_cap'],node=node,
        generator_calls=0, paid_api=0, protected_opened=False,
        scope='Allocation includes task startup/idling/failures; preparatory login-node image hashing and analysis not included in GPU hours.')
    payload = {
        'plan.aggregate.json':encode({k:v for k,v in plan.items() if k!='files'}),
        'summary.aggregate.json':encode({k:v for k,v in primary.items() if k!='input_sources'}),
        'resources.json':encode(costs),
        'posthoc-blend-direction.json':encode(supplement),
    }
    for name in ('runs.csv','pairs.csv'):
        payload[name] = (R/'readout-v1'/name).read_bytes()
    for name in ('cpu.json','analysis-freeze.json','launch.json'):
        payload[name] = (R/name).read_bytes()
    assert all(not SECRET.search(raw) for raw in payload.values())
    receipt = dict(plan_sha256=PLAN,full_summary_sha256=sha(R/'readout-v1/summary.json'),
        exporter_sha256=sha(Path(__file__)),files={n:hashlib.sha256(v).hexdigest() for n,v in payload.items()},
        excluded=['raw programs','model replies','training labels','OOF arrays','credentials'],
        scope='Only the closed10-execution public-training diagnostic replay and explicitly posthoc fixed-blend sensitivity.')
    payload['export-receipt.json'] = encode(receipt)
    target = R/'safe-export-v1'
    target.mkdir(mode=0o700)
    for name, raw in payload.items():
        with (target/name).open('xb') as f:
            f.write(raw)
    print(json.dumps(dict(status='EXPORTED',files=len(payload),receipt_sha256=sha(target/'export-receipt.json'),resources=costs)))


if __name__ == '__main__':
    os.umask(0o077)
    p = argparse.ArgumentParser()
    p.add_argument('mode',choices=['posthoc','export'])
    globals()[p.parse_args().mode]()
