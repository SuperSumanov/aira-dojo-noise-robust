"""All-closed readout + independent scoring; never feeds results back to agents."""
import argparse,csv,hashlib,json,math,re,statistics,sys
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/task-feedback-local-edit-20261002-v1')
PLAN_SHA='7bd84ff0e867043b2787d5c07af867eff50370f4e7b6bafa811ef215196c4139'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def close(a,b):return math.isclose(a,b,abs_tol=1e-11,rel_tol=1e-11)
def stats(v):
    x=[y for y in v if y is not None]
    return dict(n=len(x),values=v,median=statistics.median(x) if x else None,sample_variance=statistics.variance(x) if len(x)>1 else None)
def run():
    if sha(ROOT/'plan.json')!=PLAN_SHA or not (ROOT/'all-closed.json').exists():raise ValueError('frozen all-closed gate')
    sys.path.insert(0,str(ROOT));from task_feedback_real_20261001 import m
    m.check();m.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.utils.code_parsing import extract_code
    legacy_path=m.B/'task-feedback-real-20261001-v6/task_feedback_facts_20261001.py'
    assert sha(legacy_path)=='b44bc3badff713fe8e595fea6b8d2d6fc9e7c453e1e412ece7b833f4af0c908b'
    legacy=m.load('local_edit_independent_metrics',legacy_path)
    plan=read(ROOT/'plan.json');job=read(ROOT/'launch.json')['job'];serv=read(ROOT/'service-native.json')
    rows=[];verified=[];assert len(plan['schedule'])==12
    for s in plan['schedule']:
        ep=ROOT/f'episode-{s["index"]}';assert (ep/'closed.json').exists()
        native=read(ep/'native.json');assert native['job']==job and not set(native['gpu_uuids'])&set(serv['gpu_uuids'])
        assert native['config_sha256']==sha(ROOT/'configs'/f'{s["index"]}.json')
        task=MLEBenchTask(RunConfig.load_from_json(ROOT/'configs'/f'{s["index"]}.json').task)
        initial=read(ROOT/'starts'/f'{s["start"]}.private.json')['code'];initial_score=None;values=[];actions=[]
        for step in range(2):
            d=ep/f'action-{step}'
            if not (d/'result.json').exists():continue
            r=read(d/'result.json');node=read(d/'node.private.json');began=read(d/'started.json')
            code_hash=hashlib.sha256(node['code'].encode()).hexdigest()
            assert code_hash==r['code_sha256']==began['code_sha256']
            if step==0:assert code_hash==plan['starts'][s['start']]['normalized_code_sha256']
            if r['execution_started']:assert read(d/'binding.json')['namespace']['exact_device_namespace']
            if r['valid']:
                sub=d/'submission.private.csv';before=sha(sub);receipt=task._search_only_score(s['task'],sub)
                assert receipt['split']=='D_search_development_only'
                metric='auc' if s['task']=='random-acts-of-pizza' else 'mean_word_jaccard'
                assert close(receipt[metric],r['metric'])
                spec=task._search_only_module.SPEC[s['task']]
                labels=m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv'
                legacy.diagnostics(s['task'],task.public_dir,labels,sub,receipt)
                assert sha(sub)==before and r['exit_code']==0 and not r['timed_out']
                values.append(r['metric'])
                if step==0:initial_score=r['metric']
            assert r['selected_metric']==(max(values) if values else None)
            verified.append(dict(index=s['index'],step=step,valid=r['valid'],result_sha256=sha(d/'result.json'),submission_sha256=sha(d/'submission.private.csv') if r['valid'] else None))
            actions.append(r)
        fmt=read(ep/'action-1/format.json') if (ep/'action-1/format.json').exists() else {}
        generation=read(ep/'action-1/generation.private.json') if (ep/'action-1/generation.private.json').exists() else {}
        if fmt.get('status')=='accepted' and (ep/'action-1/node.private.json').exists():
            # Independent plain sequential application, no imported patch applier.
            raw=generation['response']
            if s['arm']=='P':
                payload=re.findall(r'^```json[ \t]*\r?\n(.*?)^```[ \t]*$',raw,re.M|re.S);assert len(payload)==1
                edits=json.loads(payload[0]);expect=initial
                for e in edits:
                    left,matched,right=expect.partition(e['search'])
                    assert matched and e['search'] not in right
                    expect=left+e['replace']+right
            else:expect=extract_code(raw)
            actual=extract_code(read(ep/'action-1/node.private.json')['code'])
            assert actual.strip()==expect.strip()
            assert fmt['parent_sha256']==hashlib.sha256(initial.encode()).hexdigest()
        status=read(ep/'finished.json')['status'] if (ep/'finished.json').exists() else 'unknown'
        selected=max(values) if values else None
        if (ep/'completed.json').exists():assert read(ep/'completed.json')['selected_metric']==selected
        revised=next((x for x in actions if x['step']==1),{})
        usage=generation.get('usage',{})
        rows.append(dict(**s,base_commit=plan['base_commit'],plan_sha256=PLAN_SHA,status=status,initial=initial_score,
            selected=selected,gain=selected-initial_score if selected is not None and initial_score is not None else None,
            revised_valid=revised.get('valid'),revised_metric=revised.get('metric'),format_status=fmt.get('status'),
            changed_lines=fmt.get('changed_lines'),parent_lines=fmt.get('parent_lines'),edit_count=fmt.get('edit_count'),
            returned_actions=len(actions),generation_seconds=generation.get('generation_seconds'),prompt_tokens=usage.get('prompt_tokens'),
            completion_tokens=usage.get('completion_tokens'),budget_seconds=plan['run_seconds']))
    pairs=[];groups=[]
    for task in sorted({r['task'] for r in rows}):
        for seed in sorted({r['seed'] for r in rows if r['task']==task}):
            z={r['arm']:r for r in rows if r['task']==task and r['seed']==seed};f,p=z['F'],z['P']
            initial_equal=f['initial'] is not None and p['initial'] is not None and close(f['initial'],p['initial'])
            strict=initial_equal and all(x['status'] in ('completed','budget_exhausted') for x in (f,p))
            pairs.append(dict(task=task,seed=seed,initial_equal=initial_equal,strict_estimable=strict,
                saved_gain_difference=p['gain']-f['gain'] if p['gain'] is not None and f['gain'] is not None else None,
                F_gain=f['gain'],P_gain=p['gain'],F_status=f['status'],P_status=p['status']))
        for arm in 'FP':
            subset=sorted((r for r in rows if r['task']==task and r['arm']==arm),key=lambda r:r['seed'])
            groups.append(dict(task=task,arm=arm,planned=3,valid_revisions=sum(r['revised_valid'] is True for r in subset),
                gain=stats([r['gain'] for r in subset]),generation_seconds=stats([r['generation_seconds'] for r in subset]),
                changed_lines=stats([r['changed_lines'] for r in subset]),completion_tokens=stats([r['completion_tokens'] for r in subset])))
    return dict(status='PASS',plan_sha256=PLAN_SHA,job=job,planned=12,rows=rows,pairs=pairs,groups=groups,verified_actions=verified,
        valid_actions_verified=sum(r['valid'] for r in verified),scope='two curated code instances, human guidance, development only; no automatic-method/novelty/generalization claim')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();result=run();a.out.mkdir()
    (a.out/'summary.json').write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')
    for key in ('rows','pairs'):
        with (a.out/(key+'.csv')).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(result[key][0]));w.writeheader();w.writerows(result[key])
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','verified_actions')},sort_keys=True))
