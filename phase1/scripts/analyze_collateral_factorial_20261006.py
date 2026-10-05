"""Closed-batch descriptive numeric-bundle causal contrasts; no reselection.

Four executions per old development edge diagnose a mechanism, not a deployable
same-budget method. Static token/character changes invalidate semantic sameness
of MAX_LEN; all such cases remain in the denominator and are explicitly flagged.
"""
import csv
import json
import math
import os
import statistics
import subprocess
import sys
from run_collateral_factorial_20261006 import B, R, check, load, read, schedule, sha, write

PIZZA = 'random-acts-of-pizza'

def compare(values):
    if set(values) != {'P', 'C', 'CP', 'PC'} or any(v is None for v in values.values()):
        return dict(complete=False, CP_minus_P=None, C_minus_P=None,
            CP_minus_C=None, PC_minus_P=None, interaction=None, rescue=None)
    p, c, cp, pc = (values[k] for k in ('P', 'C', 'CP', 'PC'))
    assert all(math.isfinite(v) for v in values.values())
    return dict(complete=True, CP_minus_P=cp-p, C_minus_P=c-p,
        CP_minus_C=cp-c, PC_minus_P=pc-p, interaction=c-cp-pc+p,
        rescue=cp>p and c<=p)

def independent(task, prediction, spec):
    from sklearn.metrics import roc_auc_score
    manifest = B/spec['view']/'manifest.json'
    assert sha(manifest) == spec['view_sha']
    if task == PIZZA:
        truth_path = B/spec['source']/'private/dsearch.csv'
        assert sha(truth_path) == read(manifest)['source_dsearch_sha256']
        ident = spec['id']; label = spec['label']
    else:
        truth_path = B/spec['view']/'private/dsearch.csv'
        assert sha(truth_path) == read(manifest)['files_sha256']['dsearch']
        ident = 'textID'; label = 'selected_text'
    with truth_path.open(newline='', encoding='utf-8-sig') as f:
        truth = list(csv.DictReader(f))
    with prediction.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    pred = {r[ident]:r[label] for r in rows}
    assert len(pred) == len(rows) == len(truth)
    assert set(pred) == {r[ident] for r in truth}
    if task == PIZZA:
        return float(roc_auc_score([int(r[label]) for r in truth],
                                  [float(pred[r[ident]]) for r in truth]))
    total = 0.0
    for r in truth:
        a, b = set(r[label].lower().split()), set(pred[r[ident]].lower().split())
        assert a
        total += len(a.intersection(b)) / len(a.union(b))
    return total / len(truth)

def main():
    plan = check()
    launch = read(R/'serial-launch.json') if (R/'serial-launch.json').exists() else read(R/'launch.json')
    job = launch['job']; gpus = 2
    amendment_sha = None
    if (R/'serial-launch.json').exists():
        amendment_sha = sha(R/'scheduling-amendment.json')
        assert launch['amendment_sha256'] == amendment_sha
        a = read(R/'scheduling-amendment.json')
        assert a['original_plan_sha256'] == sha(R/'plan.json')
        assert a['gpus'] == 1 and a['gpu_hours_cap'] == 4
        gpus = 1
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    assert not subprocess.check_output(['squeue','-j',job,'-h','-o','%i'], env=env, text=True, timeout=20).strip()
    lines = subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o',
        'JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'], env=env, text=True, timeout=20).strip().splitlines()
    assert len(lines) == 1
    jid, state, elapsed, tres, exitcode, *_ = lines[0].split('|')
    assert jid == job and f'gres/gpu={gpus}' in tres
    assert state.startswith(('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY'))
    assert read(R/'closed.json')['assigned'] == 32, 'whole batch must be closed before scoring'
    assert all((R/f"episode-{s['index']}/closed.json").exists() for s in schedule())
    out = R/'readout-v1'; out.mkdir(mode=0o700, exist_ok=False)
    freeze = {str(p.relative_to(R)):sha(p) for p in R.glob('episode-*/action-0/submission.private.csv')}
    write(out/'prediction-freeze.json', freeze)
    rows=[]; errors=[]
    for s in schedule():
        ep=R/f"episode-{s['index']}"; pred=ep/'action-0/submission.private.csv'
        d=read(ep/'completed.json') if (ep/'completed.json').exists() else {}
        row=dict(**s, completed=bool(d), valid=False, dev_metric=None,
            metric='auc' if s['task']==PIZZA else 'mean_word_jaccard',
            seconds=d.get('seconds'), exec_seconds=d.get('exec_seconds'),
            timed_out=d.get('timed_out'), error_type=d.get('error_type'),
            step_returncode=read(ep/'closed.json')['returncode'], prediction_sha256=None,
            source_commit=plan['source_commit'])
        if d.get('valid_execution') and row['step_returncode']==0:
            assert pred.is_file() and sha(pred)==d['prediction_sha256']
            cfg=read(R/'configs'/f"{s['index']}.json")
            scorer=cfg['task']['search_only_dev_scorer_path']
            assert sha(scorer)==cfg['task']['search_only_dev_scorer_sha256']
            m=load('collateral_scorer_'+str(s['index']), scorer)
            try:
                result=m.score(s['task'], pred)
            except m.InvalidSubmissionError:
                row['error_type']='InvalidSubmissionError'
            else:
                v=result[row['metric']]
                v2=independent(s['task'],pred,m.SPEC[s['task']])
                err=abs(v-v2); assert math.isfinite(v) and err<1e-12
                errors.append(err)
                row.update(valid=True,dev_metric=v,prediction_sha256=sha(pred))
        rows.append(row)
    contrasts=[]
    for case in range(8):
        q={r['arm']:r for r in rows if r['case']==case}
        assert len(q)==4
        contrasts.append(dict(case=case,task=q['P']['task'],
            **compare({k:v['dev_metric'] for k,v in q.items()}),
            pre_outcome_semantic_caveat=('MAX_LEN changes units: characters to words/tokens; numeric restoration is not matched semantic capacity.' if case in (6,7) else
                'Architecture changes BiLSTM to Transformer; LR transfer need not preserve suitable optimization.' if case==5 else
                'All untransplanted changes remain bundled; no intent/semantic equivalence guarantee.')))
    per_task=[]
    for task in sorted({r['task'] for r in rows}):
        q=[c for c in contrasts if c['task']==task and c['complete']]
        vals=[c['CP_minus_C'] for c in q]
        per_task.append(dict(task=task,assigned_edges=4,complete_quartets=len(q),
            strict_rescues=sum(c['rescue'] for c in q),
            CP_minus_C_median=statistics.median(vals) if vals else None,
            CP_minus_C_sample_variance=statistics.variance(vals) if len(vals)>1 else None))
    for rel,h in freeze.items(): assert sha(R/rel)==h
    summary=dict(protocol=plan['protocol'],source_commit=plan['source_commit'],
        plan_sha256=sha(R/'plan.json'),analysis_sha256=sha(__file__),job=job,
        allocation_state=state,exitcode=exitcode,allocation_seconds=int(elapsed),
        allocated_gpu_hours=gpus*int(elapsed)/3600,assigned=32,
        scheduling_amendment_sha256=amendment_sha,
        valid=sum(r['valid'] for r in rows),independent_scores=len(errors),
        max_absolute_verifier_error=max(errors,default=None),contrasts=contrasts,
        per_task=per_task,new_method_confirmed=False,automatic_expansion=False,
        protected_opened=False,limitation=plan['limitation']+' '+plan['cost'])
    write(out/'summary.json',summary)
    for name,data in [('runs.csv',rows),('contrasts.csv',contrasts)]:
        with (out/name).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    write(out/'export-receipt.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps(summary))

def tests():
    x=compare(dict(P=.5,C=.4,CP=.6,PC=.3))
    assert x['rescue'] and abs(x['interaction'])<1e-12
    assert not compare(dict(P=.5,C=.6,CP=.7,PC=.4))['rescue']
    assert not compare(dict(P=.5,C=.4,CP=.5,PC=.3))['rescue']
    assert compare(dict(P=.5,C=None,CP=.6,PC=.3))['rescue'] is None
    assert not compare({})['complete']
    print(json.dumps(dict(status='PASS',fixtures=5)))

if __name__=='__main__':
    os.umask(0o077)
    tests() if sys.argv[1:]==['--tests'] else main()
