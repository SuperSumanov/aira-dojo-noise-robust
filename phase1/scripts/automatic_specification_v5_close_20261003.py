"""Post-closure manual mechanism record, after code inspection; no new scoring."""
import datetime,hashlib,json,re
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-gpu3-v5')
PLAN='e533639434bc1c1cca57a301127a63eff56452119dfe78ccd332199e9f8fb2ce'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    out=R/'readout-v1';s=read(out/'summary.json')
    assert sha(R/'plan.json')==PLAN and read(out/'verification.json')['status']=='PASS'
    assert read(out/'verification.json')['summary_sha256']==sha(out/'summary.json')
    assert read(R/'closed.json')['service_closed'] and s['accounting']['state']=='COMPLETED'
    notes={
      0:('SOURCE_VALID_NOT_MEANINGFULLY_TRAINED','Generic loader treats a target-bearing CSV as training; sample submission overwrites/blocks the actual training JSON. Third attempt writes constant predictions. Claims that train.json has no features are false attribution, contradicted by later explicit JSON loading.'),
      1:('SOURCE_VALID','Word/char TFIDF plus LR C4. First attempt used numpy hstack; successful correction uses scipy sparse hstack. Known baseline, no novelty.'),
      2:('NOT_IMPLEMENTED','Repeated recovery-of-training-features plans, no post-initial code execution. Correctly notices feature mismatch but attributes the dataframe to train.json without evidence.'),
      3:('NOT_IMPLEMENTED','Repeated plans drift from a new boosting blend to LR regularization CV without new execution evidence. No post-initial code execution.'),
      4:('NOT_IMPLEMENTED','Repeats checklist-backed heuristics while assuming featureless training. No post-initial code execution.'),
      5:('IMPLEMENTED_MULTIPLE_CHANGES','Final code splits word unigram/bigram views, adds char 2-4 beside 3-5, increases max_features; same LR C4. Standard checklist family, multiple simultaneous changes and retraining, no single-change attribution.'),
      6:('NOT_IMPLEMENTED','Ordinary arm mixes PLAN with code and incurs format rejects, then repeats the incorrect featureless-training premise. No post-initial execution.'),
      7:('IMPLEMENTED_MULTIPLE_CHANGES','Step3 widens word/char ngrams, increases features and LR C. Step4 retrains two views/C values and uses fixed half-half blending, not public-CV-selected blend. Known ML changes.'),
      8:('IMPLEMENTED_WITH_EVIDENCE_CORRECTION','Step3 explicitly loads train.json and prints real featureful training shape while still implementing an unsupervised heuristic. Step4 uses that new observation to fit train-only TFIDF/scaler and LR using common non-future numeric columns. Ordinary agent corrects source premise without task-specific human hint.'),
      9:('IMPLEMENTED_MULTIPLE_CHANGES','Adds char 2-4, expands feature cap, selects LR C by five-fold CV, then retrains. TFIDF fitted before internal CV means its CV estimate is not a clean end-to-end fold estimate; external held-out scoring remains separate.'),
      10:('IMPLEMENTED_BUT_NOT_CLAIMED_SUPERVISED_RULE','Fits unused TFIDF on query features, then scores handcrafted length/keywords/activity/recency. Continues false no-training premise. Not a supervised TFIDF model or novel rule discovery; preprocessing-on-training checklist not followed.'),
      11:('ATTEMPTED_NOT_COMPLETED','Attempts five-fold LR/LightGBM blend selection on globally train-fitted TFIDF, omits planned early stopping, adds class balancing. Compares internal CV to external incumbent score from a different split. Execution fails; do not attribute a benefit or preservation guarantee.'),
      12:('NOT_IMPLEMENTED','Repeated dataset-layout hypotheses without execution, including hypothetical query-label availability; no such label acquisition was executed. No post-initial code execution.'),
      13:('NOT_IMPLEMENTED','Repeated LightGBM/half-half blend plans without new execution evidence. No post-initial code execution.')}
    records=[]
    for r in s['runs']:
        status,note=notes[r['index']]
        records.append(dict(index=r['index'],role=r['role'],task=r['task'],arm=r['arm'],seed=r['seed'],implementation=status,review=note,
            calls=r['calls_completed'],accepted_plans=r['plan_actions'],format_rejections=r['format_rejects'],new_valid_candidates=r['valid_candidates'],new_improved_candidates=r['improved_candidates']))
    b=[r for r in s['runs'] if r['arm']=='B'];assert len(b)==4 and all(r['valid_candidates']==0 and r['plan_actions']==3 for r in b)
    audit=dict(status='MANUAL_CLOSED_BATCH_AUDIT',plan_sha256=PLAN,summary_sha256=sha(out/'summary.json'),rubric_sha256=sha(R/'mechanism-freeze.json'),
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),records=records,numerical_B_gate=s['numerical_B_gate'],method_effect='B_NOT_BETTER_IN_THIS_PROTOCOL',novelty='NOT_ESTABLISHED',
        source_warning='First-valid availability does not ensure trained or strong root: Pizza source is constant. This root was included by the frozen rule, not chosen after seeing treatment outcomes.',
        protocol_warning='B/C repeat call1-only PLAN instruction on every call without explicit current-call ordinal. Actual B responses repeatedly remain PLAN including final rejected call. This supports a bounded stage-clarity correction but does not prove the wording is the only cause.',
        limitations='Same analyst code review, arm visible; model rationales contain score tendencies. Some code review overlapped aggregate readout. Not blind/independent semantic review. Developer data reused; two roots/two generation seeds, not generalization confirmation.',
        decision='Seal V5 unchanged. Permit exactly one separately frozen stage-clarity follow-up within the original cumulative8GPUh authorization. No source rescue, hidden-label hint, pooled inference or further prompt sweep.')
    with (out/'mechanism-audit.json').open('x') as f:json.dump(audit,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps(dict(status=audit['status'],records=len(records),numerical_B_gate=s['numerical_B_gate'],sha256=sha(out/'mechanism-audit.json'))))

if __name__=='__main__':main()
