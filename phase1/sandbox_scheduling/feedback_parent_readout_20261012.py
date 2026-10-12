"""Predeclared independent readout; endpoint is timely external best, not imports."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import tempfile

ARMS=('greedy','pending_ucb','feedback_gate')
ORDER=ARMS+tuple(reversed(ARMS))
TASKS=('aerial-cactus-identification','denoising-dirty-documents')
SIGN={TASKS[0]:1,TASKS[1]:-1}


def read(p):return json.loads(Path(p).read_text())
def lines(p):return [json.loads(x) for x in Path(p).read_text().splitlines() if x]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,sort_keys=True,allow_nan=False)


def quality_summary(scores):
    contrasts=[]
    for rep in range(2):
        blocks={ORDER[b]:b for b in range(rep*3,rep*3+3)}
        for task in TASKS:
            for ref in ARMS[:2]:
                a,b=scores[blocks['feedback_gate'],task],scores[blocks[ref],task]
                contrasts.append(dict(repeat=rep,task=task,reference=ref,method_best=a,reference_best=b,
                                      oriented_delta=SIGN[task]*(a-b)))
    gain=all(x['oriented_delta']>=.001 for x in contrasts if x['task']==TASKS[1])
    nonloss=all(x['oriented_delta']>=-1e-12 for x in contrasts if x['task']==TASKS[0])
    return dict(contrasts=contrasts,denoising_material_both_repeats_both_references=gain,
                aerial_no_loss=nonloss,quality_gate=gain and nonloss)


def native_cpu_test(root,host,install_hooks):
    from feedback_parent_policy_20261012 import initialize,locked,key_for,record,install
    host().setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.core.tasks.constants import TASK_DESCRIPTION,EXECUTION_OUTPUT,VALIDATION_FITNESS,VALID_SOLUTION
    from dojo.core.interpreters.base import ExecutionResult
    from dojo.utils.experiment_deadline import ExperimentDeadline
    from dojo.utils.logger import config_logger
    from omegaconf import OmegaConf
    import dojo.solvers.mcts.mcts as mm
    p=read(root/'plan.json');row=dict(p['schedule'][0],arm='feedback_gate');warm=read(root/'warm.private.json')
    fixture=Path(tempfile.mkdtemp(prefix='cpu-native-fixture-',dir=root));ep=fixture/'episode-0';ep.mkdir()
    initialize(fixture/'generation-0',p['schedule'][:8],warm)
    # The unchanged container lease hook requires a real Slurm allocation.
    # Exercise the new native parent hook directly, as in the donor CPU gate.
    install(row,ep,ExperimentDeadline(60),warm[row['task']])
    cfg=RunConfig.load_from_json(root/'configs/0.json');cfg.solver.checkpoint_path=str(fixture/'checkpoint');cfg.logger.output_dir=str(fixture/'log')
    task=MLEBenchTask(cfg.task);config_logger(cfg)
    solver=MCTS(OmegaConf.structured(cfg.solver),{TASK_DESCRIPTION:task.task_description,'lower_is_better':task._search_only_lower_is_better})
    log=solver.log_journal
    solver.log_journal=lambda:(log(),solver.save_checkpoint())
    solver.create_root_node()
    # A previously observed peer parent is available. Real import and journal
    # serialization must work, not only the ranking function in a mock.
    peer=dict(warm[row['task']],code='print("peer CPU fixture")',metric=warm[row['task']]['metric']+.00001)
    with locked(fixture/'generation-0') as s:s['archive'][row['task']][key_for(peer['code'])]=record(peer,1)
    calls=[0]
    def op(*args,**kwargs):
        calls[0]+=1
        return 'CPU fixture',f'print({calls[0]})',[]
    old=mm.execute_op_plan_code;mm.execute_op_plan_code=op
    solver.analyze_fn=lambda *args:({'metric':None,'summary':'fixture','is_bug':True},[])
    class Task:
        calls=0
        def step_task(self,state,code):
            self.calls+=1;valid=self.calls!=2
            return state,{EXECUTION_OUTPUT:ExecutionResult(term_out=['fixture'],exec_time=.1,exit_code=0 if valid else 1),
                          VALIDATION_FITNESS:warm[row['task']]['metric'] if valid else None,VALID_SOLUTION:valid}
    t=Task()
    try:
        solver._expand_leaf_and_backprop(solver.search_policy(solver.root_node),{},t)
        solver.save_checkpoint()
        assert t.calls==3 and any(n.operators_used==['shared_parent'] for n in solver.journal.nodes)
        with locked(fixture/'generation-0') as s:
            assert not s['pending'] and not s['active'] and not s['waiting']
        # A generation exception clears the reservation without manufacturing an outcome.
        def failing(*args,**kwargs):raise RuntimeError('controlled CPU fixture')
        mm.execute_op_plan_code=failing
        try:solver._improve(solver.journal.nodes[1])
        except RuntimeError:pass
        else:raise AssertionError('expected controlled failure')
        with locked(fixture/'generation-0') as s:
            assert not s['pending'] and not s['active'] and not s['waiting']
    finally:mm.execute_op_plan_code=old


def audit(events,arm):
    pending={};active=set();waiting=set();admitted=0;waits=0;changes=0;used={};completed=set();requests={}
    nonwarm=set()
    def independent_choice(s,task,a):
        arc=s['archive'][task];n={k:0 for k in arc}
        for r in s['pending'].values():
            if r['task']==task:n[r['parent']]+=1
        eligible=[k for k in arc if a!='feedback_gate' or n[k]==0]
        if not eligible:return None
        if a=='greedy':return max(eligible,key=lambda k:(s['sign'][task]*arc[k]['metric'],-arc[k]['order']))
        q={k:v['total']/v['visits'] for k,v in arc.items()}
        scale=max(q.values())-min(q.values());total=sum(v['visits']+n[k] for k,v in arc.items())
        return max(eligible,key=lambda k:(((q[k]-min(q.values()))/scale if scale else .5)+.5*math.sqrt(2*math.log(max(2,total))/(arc[k]['visits']+n[k])),-arc[k]['order']))
    for e in events:
        k=e.get('key');kind=e['event']
        if kind=='queued':
            k=e['request']['key'];assert k not in waiting and k not in active;waiting.add(k);requests[k]=e['request']
        elif kind=='admitted':
            assert k in waiting
            assert sum(requests[x]['task']==requests[k]['task'] for x in active)<2
            waiting.remove(k);active.add(k);admitted+=1
            if e['role']=='improve':
                tasks=[t for t,arc in e['snapshot']['archive'].items() if e['parent'] in arc]
                assert len(tasks)==1
                task=tasks[0]
                # The same code may be shared by tasks only if independently admitted;
                # experiment task code hashes are expected distinct and checked here.
                choices={a:independent_choice(e['snapshot'],task,a) for a in ARMS}
                assert choices==e['alternatives'] and e['parent']==choices[arm]
                assert k not in pending
                if arm=='feedback_gate':assert e['parent'] not in pending.values()
                pending[k]=e['parent']
                if e['snapshot']['archive'][task][e['parent']]['order']>0:nonwarm.add(k)
                changes+=int(choices['feedback_gate']!=choices['pending_ucb'])
        elif kind=='released':assert k in active;active.remove(k)
        elif kind=='cancelled':assert k in waiting;waiting.remove(k)
        elif kind=='feedback_wait':
            assert arm=='feedback_gate' and k in waiting and e['reference_parent'] in pending.values()
            assert e['active_generation']==sum(requests[x]['task']==e['task'] for x in active)<2
            waits+=1
        elif kind=='parent_used':assert pending[k]==e['parent'];used[k]=e
        elif kind=='round_complete':
            if k is not None:assert k in pending and k in used;pending.pop(k);completed.add(k)
        elif kind=='abandoned':pending.pop(k,None)
        elif kind!='warm_start':raise ValueError('unknown event')
    assert not pending and not active and not waiting
    return dict(admitted=admitted,feedback_waits=waits,counterfactual_parent_difference=changes,
                completed_improvements=len(completed),completed_nonwarm_parent=len(completed&nonwarm),all_released=True)


def analyze(root,output,gpu_seconds):
    root=Path(root);p=read(root/'plan.json');closed=read(root/'closed.json')
    assert p['planned']==48 and p['allocation_seconds']==7800 and p['prior_failures']==[]
    assert 0<gpu_seconds<=7800*6 and p['run_seconds']==1020 and p['slot_seconds']==1180
    assert all(sha(root/n)==h for n,h in p['files'].items())
    assert all(sha(root/n)==h for n,h in p['input_files'].items())
    sys.path.insert(0,str(root))
    from image_dev_data_20261011 import score_at
    from live_readout import timely_returns,ground_scores,queue_verify
    from live_identity import cores
    spec=read(root/'dev-views/spec.json');warm=read(root/'warm-receipt.json')
    rows=[];recomputed=0
    for s in p['schedule']:
        ep=root/f"episode-{s['index']}"
        f=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        closure=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        cs=[read(x) for x in ep.glob('candidate-*.json') if '.private.' not in x.name]
        timely=timely_returns(cs,1020);receipts=[]
        for x in ep.glob('scored-*.json'):
            receipt=read(x)['receipt'];receipts.append(receipt)
            actual=score_at(root,spec,s['task'],ep/(x.stem+'.private.csv'));metric=spec[s['task']]['metric_name']
            assert actual['submission_sha256']==receipt['submission_sha256'] and abs(actual[metric]-receipt[metric])<=1e-12
            recomputed+=1
        assert ground_scores(dict(f,native_selected_valid=False),timely,receipts)
        eligible=[r['score'] for r in timely if r.get('valid') is True and r.get('exit_code')==0 and not r.get('timed_out') and isinstance(r.get('score'),(int,float)) and math.isfinite(r['score'])]
        initial=warm[s['task']]['score'];best=max([initial]+eligible,key=lambda x:SIGN[s['task']]*x)
        rows.append(dict(s,source_commit=p['source_commit'],run_seconds=1020,pool_seconds=1180,score=best,initial_score=initial,
                         started=(ep/'deadline.json').exists(),complete=closure.get('returncode')==0 and closure.get('cleanup_verified') is True and f.get('status') in ('completed','budget_exhausted'),
                         cleanup=closure.get('cleanup_verified') is True,candidate_returns=len(timely),valid_returns=len(eligible)))
    scores={(b,t):max([r['score'] for r in rows if (r['block'],r['task'])==(b,t)],key=lambda x:SIGN[t]*x) for b in range(6) for t in TASKS}
    result=quality_summary(scores);policies=[];identities=[];budgets=[];cpu=[]
    for b in range(6):
        bd=root/f'block-{b}';slot=read(bd/'budget-slot.json');steps=read(bd/'steps.json')
        budgets.append(slot['reserved_seconds']==1180 and 1180<=slot['actual_seconds']<=1182 and steps['returncodes']==[0]*4)
        assert all(queue_verify(lines(root/f'queue-{b}-{lane}/events.jsonl'),1)['complete'] for lane in range(4))
        policies.append(dict(block=b,arm=ORDER[b],**audit(lines(root/f'generation-{b}/events.jsonl'),ORDER[b])))
        st=read(root/f'generation-{b}/state.json');assert not st['pending'] and not st['waiting'] and not st['active']
        service=read(bd/'service-native.json');lanes=[read(bd/f'lane-{i}-native.json') for i in range(4)]
        devices=[x['gpu_uuid'] for x in lanes];sv=service['gpu_uuids']
        sets=[cores(x['cpu_topology']) for x in lanes]+[cores(service['cpu_topology'])]
        valid=len(set(devices))==4 and len(set(sv))==2 and not set(devices)&set(sv) and all(len(x)==4 for x in sets[:4]) and len(sets[-1])==8 and all(not sets[i]&sets[j] for i in range(5) for j in range(i))
        identities.append(dict(block=b,lanes=devices,service=sv,valid=valid))
        for lane in range(4):
            a,c=(read(root/f'episode-{b*8+lane*2+k}/cpu-partition.json') for k in (0,1))
            ac,cc=cores(a['worker_topology']),cores(c['worker_topology'])
            cpu.append(len(ac)==len(cc)==2 and not ac&cc and ac|cc==cores(a['parent_topology'])==cores(c['parent_topology']))
    cleanup=read(root/'block-0/service-cleanup.json')
    structure=all(budgets) and all(cpu) and closed['error'] is None and cleanup['gpu_clean'] and all(r['started'] and r['complete'] and r['cleanup'] for r in rows) and all(i['valid'] and i['lanes']==identities[0]['lanes'] and set(i['service'])==set(identities[0]['service']) for i in identities)
    mechanism=all(policies[b]['feedback_waits']>0 and policies[b]['completed_nonwarm_parent']>0 for b in (2,3))
    result.update(assigned=48,source_commit=p['source_commit'],plan_sha256=sha(root/'plan.json'),readout_sha256=sha(__file__),
                  scores_recomputed=recomputed,policies=policies,structural_gate=bool(structure),mechanism_gate=mechanism,
                  exploratory_gate=bool(structure and mechanism and result['quality_gate']),gpu_seconds=gpu_seconds,gpu_hours=gpu_seconds/3600,
                  cpu_pairs_passed=sum(cpu),no_automatic_expansion=True,
                  by_arm={a:{t:dict(median=statistics.median([r['score'] for r in rows if (r['arm'],r['task'])==(a,t)]),sample_sd=statistics.stdev([r['score'] for r in rows if (r['arm'],r['task'])==(a,t)])) for t in TASKS} for a in ARMS},
                  limitation=p['limitation'])
    output=Path(output);output.mkdir()
    write(output/'summary.json',result);write(output/'runs.json',rows);write(output/'identity.json',identities)
    with (output/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(result,allow_nan=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('output');ap.add_argument('--gpu-seconds',type=int,required=True)
    a=ap.parse_args();analyze(a.root,a.output,a.gpu_seconds)
