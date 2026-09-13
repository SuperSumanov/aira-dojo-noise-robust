"""Fixed four-pool immediate-program readout. Never credit debug descendants."""
import argparse
import csv
import datetime as dt
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import sys
BASE=Path('/research/d7/spc/yzyang4')
PARENT=BASE/'forets-wallclock-20260912-y_p2tlmi'
ALLOWED={'valid','program_error','program_timeout','missing_submission','invalid_submission'}
def sha(b):return hashlib.sha256(b).hexdigest()

def compare(rows,ranking):
    if [r['slot'] for r in rows]!=list(range(4)) or sorted(ranking)!=list(range(4)):raise ValueError('four slots/rank')
    for r in rows:
        if r['valid'] is not None and type(r['valid']) is not bool:raise ValueError('tri-state')
        if r['valid'] is True:
            if type(r['score']) not in (float,int) or not math.isfinite(r['score']):raise ValueError('finite score')
        elif r['score'] is not None:raise ValueError('no imputation')
    missing=[i for i,r in enumerate(rows) if r['valid'] is None];top=ranking[:2]
    pairs=list(itertools.combinations(range(4),2));values=[]
    for bits in itertools.product((False,True),repeat=len(missing)):
        v=[r['valid'] for r in rows]
        for i,b in zip(missing,bits):v[i]=b
        selected=float(any(v[i] for i in top));uniform=sum(any(v[i] for i in pair) for pair in pairs)/len(pairs)
        values.append((selected,uniform,selected-uniform))
    return dict(top2=top,unknown_slots=missing,complete_direct_outcomes=not missing,
        top2_any_valid_bounds=[min(v[0] for v in values),max(v[0] for v in values)],
        uniform_two_any_valid_bounds=[min(v[1] for v in values),max(v[1] for v in values)],
        any_valid_gain_bounds=[min(v[2] for v in values),max(v[2] for v in values)],
        contract='Two direct executions, no debug or 600-second scheduling model. Not end-to-end search utility.')

def run(root):
    root=root.resolve(strict=True)
    sys.path.insert(0,str(root));import forets_pool_completion_20260912 as worker
    root,p=worker.checked(root);worker.source_check()
    plan=json.loads((root/'completion-readout-plan.json').read_bytes())
    if plan['readers']!={n:sha(Path(__file__).with_name(n).read_bytes()) for n in plan['readers']}:
        raise ValueError('frozen reader drift')
    launch=json.loads((root/'launch.json').read_bytes())
    if sha((root/'prepared.json').read_bytes())!=launch['prepared_sha256']:raise ValueError('plan drift')
    env={**os.environ,'SLURM_CONF':'/opt1/slurm/gpu-slurm.conf'}
    acct=subprocess.check_output(['sacct','-X','-j',launch['job'],'-nP','-o','JobIDRaw,State,ElapsedRaw,NodeList,AllocTRES%128'],env=env,text=True,timeout=25).strip().split('|')
    if len(acct)!=5 or acct[0]!=launch['job'] or acct[1].split()[0].rstrip('+') not in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'} or acct[3]!='gpu28':raise ValueError('not closed')
    tres=dict(x.split('=',1) for x in acct[4].split(',') if '=' in x)
    if tres.get('gres/gpu')!='1' or tres.get('cpu')!='6':raise ValueError('allocation')
    for name,h in p['parent_evidence'].items():
        if sha((PARENT/name).read_bytes())!=h:raise ValueError('parent drift')
    done=json.loads((root/'execution-finished.json').read_bytes())
    if done['planned']!=8 or done['completed']!=len(list(root.glob('result-*.json'))):raise ValueError('coverage')
    from readout_forets_generation_capacity_20260912 import numerical
    from readout_forets_pool_completion_20260912 import rank,match_archive
    from mlebench.registry import registry
    import pandas as pd
    registry=registry.set_data_dir(BASE/'mle-bench-data');truth={};proofs=[];evidence={};uuids=set()
    def read(path,base):
        raw=worker.safe_bytes(path,base);evidence[str(path)]=sha(raw);return json.loads(raw)
    def numeric(task,path,score,digest):
        if sha(worker.safe_bytes(path,BASE))!=digest:raise ValueError('submission hash')
        if task not in truth:truth[task]=pd.read_csv(registry.get_competition(task).answers)
        v=numerical(task,pd.read_csv(path),truth[task])
        if round(v,5)!=score:raise ValueError('numeric grade')
        proofs.append(dict(task=task,submission_sha256=digest,score=score,independent_score=v))
    by_pool={p['parent_run_id']:[] for p in p['pools']}
    for item in p['rows']:
        i=item['index'];path=root/f'result-{i}.json'
        row=dict(parent_run_id=item['parent_run_id'],task=item['task'],seed=item['seed'],slot=item['parent_slot'],code_sha256=item['code_sha256'],
            origin='new_unattempted_original',valid=None,score=None,status='unattempted_after_stop')
        if path.exists():
            r=read(path,root)
            if (r['index'],r['code_sha256'],r['task'],r['original_search_seed'],r['source_tree'],r['job'])!=(i,item['code_sha256'],item['task'],item['seed'],p['source_tree'],launch['job']):raise ValueError('execution binding')
            row.update(status=r['status'],execution_seconds=r['execution_seconds'],wall_seconds=r['wall_seconds'])
            if r['status'] in ALLOWED:
                if r['valid']!=(r['status']=='valid'):raise ValueError('valid status')
                row.update(valid=r['valid'],score=r['score'])
                b=read(root/f'identity-{i}.native-binding.json',root)
                if b['native_identity']['job']!=launch['job'] or not b['namespace']['exact_device_namespace']:raise ValueError('device binding')
                uuids.add(b['native_identity']['selected_uuid'])
            elif r['status']!='infrastructure_error':raise ValueError('unclassified result')
            if row['valid']:
                report=read(root/f'grade-{i}/grading_report.json',root)
                if report['valid_submission'] is not True or report['score']!=r['score']:raise ValueError('grade binding')
                numeric(item['task'],root/f'work-{i}/submission.csv',r['score'],r['submission_sha256'])
        by_pool[item['parent_run_id']].append(row)
    if len(uuids)>1:raise ValueError('new hardware varied')
    results=[]
    for pool in p['pools']:
        rid=pool['parent_run_id'];cfg=read(PARENT/'configs'/(rid+'.json'),PARENT);cp=Path(cfg['solver']['checkpoint_path'])
        d,_=worker.snap(cp/'forets-candidates-private/batch-2.sqlite');originals=[]
        for slot in pool['previously_attempted_slots']:
            calls=[c for c in d['task_calls'] if c['intent']['role']=='candidate' and c['slot']==slot]
            if len(calls)!=1 or calls[0]['intent']['code_sha256']!=pool['code_sha256'][slot]:raise ValueError('original call')
            c=calls[0];row=dict(parent_run_id=rid,task=pool['task'],seed=pool['seed'],slot=slot,code_sha256=pool['code_sha256'][slot],
                origin='original_direct_call_never_rerun',valid=None,score=None,status='original_unresolved')
            if c['state']=='returned':
                meta=c['execution_metadata']
                if meta['timed_out_reported'] or meta['exit_code_reported']!=0:
                    row.update(valid=False,status='original_program_invalid')
                else:
                    path=cp/'journal.jsonl';nodes=[json.loads(x) for x in worker.safe_bytes(path,PARENT).splitlines()] if path.exists() else []
                    found=[n for n in nodes if n['id']==d['candidates'][slot]['node']['id'] and sha(n['code'].encode())==row['code_sha256']]
                    if len(found)>1:raise ValueError('ambiguous node identity')
                    if found:
                        node=found[0]
                        if node['exit_code']!=0:raise ValueError('execution disagreement')
                        if node.get('metric_info',{}).get('valid_submission')!=1:row.update(valid=False,status='original_submission_invalid')
                        else:
                            archives=[]
                            for ad in sorted((Path(cfg['task']['results_output_dir'])/'submission-escrow').iterdir()):
                                complete=read(ad/'complete.json',PARENT);report=read(ad/'report.json',PARENT)
                                if sha((ad/'report.json').read_bytes())!=complete['report_sha256'] or sha((ad/'submission.csv').read_bytes())!=complete['submission_sha256']:raise ValueError('archive drift')
                                archives.append((ad,report))
                            try:ad,report=match_archive(node['metric_info'],archives)
                            except ValueError:row['status']='original_archive_unresolved'
                            else:
                                complete=read(ad/'complete.json',PARENT);numeric(pool['task'],ad/'submission.csv',report['score'],complete['submission_sha256'])
                                row.update(valid=True,score=report['score'],status='original_valid')
                    else:row['status']='original_exit_zero_uncommitted_node_unknown'
            originals.append(row)
        rd=cp/'forets-contextual-judge-private/batch-2';response=worker.safe_bytes(rd/'response-0.json',PARENT);saved=read(rd/'rank-0.json',PARENT)
        if sha(response)!=saved['response_sha256']:raise ValueError('response hash')
        ranking=rank(json.loads(response),list(range(4)))
        if saved['original_slot_order']!=ranking or pool['rankings']!=[ranking]:raise ValueError('single rank')
        scores=[float(4-ranking.index(i)) for i in range(4)]
        if scores!=pool['borda'] or scores!=[c['score'] for c in d['candidates']]:raise ValueError('rank scores')
        request=read(rd/'request-0.json',PARENT);shown=json.loads(request['messages'][1]['content'])['candidates']
        if shown!=[dict(displayed_index=i,code=d['candidates'][i]['node']['code']) for i in range(4)]:raise ValueError('actual rank input')
        rows=sorted(by_pool[rid]+originals,key=lambda r:r['slot'])
        results.append(dict(parent_run_id=rid,task=pool['task'],seed=pool['seed'],rows=rows,**compare(rows,ranking)))
    result=dict(role='posthoc_direct_program_completion_not_e2e',job=launch['job'],utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        source_tree=p['source_tree'],controller_commit=p['commit'],prepared_sha256=launch['prepared_sha256'],pools=results,
        planned=8,attempted=done['completed'],execution_complete=done['complete'],allocation_seconds=int(acct[2]),allocation_gpu_hours=int(acct[2])/3600,
        proofs=proofs,evidence_sha256=evidence,api_calls=0,reader_sha256=sha(Path(__file__).read_bytes()),
        limitation='Four previously observed development pools. Direct validity ignores debug and scheduling cost; no new e2e, causal historical winner attribution or independent confirmation. Unknown original partial nodes stay unknown.')
    worker.write(root/'completion-summary.json',result)
    rows=[r for x in results for r in x['rows']]
    with (root/'completion-runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=sorted(set().union(*(r.keys() for r in rows))));w.writeheader();w.writerows(rows)
    print(json.dumps({k:v for k,v in result.items() if k not in ('proofs','evidence_sha256')}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();run(a.root)
