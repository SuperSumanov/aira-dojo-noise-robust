"""Frozen48-run deployment readout; both strong references, both repeats."""
import argparse
from pathlib import Path
import statistics
import weight_confirmation_readout_20261014 as prior
from weight_effort_policy_20261014 import effort,model

ARMS=('old_fast','old_medium','new_medium')
ORDER=('old_fast','old_medium','new_medium','new_medium','old_medium','old_fast')
RUN,SLOT,CAP=1800,1960,13500
TASKS,SIGN=prior.TASKS,prior.SIGN


def quality(scores):
    contrasts=[dict(repeat=rep,task=t,method='new_medium',reference=ref,
        method_best=scores[rep,'new_medium',t],reference_best=scores[rep,ref,t],
        oriented_delta=SIGN[t]*(scores[rep,'new_medium',t]-scores[rep,ref,t]))
        for rep in (0,1) for ref in ('old_fast','old_medium') for t in TASKS]
    return contrasts,all(r['oriented_delta']>=(.001 if r['task']==TASKS[1] else -1e-12) for r in contrasts)


def summarize(rows):
    out=[]
    for block,arm in enumerate(ORDER):
        for task in TASKS:
            values=[r['score'] for r in rows if r['block']==block and r['task']==task]
            assert len(values)==4 and all(v is not None for v in values)
            out.append(dict(block=block,repeat=block//3,arm=arm,task=task,
                best=max(values,key=lambda x:SIGN[task]*x),median=statistics.median(values),
                sample_sd=statistics.stdev(values),n=4))
    return out


def runtime_inputs(root,p,rows):
    expected=prior.prior.read(root/'input-matrix/summary.safe.json')
    assert expected['assigned']==expected['passed']==48 and expected['exact_input_gate']
    assert prior.prior.sha(root/'public-preview.private.json')==p['public_preview_sha256']
    checks=[]
    for row in rows:
        ref=expected['rows'][row['index']]
        assert all(row[k]==ref[k] for k in ('index','arm','task','seed'))
        path=root/f"episode-{row['index']}/input-gate.jsonl"
        events=prior.prior.lines(path) if path.exists() else []
        gates=[x for x in events if x['event']=='first_request_input_gate']
        previews=[x for x in events if x['event']=='fixed_public_preview_loaded']
        ok=(len(gates)==1 and gates[0].get('passed') is True
            and gates[0]['sha256']==gates[0]['expected_sha256']==ref['first_prompt_sha256']
            and bool(previews) and all(x['sha256']==ref['preview_sha256'] for x in previews))
        checks.append(dict(index=row['index'],passed=ok,expected_sha256=ref['first_prompt_sha256'],
            observed_sha256=gates[0]['sha256'] if len(gates)==1 else None))
    return checks


source=prior.source
for old,new in [("p['planned'] == 32","p['planned'] == 48"),
                ('dict(assigned=32,','dict(assigned=48,'),
                ('for b in range(4):','for b in range(6):'),
                ('for b in range(4))','for b in range(6))')]:
    assert source.count(old)==1,old
    source=source.replace(old,new)
namespace=dict(prior.namespace,ARMS=ARMS,ORDER=ORDER,RUN=RUN,SLOT=SLOT,CAP=CAP,
    effort=effort,model=model,quality=quality,runtime_inputs=runtime_inputs,summarize=summarize,__file__=__file__)
exec(compile(source,__file__,'exec'),namespace)
analyze=namespace['analyze']


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('out');ap.add_argument('--gpu-seconds',type=int,required=True)
    a=ap.parse_args();analyze(a.root,a.out,a.gpu_seconds)
