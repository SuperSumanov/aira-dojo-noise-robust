"""Fixed sentiment decomposition after all 18 runs close; never fed to agents."""
import argparse,csv,hashlib,json,math,statistics,sys
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/task-feedback-upper-20261002-v1')
PLAN='9fe231e1b9e2da8cb51fadb7ff9844b074c10e8e3dc64d1d1f3be170fb0703a0'
def read(p):return json.loads(p.read_bytes())
def csvrows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def jac(a,b):
    x=set(a.lower().split());y=set(b.lower().split());return len(x&y)/len(x|y) if x|y else 0
def run():
    assert hashlib.sha256((ROOT/'plan.json').read_bytes()).hexdigest()==PLAN
    assert (ROOT/'all-closed.json').exists(), 'No intermediate outcome read'
    sys.path.insert(0,str(ROOT));from task_feedback_real_20261001 import m
    plan=m.check();m.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    schedule=[s for s in plan['schedule'] if s['task']=='tweet-sentiment-extraction'];assert len(schedule)==9
    cfg=RunConfig.load_from_json(ROOT/'configs'/f'{schedule[0]["index"]}.json');task=MLEBenchTask(cfg.task)
    public={r['textID']:r for r in csvrows(task.public_dir/'test.csv')}
    spec=task._search_only_module.SPEC[cfg.task.name]
    truth={r['textID']:r['selected_text'] for r in csvrows(m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv')}
    assert set(public)==set(truth)
    groups={g:[i for i,r in public.items() if r['sentiment']==g] for g in ('negative','neutral','positive')}
    assert sum(map(len,groups.values()))==len(public)
    neutral_copy_score=statistics.mean(jac(truth[i],public[i]['text']) for i in groups['neutral'])
    rows=[]
    for s in schedule:
        ep=ROOT/f'episode-{s["index"]}';assert (ep/'closed.json').exists()
        selected=sorted(ep.glob('action-*/selected.json'),key=lambda p:int(p.parent.name.split('-')[-1]))
        initial=ep/'action-0';final=selected[-1].parent if selected else None
        def score(d):
            if d is None or not (d/'result.json').exists() or not read(d/'result.json')['valid']:return None
            pred={r['textID']:r['selected_text'] for r in csvrows(d/'submission.private.csv')};assert set(pred)==set(public)
            out={g:statistics.mean(jac(truth[i],pred[i]) for i in ids) for g,ids in groups.items()}
            aggregate=sum(out[g]*len(groups[g]) for g in groups)/len(public)
            assert math.isclose(aggregate,read(d/'result.json')['metric'],abs_tol=1e-12)
            out['aggregate']=aggregate
            out['neutral_exact_text_rows']=sum(pred[i]==public[i]['text'] for i in groups['neutral'])
            out['neutral_exact_wordset_rows']=sum(set(pred[i].lower().split())==set(public[i]['text'].lower().split()) for i in groups['neutral'])
            out['neutral_rule_aggregate_direct']=statistics.mean(jac(truth[i],public[i]['text'] if public[i]['sentiment']=='neutral' else pred[i]) for i in public)
            return out
        before,after=score(initial),score(final)
        # Same fixed public-data rule as the completed old-prediction control.
        # Chosen before viewing this pilot's outcomes; uses each actual initial
        # prediction, not a different replay's score. Not a new randomized arm.
        initial_rule_reference=(neutral_copy_score*len(groups['neutral'])+sum(before[g]*len(groups[g]) for g in ('negative','positive')))/len(public) if before else None
        if before:assert math.isclose(initial_rule_reference,before['neutral_rule_aggregate_direct'],abs_tol=1e-12)
        delta={g:after[g]-before[g] for g in groups} if before and after else None
        contribution={g:delta[g]*len(groups[g])/len(public) for g in groups} if delta else None
        if contribution:assert math.isclose(sum(contribution.values()),after['aggregate']-before['aggregate'],abs_tol=1e-12)
        rows.append({**s,'finish_status':read(ep/'finished.json')['status'] if (ep/'finished.json').exists() else 'missing',
                     'selected_step':int(final.name.split('-')[-1]) if final else None,
                     'initial':before,'selected':after,'group_delta':delta,'weighted_contribution_to_gain':contribution,
                     'own_initial_neutral_only_reference':initial_rule_reference,
                     'selected_minus_own_initial_reference':after['aggregate']-initial_rule_reference if after and initial_rule_reference is not None else None})
    return {'scope':'fixed three public sentiment strata, descriptive mechanism only; not an adaptive subgroup success claim or a replacement endpoint',
            'plan_sha256':PLAN,'public_group_counts':{g:len(v) for g,v in groups.items()},'planned_tweet_trajectories':9,
            'reference_scope':'same already-fixed neutral rule on each initial prediction; descriptive no-call reference, not fourth arm or final test',
            'rows':rows}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();result=run()
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
    print(json.dumps(result,sort_keys=True))
