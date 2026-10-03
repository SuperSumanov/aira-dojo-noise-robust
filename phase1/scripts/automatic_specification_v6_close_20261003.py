"""Record the closed, unavailable-source batch without imputing treatment effects."""
import datetime,hashlib,json
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-gpu3-v6')
PLAN='71340fc4a5fb97f09fa1dc31b5189500bffef3e73b68382a6bff9b628b61e154'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=R/'readout-v1';s=read(out/'summary.json');v=read(out/'verification.json')
    assert sha(R/'plan.json')==PLAN and v['status']=='PASS' and v['summary_sha256']==sha(out/'summary.json')
    assert read(R/'closed.json')['service_closed'] and s['accounting']['state']=='COMPLETED'
    assert not s['root_availability_gate'] and not s['numerical_B_gate']
    records=[]
    for r in s['runs']:
        if r['index']==0:
            status='SOURCE_UNAVAILABLE'
            note=('Four accepted SOLUTION programs execute and fail. CSV target-column detection selects sampleSubmission.csv as training; later mixed-file loops overwrite the real training JSON. '
                'Observed file order is train.json, description.md, test.json, sampleSubmission.csv. Error sequence: missing text key, empty vocabulary, Series axis error, Series join TypeError. '
                'Later rationales incorrectly attribute the 300x2 dataframe to train.json, and code joins sample labels to query features. No valid submission and no hidden labels acquired. '
                'This is a source-generation failure, not an evaluated B/C phase-prompt failure. Multiple downstream bugs mean fixing the file choice alone is not proven sufficient.')
        elif r['index']==1:
            status='SOURCE_VALID'
            note='First SOLUTION succeeds: train-fitted word/char TFIDF and LR C4. Known baseline. No comparison continuation was launched.'
        else:
            status='NOT_LAUNCHED'
            note='Frozen joint source-availability gate stopped the comparison. No model call, no initial execution and no treatment-effect observation; preserve nulls, not zero gain.'
            assert r['calls_completed']==0
        records.append(dict(index=r['index'],role=r['role'],task=r['task'],arm=r['arm'],seed=r['seed'],implementation=status,review=note,
            calls=r['calls_completed'],accepted_plans=r['plan_actions'],format_rejections=r['format_rejects'],new_valid_candidates=r['valid_candidates'],new_improved_candidates=r['improved_candidates']))
    assert len(records)==14 and sum(r['calls'] for r in records)==5
    audit=dict(status='MANUAL_CLOSED_BATCH_AUDIT',plan_sha256=PLAN,summary_sha256=sha(out/'summary.json'),rubric_sha256=sha(R/'mechanism-freeze.json'),
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),records=records,numerical_B_gate=s['numerical_B_gate'],method_effect='NOT_TESTED_SOURCE_GATE_FAILED',novelty='NOT_ESTABLISHED',
        source_warning='One successful source and one unavailable source; joint gate prevents survivor-only comparison. Do not replace the failed seed or import a prior successful root.',
        protocol_warning='Stage-clarity comparison change was never exercised by a model. Source interface produced accepted code on every call; this batch does not fail through the V4 formatting/PLAN mechanism.',
        limitations='Same analyst, arm visible, code/rationale review before and after aggregate closure; not independent blinded semantic review. Two developer tasks, reused data, no generalization confirmation.',
        decision='Seal without rescue. No further GPU batch or prompt sweep in this work window. V5 remains negative evidence for its actual mandatory-plan protocol; V6 is missing treatment evidence, not a second negative comparison. Use existing traces only for exploratory mechanism appraisal.')
    with (out/'mechanism-audit.json').open('x') as f:json.dump(audit,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps(dict(status=audit['status'],records=len(records),method_effect=audit['method_effect'],sha256=sha(out/'mechanism-audit.json'))))
if __name__=='__main__':main()
