"""One post-hoc, zero-fit diagnostic reference; never a new pilot arm."""
import csv,datetime,hashlib,json,sys,time
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/task-feedback-real-20261001-v6')
O=Path('/tmp/task-feedback-tweet-copy-reference-20261001')
sys.path.insert(0,str(R))
import task_feedback_real_20261001 as engine
engine.check();engine.setup()
from dojo.config_dataclasses.run import RunConfig
from dojo.tasks.mlebench.task import MLEBenchTask
from task_feedback_facts_20261001 import csvrows,diagnostics
cfg=RunConfig.load_from_json(R/'configs/2.json');assert cfg.task.name=='tweet-sentiment-extraction'
task=MLEBenchTask(cfg.task)
# The rule is fixed before inspecting this reference's score; no fit or selection.
public=csvrows(task.public_dir/'test.csv')
assert all(isinstance(r['text'],str) and r['text'].strip() for r in public)
O.mkdir(mode=0o700,exist_ok=False);prediction=O/'prediction.private.csv'
began=time.monotonic()
with prediction.open('x',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=['textID','selected_text']);w.writeheader()
    w.writerows({'textID':r['textID'],'selected_text':r['text']} for r in public)
receipt=task._search_only_score(cfg.task.name,prediction)
spec=task._search_only_module.SPEC[cfg.task.name]
labels=engine.B/spec.get('source',spec.get('view'))/'private/dsearch.csv'
independent=diagnostics(cfg.task.name,task.public_dir,labels,prediction,receipt)
out={'status':'PASS_NATIVE_AND_INDEPENDENT','rule':'copy entire supplied tweet text, unchanged, for every row','task':cfg.task.name,'n':len(public),'development_metric':receipt['mean_word_jaccard'],'independent_metric':independent['overall'],'elapsed_seconds':time.monotonic()-began,'gpu':0,'api_calls':0,'model_fit':False,'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'pilot_plan_sha256':engine.sha(R/'plan.json'),'public_input_sha256':engine.sha(task.public_dir/'test.csv'),'submission_sha256':engine.sha(prediction),'scope':'Post-hoc diagnostic floor, chosen after observing the first-start repair result. Not a preregistered A/B/C arm, not fed to any running agent, no D_val/test/protected-cohort access. Does not match continuation compute cost.'}
with (O/'receipt.json').open('x',encoding='utf-8') as f:json.dump(out,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
print(json.dumps(out,sort_keys=True))
