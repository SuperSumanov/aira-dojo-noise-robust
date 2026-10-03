"""Record manual closed-batch interpretation, not new experiments or scores."""
import hashlib,json,datetime
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-gpu3-v4')
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    summary=read(R/'readout-v1/summary.json');audit=read(R/'readout-v1/protocol-audit.json')
    assert read(R/'closed.json')['service_closed'] and read(R/'readout-v1/verification.json')['status']=='PASS'
    assert audit['counts']==dict(responses=8,accepted_plans=4,format_rejections=4,executions_started=0,parseable_code_blocks=3,csv_writer_blocks=0)
    assert not audit['method_tested'] and not summary['root_availability_gate']
    assert all(r['gain'] is None for r in summary['runs'])
    records=[]
    for i,steps in [(0,[1,2,3,4]),(1,[1,2,3,4])]:
        records.append(dict(index=i,grounding='No executed data observation. Plans proposed standard ML pipelines and guessed file structure.',
            implementation='NOT_IMPLEMENTED: no program reached execution; no valid submission.',preservation='NOT_ASSESSABLE: no initial valid program.',
            known_rules='Root plans proposed standard TFIDF, regularized linear models, public CV and optional boosting, not novel edits.',
            steps_reviewed=steps,
            protocol_findings=('Two accepted PLAN replies; call2 included both PLAN and CHECK before a valid Python inspection block, rejected; final call repeated PLAN despite SOLUTION requirement.' if i==0 else 'Two accepted near-duplicate PLAN replies; calls3/4 used native XML-like tool syntax for inspection and were rejected by the declared text-action parser.'),
            recovered_code='Only file/data inspection in the three recoverable blocks across both tasks. Not hidden complete solutions. Not executed after closure.'))
    result=dict(status='MANUAL_CLOSED_BATCH_AUDIT',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        summary_sha256=sha(R/'readout-v1/summary.json'),rubric_sha256=sha(R/'mechanism-freeze.json'),protocol_audit_sha256=sha(R/'readout-v1/protocol-audit.json'),
        root_records=records,comparison_assignments=12,comparison_started=0,method_effect='UNTESTED',novelty='NOT_ESTABLISHED',
        decision='Close this cohort. No source rescue, replacement, additional seeds or parser reinterpretation counted as its result. A future separately frozen acquisition-interface change needs authorization.',
        limitation='Manual review by the same analyst; arm and execution events visible, qualitative response text may reveal intended behavior. Not an independent or perfectly blinded review. No new effect, no conclusion that automatic specifications cannot work.',
        preflight_lesson='Synthetic SDK/loop tests established software mechanics, not real-model adherence. Allowing no-execution PLAN at shared source acquisition created an unnecessary failure surface; this pilot did not reach the intended comparison.')
    with (R/'readout-v1/mechanism-audit.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps(dict(status=result['status'],method_effect=result['method_effect'],comparison_started=0,sha256=sha(R/'readout-v1/mechanism-audit.json'))))
if __name__=='__main__':main()
