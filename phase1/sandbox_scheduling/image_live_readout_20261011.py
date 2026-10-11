"""Independent all-assignment quality readout. Never scores protected cohorts.

This reads only the fresh image-live batch; no missing endpoint imputation,
no global scheduling superiority or population inference from two pool pairs.
"""
import csv,json,math,statistics,sys
from pathlib import Path
from lifecycle_pilot import read,write,sha
from live_readout import finite,ground_scores,queue_verify,lines,timely_returns
from image_dev_data_20261011 import TASKS,score_at

def summarize(rows):
    assert len(rows)==32 and len({r['index'] for r in rows})==32
    pairs=[];per_task={task:[] for task in TASKS};wins={task:dict(win=0,loss=0,tie=0,unobserved=0) for task in TASKS}
    for rep in (0,1):
        for lane in range(4):
            for task in TASKS:
                pair={r['arm']:r for r in rows if (r['repeat'],r['lane'],r['task'])==(rep,lane,task)}
                a,b=pair['fifo1'],pair['share2'];assert a['seed']==b['seed']
                av=a['complete'] and a['valid'] and finite(a['score']);bv=b['complete'] and b['valid'] and finite(b['score'])
                delta=(-1 if task==TASKS[1] else 1)*(b['score']-a['score']) if av and bv else None
                if delta is not None:per_task[task].append(delta)
                if av and bv:sign=(delta>0)-(delta<0)
                elif a['started'] and b['started']:sign=int(bv)-int(av)
                else:sign=None
                wins[task]['unobserved' if sign is None else 'win' if sign>0 else 'loss' if sign<0 else 'tie']+=1
                pairs.append(dict(repeat=rep,lane=lane,task=task,seed=a['seed'],oriented_delta=delta,validity_rank_sign=sign))
    pools=[]
    for rep in (0,1):
        selected=[r for r in rows if r['repeat']==rep]
        present=all(r['started'] for r in selected)
        for task in TASKS:
            best={}
            for arm in ('fifo1','share2'):
                scores=[r['score'] for r in selected if r['task']==task and r['arm']==arm and r['complete'] and r['valid'] and finite(r['score'])]
                best[arm]=(min(scores) if task==TASKS[1] else max(scores)) if scores else None
            pools.append(dict(repeat=rep,task=task,best=best,complete_pool_assignment=present,
                oriented_best_delta=(-1 if task==TASKS[1] else 1)*(best['share2']-best['fifo1']) if all(finite(v) for v in best.values()) and present else None))
    medians={task:statistics.median(values) if values else None for task,values in per_task.items()}
    diffs=[];cuda_diffs=[]
    for rep in (0,1):
        selected=[r for r in rows if r['repeat']==rep]
        for field,target in [('valid_returns',diffs),('cuda_valid_returns',cuda_diffs)]:
            target.append(sum(r[field] for r in selected if r['arm']=='share2')-sum(r[field] for r in selected if r['arm']=='fifo1') if all(r['started'] for r in selected) else None)
    all_complete=all(r['complete'] for r in rows)
    quality_gate=bool(all_complete and all(finite(p['oriented_delta']) for p in pairs)
        and all(finite(v) and v>=0 for v in medians.values()) and any(finite(v) and v>0 for v in medians.values())
        and all(v is not None and v>0 for v in cuda_diffs))
    return dict(assigned=32,started=sum(r['started'] for r in rows),complete=sum(r['complete'] for r in rows),
        valid=sum(r['complete'] and r['valid'] for r in rows),pairs=pairs,pool_task_best=pools,
        per_task_oriented_differences=per_task,per_task_medians=medians,
        per_task_sample_sd={task:statistics.stdev(ds) if len(ds)>1 else None for task,ds in per_task.items()},
        validity_rank=wins,paired_pool_valid_return_differences=diffs,paired_pool_cuda_valid_return_differences=cuda_diffs,
        quality_gate_before_structure=quality_gate,independent_pool_pairs=2,
        limitation='Exploratory public-training development only; 32 trajectories are not32 independent scheduling replicates. No missing score imputation, posthoc seed replacement or SchedMate claim.')

def analyze(root,output,gpu_seconds):
    root=Path(root);output=Path(output);p=read(root/'plan.json');closed=read(root/'closed.json')
    assert p['planned']==32 and p['gpus']==6 and 0<=gpu_seconds<=p['allocation_seconds']*6
    for n,h in p['files'].items():assert sha(root/n)==h
    for n,h in p['input_files'].items():assert sha(root/n)==h
    spec=read(root/'dev-views/spec.json');rows=[];score_recomputed=0;blocks=[]
    for item in p['schedule']:
        ep=root/f"episode-{item['index']}";f=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        c=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        candidates=[read(v) for v in ep.glob('candidate-*.json') if '.private.' not in v.name]
        timely=timely_returns(candidates,p['run_seconds']);receipts=[];cuda=0
        for file in sorted(ep.glob('scored-*.json')):
            saved=read(file);receipt=saved['receipt'];receipts.append(receipt)
            csv_path=ep/(file.stem+'.private.csv');actual=score_at(root,spec,item['task'],csv_path)
            metric=spec[item['task']]['metric_name'];assert abs(actual[metric]-receipt[metric])<=1e-12 and actual['submission_sha256']==receipt['submission_sha256'];score_recomputed+=1
            training=ep/('gpu-training-'+file.stem.split('-')[-1]+'.json')
            matched=any(r['valid'] and r['aux']['submission_sha256']==receipt['submission_sha256'] for r in timely)
            if matched and training.exists() and read(training)['cuda_gradient_steps']>0:cuda+=1
        grounded=ground_scores(f,timely,receipts)
        complete=c.get('returncode')==0 and c.get('cleanup_verified') is True and f.get('status') in ('completed','budget_exhausted')
        rows.append(dict(item,started=(ep/'deadline.json').exists(),complete=complete,valid=f.get('native_selected_valid',False),score=f.get('native_selected_score'),
            score_grounded=grounded,valid_returns=sum(r['valid'] for r in timely),cuda_valid_returns=cuda,
            code_sha256=f.get('native_selected_code_sha256'),source_commit=p['source_commit']))
    for block in range(4):
        bd=root/f'block-{block}';queues=[]
        for lane in range(4):
            q=root/f'queue-{block}-{lane}';queues.append(queue_verify(lines(q/'events.jsonl'),1 if block in (0,3) else 2))
        budget=read(bd/'budget-slot.json') if (bd/'budget-slot.json').exists() else {}
        steps=read(bd/'steps.json') if (bd/'steps.json').exists() else {}
        blocks.append(dict(block=block,queues=queues,budget=budget,
            complete=all(q['complete'] for q in queues) and budget.get('reserved_seconds')==2400 and steps.get('returncodes')==[0]*4))
    summary=summarize(rows);summary.update(structural_complete=all(b['complete'] for b in blocks),scores_recomputed=score_recomputed,
        all_scores_grounded=all(r['score_grounded'] for r in rows),gpu_seconds=gpu_seconds,gpu_hours=gpu_seconds/3600,
        plan_sha256=sha(root/'plan.json'),controller_error=closed.get('error'))
    summary['exploratory_go']=summary['quality_gate_before_structure'] and summary['structural_complete'] and summary['all_scores_grounded']
    output.mkdir();write(output/'runs.json',rows);write(output/'blocks.json',blocks);write(output/'summary.json',summary)
    with (output/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({k:summary[k] for k in ('assigned','started','complete','valid','per_task_medians','paired_pool_valid_return_differences','paired_pool_cuda_valid_return_differences','exploratory_go','gpu_hours')},allow_nan=False))

if __name__=='__main__':analyze(sys.argv[1],sys.argv[2],int(sys.argv[3]))
