"""Apply the already-fixed neutral rule to ALL six old Tweet trajectory endpoints.

Four historically valid endpoints and two missing endpoints are retained. No
rescoring-based choice of source programs, fitting, new generation or GPU jobs.
"""
import hashlib,importlib.util,json,os,statistics,time
from pathlib import Path
BASE=Path('/research/d7/spc/yzyang4')
OLD=BASE/'task-feedback-real-20261001-v6'
OUT=BASE/'task-feedback-neutral-replays-20261002-v1'
MODULE=BASE/'task-feedback-neutral-control-20261002-v1/task_feedback_neutral_control_20261002.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def run(module_path):
    os.umask(0o077);began=time.monotonic();OUT.mkdir(exist_ok=False)
    assert sha(OLD/'plan.json')=='15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403'
    assert sha(module_path)=='b260df99b612105f7f6c1d35e200701a618d187b182b39fed3e096d491bab5fa'
    specs=[]
    for s in read(OLD/'plan.json')['schedule']:
        if s['task']!='tweet-sentiment-extraction':continue
        ep=OLD/f'episode-{s["index"]}';assert (ep/'closed.json').exists()
        selected=sorted(ep.glob('action-*/selected.json'),key=lambda p:int(p.parent.name.split('-')[-1]))
        source=selected[-1].parent/'submission.private.csv' if selected else None
        specs.append({**s,'source':str(source) if source else None,'source_sha256':sha(source) if source else None})
    assert len(specs)==6
    plan={'sources':specs,'rule':'same already-fixed neutral-only full-text rule; no new thresholds or exclusions',
          'script_sha256':sha(Path(__file__)),'rule_module_sha256':sha(module_path),
          'new_gpu':0,'model_fits':0,'agent_calls':0,'not_sent_to_running_agents':True,
          'selection':'old final selected submission fixed under original scores, not best after applying rule'}
    (OUT/'plan.json').write_text(json.dumps(plan,sort_keys=True,indent=2)+'\n')
    spec=importlib.util.spec_from_file_location('neutral_rule_reuse',module_path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    rows=[]
    for s in specs:
        r={**s,'valid_source':s['source'] is not None,'baseline':None,'neutral_only':None,'difference':None,'modified_rows':None}
        if s['source']:
            m.SOURCE=Path(s['source']);m.OUT=OUT/f'episode-{s["index"]}';m.run()
            receipt=read(m.OUT/'receipt.json')
            r.update({k:receipt[k] for k in ('baseline','neutral_only','difference','modified_rows')})
            r['independent_match']=receipt['baseline']==receipt['independent_original'] and receipt['neutral_only']==receipt['independent_modified']
        rows.append(r)
    delta=[r['difference'] for r in rows if r['difference'] is not None]
    out={'rows':rows,'plan_sha256':sha(OUT/'plan.json'),'full_denominator':6,'valid_sources':len(delta),
         'median_difference':statistics.median(delta),'sample_variance_difference':statistics.variance(delta),
         'elapsed_seconds':time.monotonic()-began,
         'scope':'posthoc one-task old-program robustness, shared development labels; no new independent trial or generalization claim'}
    (OUT/'summary.json').write_text(json.dumps(out,sort_keys=True,indent=2)+'\n');print(json.dumps(out,sort_keys=True))
if __name__=='__main__':
    # The rule source is staged read-only; it need not reside in its output root.
    run(Path('/tmp/task-feedback-stage-20261001/task_feedback_neutral_control_20261002.py'))
