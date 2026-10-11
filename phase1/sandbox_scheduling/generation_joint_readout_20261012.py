"""Quality-first readout for the prospectively frozen joint-admission batch.

Read only after closure. Independent numeric rank calculation, all48
assignments, all eight pool/task/reference contrasts; no complete-case rescue.
Raw source, model responses and predictions never leave the experiment root.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import sys

from lifecycle_pilot import read,write,sha
from live_readout import lines,finite,queue_verify,timely_returns,ground_scores

ARMS=('continuation','cost','joint')
TASKS=('aerial-cactus-identification','denoising-dirty-documents')
SIGN={TASKS[0]:1,TASKS[1]:-1}


def independent_rank(request, snapshot, now, arm, busy):
    s=snapshot['stats'][str(request['run'])]
    age=max(0.,now-request['requested'])
    role=int(request['role']=='analyze')
    if arm=='continuation':return (role,s['completed']+int(request['role']=='debug'),age,-request['run'])
    lane=busy.get(str(request['lane']));extra=0.
    if arm=='joint' and lane and request['role']!='analyze':
        # Frozen caller samples decision_time immediately before reading lane
        # occupancy. A concurrently acquired lease can have a slightly later
        # timestamp; replay the signed interval, not a new clamped policy.
        extra=max(0.,lane['expected_seconds']-(now-lane['start'])-s['generation_mean'])
    cost=max(1.,s['generation_mean']+s['execution_mean']+s['analysis_mean']+extra)
    feasible=request['role']=='analyze' or request['deadline']-now>=cost
    return(role,int(feasible),(s['improvements']+1)/(s['completed']+2)*(1+age/300)/cost,age,-request['run'])


def generation_audit(events, arm):
    waiting={};active={};seen=set();completed={};improvements={};scarce=divergent=admissions=0;peak=0
    for e in events:
        k=e.get('key');kind=e['event']
        if kind=='warm_start':continue
        if kind=='round_complete':
            run=str(e['run']);completed[run]=completed.get(run,0)+1
            improvements[run]=improvements.get(run,0)+int(e['improved'])
            assert e['completed']==completed[run];continue
        if kind=='queued':
            r=e['request'];k=r['key'];assert k not in seen;seen.add(k);waiting[k]=r
        elif kind=='admitted':
            assert k in waiting
            snap=e['snapshot'];assert {r['key'] for r in snap['waiting']}==set(waiting)
            assert {r['key'] for r in snap['active']}==set(active)
            for run,s in snap['stats'].items():
                assert s['completed']==completed.get(run,0) and s['improvements']==improvements.get(run,0)
            task=waiting[k]['task'];candidates=[r for r in waiting.values() if r['task']==task]
            assert sum(r['task']==task for r in active.values())<2
            expected={a:max(candidates,key=lambda r:independent_rank(r,snap,e['decision_time'],a,e['occupancy']))['key'] for a in ARMS}
            assert expected==e['alternatives'] and expected[arm]==k
            scarcity=len(candidates)>2-sum(r['task']==task for r in active.values())
            assert scarcity==e['scarce'];scarce+=scarcity
            divergent+=scarcity and expected['cost']!=expected['joint']
            active[k]=waiting.pop(k);admissions+=1;peak=max(peak,len(active))
        elif kind=='released':assert k in active;active.pop(k)
        elif kind=='cancelled':assert k in waiting;waiting.pop(k)
        else:raise ValueError('unexpected generation event')
    return dict(admissions=admissions,scarce_choices=scarce,resource_changed_choices=divergent,
        peak_active=peak,all_released=not waiting and not active,completed_rounds=sum(completed.values()),
        improving_rounds=sum(improvements.values()))


def distribution(values):
    return dict(n=len(values),median=statistics.median(values) if values else None,
        sample_sd=statistics.stdev(values) if len(values)>1 else None)


def deployable_best(task, initial, timely):
    # Diagnostic only: same cutoff/exit/validity, but does not require the
    # optional LLM analysis to finish before retaining an already graded code.
    scores=[initial]+[r['score'] for r in timely if r.get('valid') is True
        and r.get('exit_code')==0 and not r.get('timed_out') and finite(r.get('score'))]
    return max(scores,key=lambda x:SIGN[task]*x)


def summarize(rows, initial):
    assert len(rows)==48 and {r['index'] for r in rows}==set(range(48))
    assert len({(r['repeat'],r['task'],r['lane'],r['arm']) for r in rows})==48
    pairs=[];pools=[]
    for repeat in (0,1):
        for task in TASKS:
            per={a:[r for r in rows if (r['repeat'],r['task'],r['arm'])==(repeat,task,a)] for a in ARMS}
            assert all(len(x)==4 for x in per.values())
            best={a:max([initial[task]]+[r['score'] for r in rs if r['valid']],key=lambda x:SIGN[task]*x) for a,rs in per.items()}
            for ref in ARMS[:2]:
                pools.append(dict(repeat=repeat,task=task,reference=ref,
                    joint_best=best['joint'],reference_best=best[ref],
                    oriented_delta=SIGN[task]*(best['joint']-best[ref]),
                    all_assigned_started=all(r['started'] for a in (ref,'joint') for r in per[a]),
                    all_assigned_clean=all(r['cleanup'] for a in (ref,'joint') for r in per[a])))
                for lane in range(4):
                    a,b=(next(r for r in per[arm] if r['lane']==lane) for arm in (ref,'joint'))
                    assert a['seed']==b['seed']
                    # Null is still null at run level, even though the supplied
                    # common checkpoint remains available at portfolio level.
                    d=SIGN[task]*(b['score']-a['score']) if a['valid'] and b['valid'] else None
                    pairs.append(dict(repeat=repeat,task=task,reference=ref,lane=lane,seed=a['seed'],oriented_delta=d))
    no_loss=all(r['oriented_delta']>=-1e-12 for r in pools)
    material=any(all(r['oriented_delta']>=.001 for r in pools if r['task']==task) for task in TASKS)
    return dict(assigned=48,pool_repeats=2,initial_score=initial,pool_task_contrasts=pools,run_pairs=pairs,
        no_task_repeat_loss_to_either_reference=no_loss,same_task_material_gain_both_references_both_repeats=material,
        quality_signal_before_structure=no_loss and material,
        contrast_distribution={t:{a:distribution([r['oriented_delta'] for r in pools if (r['task'],r['reference'])==(t,a)]) for a in ARMS[:2]} for t in TASKS},
        by_arm={a:dict(assigned=16,started=sum(r['started'] for r in rows if r['arm']==a),
            complete=sum(r['complete'] for r in rows if r['arm']==a),
            valid=sum(r['valid'] for r in rows if r['arm']==a),
            improved=sum(r['valid'] and SIGN[r['task']]*(r['score']-initial[r['task']])>1e-12 for r in rows if r['arm']==a),
            task_gain={t:distribution([SIGN[t]*(r['score']-initial[t]) for r in rows if (r['arm'],r['task'])==(a,t) and r['valid']]) for t in TASKS}) for a in ARMS},
        boundary='Conditional refinement from supplied valid checkpoint; all48 assigned. Two reversed-order pool replicates, not48 independent scheduling samples. Common checkpoint construction is historical initialization, not free from-scratch performance. Small controlled baseline adaptations, not published SOTA replicas.')


def analyze(root, output, gpu_seconds):
    root=Path(root);p=read(root/'plan.json');closed=read(root/'closed.json')
    assert p['planned']==48 and p['allocation_seconds']==7560 and p['slot_seconds']==1180 and p['run_seconds']==1020
    assert p['prior_failures'][0]['job']=='17673' and p['prior_failures'][0]['gpu_seconds']==2856
    assert p['prior_failures'][1]['job']=='17674' and p['prior_failures'][1]['gpu_seconds']==2118
    prior=sum(r['gpu_seconds'] for r in p['prior_failures'])
    assert 0<gpu_seconds<=7560*6 and gpu_seconds+prior<=50400
    for name,h in p['files'].items():assert sha(root/name)==h
    for name,h in p['input_files'].items():assert sha(root/name)==h
    # This imports the pinned scoring code from THIS trial, not a mutable tree.
    sys.path.insert(0,str(root))
    from image_dev_data_20261011 import score_at
    from live_identity import cores
    spec=read(root/'dev-views/spec.json');warm=read(root/'warm-receipt.json')
    initial={t:warm[t]['score'] for t in TASKS}
    rows=[];recomputed=0
    for s in p['schedule']:
        ep=root/f"episode-{s['index']}";f=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        closure=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        cs=[read(x) for x in ep.glob('candidate-*.json') if '.private.' not in x.name]
        timely=timely_returns(cs,p['run_seconds']);receipts=[]
        for path in ep.glob('scored-*.json'):
            rec=read(path)['receipt'];receipts.append(rec)
            actual=score_at(root,spec,s['task'],ep/(path.stem+'.private.csv'));metric=spec[s['task']]['metric_name']
            assert actual['submission_sha256']==rec['submission_sha256'] and abs(actual[metric]-rec[metric])<=1e-12;recomputed+=1
        grounded=ground_scores(dict(f,native_selected_valid=False),timely,receipts)
        is_warm=f.get('native_selected_code_sha256')==warm[s['task']]['code_sha256'] and f.get('native_selected_score')==initial[s['task']]
        if f.get('native_selected_valid'):
            grounded=grounded and (is_warm or ground_scores(f,timely,receipts));assert grounded
        rows.append(dict(s,source_commit=p['source_commit'],run_seconds=p['run_seconds'],pool_seconds=p['slot_seconds'],
            started=(ep/'deadline.json').exists(),complete=closure.get('returncode')==0 and closure.get('cleanup_verified') is True and f.get('status') in ('completed','budget_exhausted'),
            cleanup=closure.get('cleanup_verified') is True,returncode=closure.get('returncode'),
            valid=f.get('native_selected_valid') is True and grounded and finite(f.get('native_selected_score')),
            score=f.get('native_selected_score'),initial_score=initial[s['task']],selected_warm=is_warm,
            external_best_score=deployable_best(s['task'],initial[s['task']],timely),
            candidate_returns=len(timely),valid_returns=sum(r['valid'] for r in timely),late_returns=len(cs)-len(timely),
            score_grounded=grounded))
    budgets=[];identities=[];policies=[];cpu=[]
    for block in range(6):
        bd=root/f'block-{block}';arm=p['schedule'][block*8]['arm']
        slot=read(bd/'budget-slot.json') if (bd/'budget-slot.json').exists() else {}
        steps=read(bd/'steps.json') if (bd/'steps.json').exists() else {}
        q=[queue_verify(lines(root/f'queue-{block}-{lane}/events.jsonl'),1) for lane in range(4)]
        budgets.append(slot.get('reserved_seconds')==1180 and 1180<=slot.get('actual_seconds',0)<=1182 and steps.get('returncodes')==[0]*4 and all(r['complete'] for r in q))
        policies.append(dict(block=block,arm=arm,**generation_audit(lines(root/f'generation-{block}/events.jsonl'),arm)))
        service=read(bd/'service-native.json') if (bd/'service-native.json').exists() else {}
        lanes=[read(bd/f'lane-{i}-native.json') if (bd/f'lane-{i}-native.json').exists() else {} for i in range(4)]
        devices=[x.get('gpu_uuid') for x in lanes];svc=service.get('gpu_uuids',[])
        sets=[cores(x.get('cpu_topology',[])) for x in lanes]+[cores(service.get('cpu_topology',[]))]
        ok=all(devices) and len(set(devices))==4 and len(set(svc))==2 and not set(devices)&set(svc) and all(len(x)==4 for x in sets[:4]) and len(sets[-1])==8 and all(not sets[i]&sets[j] for i in range(5) for j in range(i))
        identities.append(dict(block=block,valid=bool(ok),lanes=devices,service=svc))
        for lane in range(4):
            paths=[root/f'episode-{block*8+lane*2+k}/cpu-partition.json' for k in (0,1)]
            if not all(x.exists() for x in paths):cpu.append(False);continue
            a,b=(read(x) for x in paths);ac,bc=cores(a['worker_topology']),cores(b['worker_topology'])
            cpu.append(len(ac)==len(bc)==2 and not ac&bc and ac|bc==cores(a['parent_topology'])==cores(b['parent_topology']))
    cleaned=read(root/'block-0/service-cleanup.json') if (root/'block-0/service-cleanup.json').exists() else {}
    physical=all(r['valid'] and r['lanes']==identities[0]['lanes'] and set(r['service'])==set(identities[0]['service']) for r in identities)
    structural=all(budgets) and all(cpu) and physical and cleaned.get('gpu_clean') is True and closed['error'] is None and all(r['started'] and r['cleanup'] and r['score_grounded'] for r in rows) and all(r['all_released'] for r in policies)
    signal=any(r['scarce_choices'] and r['resource_changed_choices'] for r in policies if r['arm']=='joint')
    result=summarize(rows,initial)
    external=summarize([dict(r,valid=True,score=r['external_best_score']) for r in rows],initial)
    retention=[dict(index=r['index'],arm=r['arm'],task=r['task'],
        oriented_gap=SIGN[r['task']]*(r['external_best_score']-r['score'])) for r in rows if r['valid']]
    result['external_endpoint_diagnostic']=dict(
        status='Secondary retention check added before any quality readout, after first pool finished; frozen primary gate unchanged.',
        definition='Best externally graded timely exit0 non-timeout program plus supplied initial checkpoint. No new execution or hidden evaluation.',
        pool_task_contrasts=external['pool_task_contrasts'],native_retention_gaps=retention,
        native_outside_strict_external_contract=[r['index'] for r in retention if r['oriented_gap'] < -1e-12],
        quality_condition=external['quality_signal_before_structure'],
        cannot_rescue_failed_primary=True)
    result.update(source_commit=p['source_commit'],plan_sha256=sha(root/'plan.json'),readout_sha256=sha(__file__),
        gpu_seconds=gpu_seconds,gpu_hours=gpu_seconds/3600,prior_failure_gpu_seconds=prior,
        window_gpu_seconds=gpu_seconds+prior,window_gpu_hours=(gpu_seconds+prior)/3600,structural_complete=bool(structural),
        policy_choices=policies,live_resource_choice_divergence=signal,scores_recomputed=recomputed,
        cpu_pairs_passed=sum(cpu),cpu_pairs_planned=24,physical_identity_passed=physical,
        exploratory_quality_signal=bool(structural and signal and result['quality_signal_before_structure']),
        no_automatic_expansion=True)
    output=Path(output);output.mkdir()
    write(output/'summary.json',result);write(output/'runs.json',rows);write(output/'identity.json',identities)
    with (output/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(result,allow_nan=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('output');ap.add_argument('--gpu-seconds',type=int,required=True)
    a=ap.parse_args();analyze(a.root,a.output,a.gpu_seconds)
