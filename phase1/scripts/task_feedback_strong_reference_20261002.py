"""Descriptive reference comparison; no new model, score or randomized arm."""
import hashlib,json,statistics
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]/'results'
P=BASE/'task_feedback_local_edit_20261002/complete/summary.json'
Q=BASE/'task_feedback_public_rule_20261002/summary.json'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
    x,y=read(P),read(Q)
    manual=sorted((r for r in x['rows'] if r['task']=='tweet-sentiment-extraction' and r['arm']=='F'),key=lambda r:r['seed'])
    assert len(manual)==3 and all(r['initial']==manual[0]['initial'] for r in manual)
    reference=next(r for r in y['rows'] if r['batch']=='task-feedback-real-20261001-v6' and r['index']==11)
    assert reference['baseline']==manual[0]['initial']
    base=reference['rule_score'];values=[r['selected'] for r in manual]
    composed=sorted((r for r in y['rows'] if r['arm']=='F'),key=lambda r:r['seed'])
    assert len(composed)==3 and all(a['selected']==b['baseline'] for a,b in zip(manual,composed))
    out=dict(source_sha256=[sha(P),sha(Q)],task='tweet-sentiment-extraction',same_program_generation_seeds=[r['seed'] for r in manual],
        initial=manual[0]['initial'],unchanged_initial_plus_public_rule=base,
        manual_selected_values=values,manual_median=statistics.median(values),manual_sample_variance=statistics.variance(values),
        manual_minus_reference=[v-base for v in values],manual_median_minus_reference=statistics.median(values)-base,
        manual_strictly_above_reference=sum(v>base for v in values),
        manual_plus_rule_values=[r['rule_score'] for r in composed],manual_plus_rule_median=statistics.median(r['rule_score'] for r in composed),
        scope='reference selected without these new gains but constructed after earlier same-task evidence; not new randomized arm or independent test. Zero NEW GPU postprocessing inherits nonzero initial-program cost. Same initial code and development set; three generation seeds not three tasks.')
    return out
if __name__=='__main__':print(json.dumps(run(),sort_keys=True))
