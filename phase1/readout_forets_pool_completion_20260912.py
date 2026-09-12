"""Whole-matrix, independent frozen-rank mechanism readout; no execution or API."""
import argparse
import csv
import datetime as dt
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import sqlite3
import statistics
import subprocess
import sys

BASE=Path('/research/d7/spc/yzyang4')
PARENT=BASE/'forets-wallclock-20260912-cxb9p0og'
ALLOWED={'valid','program_error','program_timeout','missing_submission','invalid_submission'}
TERMINAL={'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'}

def sha(b):return hashlib.sha256(b).hexdigest()
def rank(response,order):
    if response.get('model')!='qwen/qwen3-coder-plus' or str(response.get('provider','')).lower()!='alibaba':raise ValueError('rank route')
    choices=response['choices']
    if len(choices)!=1 or choices[0]['finish_reason']!='stop':raise ValueError('rank incomplete')
    answer=json.loads(choices[0]['message']['content'])
    if set(answer)!={'ranking'}:raise ValueError('rank object')
    r=answer['ranking']
    if any(type(i) is not int for i in r) or sorted(r)!=list(range(len(order))):raise ValueError('rank permutation')
    return [order[i] for i in r]

def finite_pool(rows,ranks):
    if len(rows)!=4 or [r['slot'] for r in rows]!=[0,1,2,3]:raise ValueError('complete slot accounting')
    if len(ranks)!=2 or any(sorted(r)!=[0,1,2,3] for r in ranks):raise ValueError('two four-way ranks')
    for r in rows:
        if r['valid'] not in (True,False,None):raise ValueError('valid tri-state')
        if r['valid'] is True:
            if type(r['score']) not in (float,int) or not math.isfinite(r['score']):raise ValueError('finite valid score')
        elif r['score'] is not None:raise ValueError('no invalid/unknown score imputation')
    borda=[(8-ranks[0].index(i)-ranks[1].index(i))/2 for i in range(4)]
    top=sorted(range(4),key=lambda i:(-borda[i],i))[:2]
    policies={'uniform4':list(range(4)),'frozen_borda_top2':top,'first_order_top2':ranks[0][:2],'reverse_order_top2':ranks[1][:2]}
    missing=[i for i,r in enumerate(rows) if r['valid'] is None]
    result={}
    for name,slots in policies.items():
        v=[rows[i]['score'] for i in slots if rows[i]['valid'] is True]
        unknown=sum(rows[i]['valid'] is None for i in slots)
        result[name]=dict(slots=slots,known_valid=len(v),unknown=unknown,total=len(slots),
            validity_probability_bounds=[len(v)/len(slots),(len(v)+unknown)/len(slots)],
            conditional_mean_score=sum(v)/len(v) if v and unknown==0 else None,
            conditional_median_score=statistics.median(v) if v and unknown==0 else None,
            conditional_program_sample_std=statistics.stdev(v) if len(v)>1 and unknown==0 else None)
    possibilities=[]
    for bits in itertools.product((0,1),repeat=len(missing)):
        values=[int(r['valid']) if r['valid'] is not None else None for r in rows]
        for i,z in zip(missing,bits):values[i]=z
        possibilities.append(sum(values[i] for i in top)/2-sum(values)/4)
    return dict(full_outcome_coverage=not missing,unknown_slots=missing,policies=result,
        top2_order_invariant=set(ranks[0][:2])==set(ranks[1][:2]),
        validity_gain_bounds=[min(possibilities),max(possibilities)],
        sample_std_role='across these candidate programs, not independent search seeds')

def match_archive(metric,archives):
    matches=[]
    for path,report in archives:
        converted={k:float(v) if isinstance(v,(bool,int,float)) else v for k,v in report.items()}
        extras=set(metric)-set(converted)
        if set(converted)-set(metric):continue
        if extras and (extras!={'validity_feedback'} or metric['validity_feedback']!='Submission is valid.' or not report['valid_submission']):continue
        if all(metric[k]==v for k,v in converted.items()):matches.append((path,report))
    if len(matches)!=1:raise ValueError('first-code archive missing/ambiguous; never join by score alone')
    return matches[0]

def verify(root):
    root=root.resolve(strict=True)
    if root.parent!=BASE or not root.name.startswith('forets-pool-completion-20260912-'):raise ValueError('scope')
    if (root/'pool-completion-summary.json').exists():raise ValueError('already read out')
    sys.path.insert(0,str(root));import forets_pool_completion_20260912 as worker
    root,p=worker.checked(root);worker.source_check();launch=json.loads((root/'launch.json').read_bytes())
    if sha((root/'prepared.json').read_bytes())!=launch['prepared_sha256']:raise ValueError('plan drift')
    env={**os.environ,'SLURM_CONF':'/opt1/slurm/gpu-slurm.conf'}
    acct=subprocess.check_output(['sacct','-X','-j',launch['job'],'-nP','-o','JobIDRaw,State,ElapsedRaw,NodeList,AllocTRES%128'],env=env,text=True,timeout=25).strip().split('|')
    if len(acct)!=5 or acct[0]!=launch['job'] or acct[1].split()[0].rstrip('+') not in TERMINAL or acct[3]!='gpu28':raise ValueError('not closed')
    tres=dict(x.split('=',1) for x in acct[4].split(',') if '=' in x)
    if tres.get('gres/gpu')!='1' or tres.get('cpu')!='6':raise ValueError('hardware')
    done=json.loads((root/'execution-finished.json').read_bytes())
    if done['planned']!=12 or done['completed']!=len(list(root.glob('result-*.json'))):raise ValueError('attempt coverage')
    evidence={}
    def read(path,base):
        raw=worker.safe_bytes(path,base);evidence[str(path)]=sha(raw);return json.loads(raw)
    for name,h in p['parent_evidence'].items():
        if sha((PARENT/name).read_bytes())!=h:raise ValueError('parent mutation')
    if sha((PARENT/'wallclock-summary.json').read_bytes())!=p['parent_summary_sha256']:raise ValueError('parent closure drift')
    from readout_forets_generation_capacity_20260912 import numerical
    import pandas as pd
    from mlebench.registry import registry
    registry=registry.set_data_dir(BASE/'mle-bench-data');truth={};proofs=[];uuids=set()
    def numeric(task,submission,score,submission_hash):
        if sha(worker.safe_bytes(submission,BASE))!=submission_hash:raise ValueError('submission mutation')
        if task not in truth:truth[task]=pd.read_csv(registry.get_competition(task).answers)
        value=numerical(task,pd.read_csv(submission),truth[task])
        if round(value,5)!=score:raise ValueError('independent score disagreement')
        proofs.append(dict(submission_sha256=submission_hash,task=task,official_score=score,independent_score=value))
    by_pool={x['parent_run_id']:[] for x in p['pools']};attempt_rows=[]
    for item in p['rows']:
        i=item['index'];path=root/f'result-{i}.json'
        row=dict(parent_run_id=item['parent_run_id'],task=item['task'],seed=item['seed'],slot=item['parent_slot'],
                 code_sha256=item['code_sha256'],origin='new_unattempted_code',valid=None,score=None,status='not_attempted_after_stop')
        if path.exists():
            r=read(path,root)
            if (r['index'],r['code_sha256'],r['task'],r['original_search_seed'],r['source_tree'],r['job'])!=(i,item['code_sha256'],item['task'],item['seed'],p['source_tree'],launch['job']):raise ValueError('result binding')
            row['status']=r['status']
            if r['status'] in ALLOWED:
                if r['valid']!=(r['status']=='valid'):raise ValueError('status/valid disagreement')
                row.update(valid=r['valid'],score=r['score'])
                binding=read(root/f'identity-{i}.native-binding.json',root)
                if binding['native_identity']['job']!=launch['job'] or not binding['namespace']['exact_device_namespace']:raise ValueError('GPU namespace')
                uuids.add(binding['native_identity']['selected_uuid'])
            elif r['status']!='infrastructure_error':raise ValueError('unclassified status')
            if row['valid']:
                report=read(root/f'grade-{i}/grading_report.json',root)
                if report['valid_submission'] is not True or report['score']!=row['score']:raise ValueError('grader binding')
                numeric(item['task'],root/f'work-{i}/submission.csv',r['score'],r['submission_sha256'])
            row['execution_seconds']=r['execution_seconds'];row['wall_seconds']=r['wall_seconds']
        by_pool[item['parent_run_id']].append(row);attempt_rows.append(row)
    if len(uuids)>1:raise ValueError('different GPU within new execution')
    pool_results=[]
    for pool in p['pools']:
        rid=pool['parent_run_id'];cfg=read(PARENT/'configs'/(rid+'.json'),PARENT);cp=Path(cfg['solver']['checkpoint_path'])
        d,_=worker.snap(cp/'forets-candidates-private/batch-1.sqlite');slot=pool['previously_attempted_slots'][0]
        orig=[c for c in d['task_calls'] if c['intent']['role']=='candidate']
        if len(orig)!=1 or orig[0]['slot']!=slot or orig[0]['intent']['code_sha256']!=pool['code_sha256'][slot]:raise ValueError('original first-call binding')
        original=dict(parent_run_id=rid,task=pool['task'],seed=pool['seed'],slot=slot,code_sha256=pool['code_sha256'][slot],
            origin='original_first_call_never_rerun',valid=None,score=None,status='original_infrastructure_unknown')
        if orig[0]['state']=='returned':
            nodes=[json.loads(line) for line in worker.safe_bytes(cp/'journal.jsonl',PARENT).decode().splitlines() if line.strip()]
            nodes=[n for n in nodes if sha(n.get('code','').encode())==original['code_sha256'] and n['id']==d['candidates'][slot]['node']['id']]
            if len(nodes)!=1:raise ValueError('original node missing/ambiguous')
            node=nodes[0];meta=orig[0]['execution_metadata']
            if node['exit_code']!=meta['exit_code_reported']:raise ValueError('journal execution mismatch')
            original.update(valid=False,status='original_program_invalid')
            if node['exit_code']==0 and node.get('metric_info',{}).get('valid_submission')==1:
                archives=[]
                for ad in sorted((Path(cfg['task']['results_output_dir'])/'submission-escrow').iterdir()):
                    complete=read(ad/'complete.json',PARENT);report=read(ad/'report.json',PARENT)
                    if sha((ad/'report.json').read_bytes())!=complete['report_sha256'] or sha((ad/'submission.csv').read_bytes())!=complete['submission_sha256']:raise ValueError('archive drift')
                    archives.append((ad,report))
                ad,report=match_archive(node['metric_info'],archives)
                complete=read(ad/'complete.json',PARENT)
                numeric(pool['task'],ad/'submission.csv',report['score'],complete['submission_sha256'])
                original.update(valid=True,score=report['score'],status='original_valid')
        elif orig[0]['state']!='raised' or orig[0]['error_type']!='KernelReadinessError':raise ValueError('unexpected original incomplete call')
        rows=sorted(by_pool[rid]+[original],key=lambda r:r['slot'])
        rd=cp/'forets-contextual-judge-private/batch-1';ranks=[]
        for j,order in enumerate(([0,1,2,3],[3,2,1,0])):
            response_raw=worker.safe_bytes(rd/f'response-{j}.json',PARENT)
            saved=read(rd/f'rank-{j}.json',PARENT)
            if sha(response_raw)!=saved['response_sha256']:raise ValueError('rank response digest')
            ranking=rank(json.loads(response_raw),order)
            if saved['original_slot_order']!=ranking:raise ValueError('rank permutation receipt')
            request=read(rd/f'request-{j}.json',PARENT);shown=json.loads(request['messages'][1]['content'])['candidates']
            if shown!=[dict(displayed_index=i,code=d['candidates'][s]['node']['code']) for i,s in enumerate(order)]:raise ValueError('original full rank input')
            ranks.append(ranking)
        scores=[(8-ranks[0].index(i)-ranks[1].index(i))/2 for i in range(4)]
        if ranks!=pool['rankings'] or scores!=pool['borda'] or scores!=[c['score'] for c in d['candidates']]:raise ValueError('frozen actual rank differs')
        pool_results.append(dict(parent_run_id=rid,task=pool['task'],seed=pool['seed'],rows=rows,**finite_pool(rows,ranks)))
    result=dict(job=launch['job'],utc=dt.datetime.now(dt.timezone.utc).isoformat(),role='posthoc_frozen_rank_development_completion_not_e2e',
        prepared_sha256=launch['prepared_sha256'],controller_commit=p['commit'],source_tree=p['source_tree'],
        execution_complete=done['complete'],attempted=done['completed'],planned=12,pools=pool_results,independent_numerical_regrades=len(proofs),
        proofs=proofs,evidence_sha256=evidence,allocation_seconds=int(acct[2]),allocation_gpu_hours=int(acct[2])/3600,
        same_gpu_within_new_attempts=len(uuids)==1,old_new_same_physical_gpu_claimed=False,api_calls=0,protected_cohort_read=False,
        reader_sha256=sha(Path(__file__).read_bytes()),numerical_reader_sha256=sha(Path(__file__).with_name('readout_forets_generation_capacity_20260912.py').read_bytes()),
        limitation='Ranks frozen before original/new execution, but this completion selected after some parent outcomes were known. Four finite development pools, unknown original infrastructure result preserved; not equal-budget end-to-end or fresh confirmatory evidence.')
    with (root/'pool-completion-summary.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    allrows=[r for p in pool_results for r in p['rows']]
    with (root/'pool-completion-runs.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=sorted(set().union(*(r.keys() for r in allrows))));writer.writeheader();writer.writerows(allrows)
    print(json.dumps({k:v for k,v in result.items() if k not in ('proofs','evidence_sha256')},allow_nan=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);a=parser.parse_args();verify(a.root)
