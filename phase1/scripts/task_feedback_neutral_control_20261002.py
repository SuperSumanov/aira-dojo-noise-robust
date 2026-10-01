"""One frozen postprocessing intervention on prior A predictions; no agent call.

Fixed after public training evidence and before intervention D_search scores.
Do not send this output to the running arms; not an extra randomized arm or E2E.
"""
import csv,hashlib,json,math,os,statistics,sys,time
from pathlib import Path
OLD=Path('/research/d7/spc/yzyang4/task-feedback-real-20261001-v6')
OUT=Path('/research/d7/spc/yzyang4/task-feedback-neutral-control-20261002-v1')
SOURCE=OLD/'episode-11/action-1/submission.private.csv'
PUBLIC=Path('/research/d7/spc/yzyang4/tweet-search-only-20260927-a4d1/public')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def readrows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def run():
    os.umask(0o077);OUT.mkdir(exist_ok=False);began=time.monotonic()
    plan={'rule':'replace only public sentiment == neutral with full public input text; all other source predictions byte-value unchanged','source':str(SOURCE),'source_sha256':sha(SOURCE),'public_input_sha256':sha(PUBLIC/'test.csv'),'script_sha256':sha(Path(__file__)),'agent_calls':0,'model_fits':0,'new_gpu':0,'not_sent_to_running_agents':True,'not_equal_budget_arm':True}
    # Persist the rule and source identities BEFORE computing its scores.
    (OUT/'plan.json').write_text(json.dumps(plan,sort_keys=True,indent=2)+'\n')
    rows=readrows(SOURCE);data=readrows(PUBLIC/'test.csv');by={r['textID']:r for r in data}
    assert len(by)==len(data)==len(rows) and {r['textID'] for r in rows}==set(by)
    amended=[];changed=0;neutral=0
    for r in rows:
        z=dict(r);d=by[r['textID']]
        if d['sentiment']=='neutral':
            neutral+=1;z['selected_text']=d['text'];changed+=z['selected_text']!=r['selected_text']
        else:assert z==r
        amended.append(z)
    dest=OUT/'amended.private.csv'
    with dest.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(amended)
    sys.path.insert(0,str(OLD));import task_feedback_real_20261001 as engine
    engine.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    cfg=RunConfig.load_from_json(OLD/'configs/11.json');task=MLEBenchTask(cfg.task)
    base=task._search_only_score(cfg.task.name,SOURCE);new=task._search_only_score(cfg.task.name,dest)
    assert base['split']==new['split']=='D_search_development_only'
    spec=task._search_only_module.SPEC[cfg.task.name]
    truth=readrows(engine.B/spec.get('source',spec.get('view'))/'private/dsearch.csv')
    pred0={r['textID']:r['selected_text'] for r in rows};pred1={r['textID']:r['selected_text'] for r in amended}
    assert {r['textID'] for r in truth}==set(by)
    def jac(a,b):
        x=set(a.lower().split());y=set(b.lower().split());return len(x&y)/len(x|y) if x|y else 0
    s0=[jac(r['selected_text'],pred0[r['textID']]) for r in truth];s1=[jac(r['selected_text'],pred1[r['textID']]) for r in truth]
    v0=statistics.mean(s0);v1=statistics.mean(s1)
    assert math.isclose(v0,base['mean_word_jaccard'],abs_tol=1e-12) and math.isclose(v1,new['mean_word_jaccard'],abs_tol=1e-12)
    assert sha(SOURCE)==plan['source_sha256'] and sha(PUBLIC/'test.csv')==plan['public_input_sha256']
    result={'plan':plan,'source_rows':len(rows),'neutral_rows':neutral,'modified_rows':changed,'baseline':base['mean_word_jaccard'],'neutral_only':new['mean_word_jaccard'],'difference':v1-v0,'independent_original':v0,'independent_modified':v1,'other_sentiments_unchanged':True,'prediction_sha256':sha(dest),'elapsed_seconds':time.monotonic()-began,'scope':'posthoc prior-prediction paired development control; not a new trained model, full agent run, or independent final evaluation'}
    (OUT/'receipt.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':run()
