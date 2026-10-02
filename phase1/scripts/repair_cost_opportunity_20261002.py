"""Read-only old-trace cost decomposition; no efficacy or savings simulation."""
import csv,hashlib,json,os,re,statistics,time
from pathlib import Path
B=Path('/research/d7/spc/yzyang4')
OUT=B/'repair-cost-opportunity-20261002-v1'
ROOTS={
 'task-feedback-real-20261001-v6':'15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403',
 'task-feedback-upper-20261002-v1':'9fe231e1b9e2da8cb51fadb7ff9844b074c10e8e3dc64d1d1f3be170fb0703a0',
 'task-feedback-local-edit-20261002-v1':'7bd84ff0e867043b2787d5c07af867eff50370f4e7b6bafa811ef215196c4139'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def save(p,obj):
    with p.open('x') as f:json.dump(obj,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def stats(v):return dict(n=len(v),median=statistics.median(v) if v else None,sample_variance=statistics.variance(v) if len(v)>1 else None,total=sum(v))

def main():
    os.umask(0o077);start=time.monotonic();OUT.mkdir()
    save(OUT/'plan.json',dict(role='HISTORICAL_COMPONENT_COST_DIAGNOSIS_NOT_E2E_SAVINGS',source_sha256=sha(Path(__file__)),
        source_commit='79cf7c6c02afc261e600cc1f88093d4f6ffb2bae',roots=ROOTS,selection='all48 original scheduled episodes; automatic ABC plus upper A/B primary',
        metric='component seconds only; generation completion plus returned followup execution; initial execution separate',
        bound='An imaginary perfect post-generation invalid-reject gate can remove at most recorded invalid followup execution from this fixed returned stream. No claims about regenerated trajectories.',
        censoring='missing generation/result receipts explicitly counted; bounds conditional on recorded subset, not total true saving',
        limitations='Generation overlaps task workers; GPU rates and idle allocation differ. Sum is not elapsed walltime, GPU hours or realizable savings. New diagnostics not timed.',gpu=0,api_calls=0,fits=0))
    rows=[];bindings={}
    cred=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
    for name,h in ROOTS.items():
        root=B/name;assert sha(root/'plan.json')==h
        plan=read(root/'plan.json')
        for entry in plan['schedule']:
            ep=root/f'episode-{entry["index"]}'
            rec=dict(batch=name,index=entry['index'],task=entry['task'],arm=entry['arm'],seed=entry['seed'],
                automatic=(name.endswith('20261001-v6') or ('upper' in name and entry['arm'] in ('A','B'))),
                returned_followups=0,valid_followups=0,invalid_followups=0,generation_completed=0,generation_unfinished=0,started_no_result=0,
                generation_seconds=0.,initial_execution_seconds=0.,valid_execution_seconds=0.,invalid_execution_seconds=0.)
            for action in sorted(ep.glob('action-*'),key=lambda p:int(p.name.split('-')[-1])):
                step=int(action.name.split('-')[-1]);gp=action/'generation.private.json';rp=action/'result.json'
                if gp.exists():
                    raw=gp.read_bytes();assert not cred.search(raw),'credential shape in private response; no echo'
                    obj=json.loads(raw);duration=float(obj['generation_seconds']);assert duration>=0
                    rec['generation_completed']+=1;rec['generation_seconds']+=duration;bindings[str(gp)]=sha(gp)
                elif (action/'generation_failed.json').exists():rec['generation_unfinished']+=1
                if (action/'started.json').exists() and not rp.exists():rec['started_no_result']+=1
                if not rp.exists():continue
                obj=read(rp);bindings[str(rp)]=sha(rp);duration=float(obj['exec_seconds']);assert duration>=0
                if step==0:rec['initial_execution_seconds']+=duration;continue
                rec['returned_followups']+=1; key='valid' if obj['valid'] else 'invalid';rec[key+'_followups']+=1;rec[key+'_execution_seconds']+=duration
            denom=rec['generation_seconds']+rec['valid_execution_seconds']+rec['invalid_execution_seconds']
            rec['generation_fraction_recorded']=rec['generation_seconds']/denom if denom else None
            rec['perfect_invalid_reject_fraction_recorded']=rec['invalid_execution_seconds']/denom if denom else None
            rec['max_average_gate_seconds_per_completed_generation']=rec['invalid_execution_seconds']/rec['generation_completed'] if rec['generation_completed'] else None
            rows.append(rec)
    assert len(rows)==48
    summaries={}
    for task in sorted(set(r['task'] for r in rows)):
        for subset in ('automatic','all'):
            rr=[r for r in rows if r['task']==task and (subset=='all' or r['automatic'])]
            summaries[task+':'+subset]=dict(episodes=len(rr),returned_followups=sum(r['returned_followups'] for r in rr),
                invalid_followups=sum(r['invalid_followups'] for r in rr),valid_followups=sum(r['valid_followups'] for r in rr),
                generation_completed=sum(r['generation_completed'] for r in rr),generation_unfinished=sum(r['generation_unfinished'] for r in rr),started_no_result=sum(r['started_no_result'] for r in rr),
                **{k:stats([r[k] for r in rr if r[k] is not None]) for k in ('generation_seconds','initial_execution_seconds','valid_execution_seconds','invalid_execution_seconds','generation_fraction_recorded','perfect_invalid_reject_fraction_recorded','max_average_gate_seconds_per_completed_generation')})
    with (OUT/'rows.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    save(OUT/'bindings.private.json',bindings)
    out=dict(status='DESCRIPTIVE_COMPONENT_COST_ONLY',plan_sha256=sha(OUT/'plan.json'),rows_sha256=sha(OUT/'rows.csv'),bindings_sha256=sha(OUT/'bindings.private.json'),
             summaries=summaries,elapsed_seconds=time.monotonic()-start,metric_outcomes_used=False,protected_opened=False)
    save(OUT/'summary.json',out);print(json.dumps(out,sort_keys=True))

if __name__=='__main__':main()
