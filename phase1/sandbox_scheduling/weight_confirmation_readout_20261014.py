"""Frozen full-denominator AB/BA medium-weight readout; no pooled rescue.

Reuse exact-count external-score/physical-identity checks from the independently
verified reader. Every transformation is asserted; donor is never rewritten.
"""
import argparse
import inspect
from pathlib import Path
import statistics
import long_effort_readout_20261013 as prior
from weight_effort_policy_20261014 import effort,model

ARMS=('old_medium','new_medium')
ORDER=('old_medium','new_medium','new_medium','old_medium')
RUN,SLOT,CAP=1800,1960,9000
TASKS,SIGN=prior.TASKS,prior.SIGN


def quality(scores):
    contrasts=[dict(repeat=rep,task=t,method='new_medium',reference='old_medium',
        method_best=scores[rep,'new_medium',t],reference_best=scores[rep,'old_medium',t],
        oriented_delta=SIGN[t]*(scores[rep,'new_medium',t]-scores[rep,'old_medium',t]))
        for rep in (0,1) for t in TASKS]
    return contrasts,all(r['oriented_delta']>=(.001 if r['task']==TASKS[1] else -1e-12) for r in contrasts)


def summarize(rows):
    out=[]
    for block,arm in enumerate(ORDER):
        for task in TASKS:
            values=[r['score'] for r in rows if r['block']==block and r['task']==task]
            assert len(values)==4 and all(v is not None for v in values)
            out.append(dict(block=block,repeat=block//2,arm=arm,task=task,
                best=max(values,key=lambda x:SIGN[task]*x),median=statistics.median(values),
                sample_sd=statistics.stdev(values),n=4))
    return out


def runtime_inputs(root,p,rows):
    expected=prior.read(root/'input-matrix/summary.safe.json')
    assert expected['assigned']==expected['passed']==32 and expected['exact_input_gate']
    assert prior.sha(root/'public-preview.private.json')==p['public_preview_sha256']
    checks=[]
    for row in rows:
        ref=expected['rows'][row['index']]
        assert all(row[k]==ref[k] for k in ('index','arm','task','seed'))
        path=root/f"episode-{row['index']}/input-gate.jsonl"
        events=prior.lines(path) if path.exists() else []
        gates=[x for x in events if x['event']=='first_request_input_gate']
        previews=[x for x in events if x['event']=='fixed_public_preview_loaded']
        ok=(len(gates)==1 and gates[0].get('passed') is True
            and gates[0]['sha256']==gates[0]['expected_sha256']==ref['first_prompt_sha256']
            and bool(previews) and all(x['sha256']==ref['preview_sha256'] for x in previews))
        checks.append(dict(index=row['index'],passed=ok,expected_sha256=ref['first_prompt_sha256'],
            observed_sha256=gates[0]['sha256'] if len(gates)==1 else None))
    return checks


source=inspect.getsource(prior.analyze)
def replace(a,b):
    global source
    assert source.count(a)==1,a[:90]
    source=source.replace(a,b)
replace("p['planned'] == 24","p['planned'] == 32")
replace('dict(assigned=24,','dict(assigned=32,')
replace('for b in range(3):','for b in range(4):')
replace('independent_pools_per_arm=1','independent_pools_per_arm=2')
replace("expected = effort(s['arm'], e['role'])","expected = effort(s['arm'], e['role'])\n                assert e['model_id'] == model(s['arm'])")
replace("spec, warm = read(root/'dev-views/spec.json'), read(root/'warm-receipt.json')", """spec, warm = read(root/'dev-views/spec.json'), read(root/'warm-receipt.json')
    assert sha(root/'warm.private.json')==p['common_start_sha256']
    assert sha(root/'warm-receipt.json')==p['common_start_receipt_sha256']
    if closed['complete']:
        qualification=read(root/'adapter-service-qualification.json')
        assert {x['model_id'] for x in qualification['rows']}=={model(a) for a in ARMS}
        assert all(x['response_received'] for x in qualification['rows'])""")
replace("    if not all(r['complete'] for r in rows):", """    inputs=runtime_inputs(root,p,rows)
    input_gate=all(x['passed'] for x in inputs)
    result.update(runtime_input_gate=input_gate,common_preview_preparation_wall_seconds=p['common_preview_preparation_wall_seconds'])
    write(out/'input-checks.json',inputs)
    if not all(r['complete'] for r in rows):""")
replace("scores = {(a, t): max([r['score'] for r in rows if (r['arm'], r['task']) == (a, t)], key=lambda x: SIGN[t]*x) for a in ARMS for t in TASKS}",
        "scores = {(rep,a,t): max([r['score'] for r in rows if (r['repeat'],r['arm'],r['task'])==(rep,a,t)],key=lambda x:SIGN[t]*x) for rep in (0,1) for a in ARMS for t in TASKS}")
replace("actual = all(any(e['arm'] == a and e['role'] == 'improve' and e['success'] for e in calls) for a in ARMS)",
        "actual = all(any(e['index']//8==b and e['role']=='improve' and e['success'] for e in calls) for b in range(4))")
replace('bool(passed and structure and actual)','bool(passed and structure and actual and input_gate)')
replace("    write(out/'identity.json', identities); write(out/'summary.json', result)",
        "    result.update(by_pool=summarize(rows))\n    write(out/'identity.json', identities); write(out/'summary.json', result)")
namespace=dict(vars(prior),ARMS=ARMS,ORDER=ORDER,RUN=RUN,SLOT=SLOT,CAP=CAP,
    effort=effort,model=model,quality=quality,runtime_inputs=runtime_inputs,summarize=summarize,__file__=__file__)
exec(compile(source,__file__,'exec'),namespace)
analyze=namespace['analyze']

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('out');ap.add_argument('--gpu-seconds',type=int,required=True)
    a=ap.parse_args();analyze(a.root,a.out,a.gpu_seconds)
