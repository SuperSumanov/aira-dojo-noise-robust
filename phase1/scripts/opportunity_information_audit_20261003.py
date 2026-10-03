"""Post-readout mechanism audit. No model invocation or candidate execution.

Numeric fields/hashes are recomputed; semantic annotations are explicitly human
code-review judgments, not automatic proof and not outcome-blind adjudication.
"""
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

R = Path('/research/d7/spc/yzyang4/opportunity-information-20261003-v2')
Q = R.parent / 'natural-opportunity-20261003-v1'
SUMMARY = '38f148d57b83a705bf0cd41597ad8807001a0bab1314ee2375d119955694d253'

NOTES = {
    0: ('rationale_and_execution_receipts', 'Multiple feature/model/blend changes; improved, not an isolated early-stopping intervention.'),
    1: ('generated_AST_and_execution_receipts', 'Inspection then LightGBM/LR and feature/blend rewrite; no returned new valid submission.'),
    2: ('rationale_and_execution_receipts', 'Feature/model/blend proposal returned a valid submission but did not beat the parent.'),
    3: ('generated_AST_and_execution_receipts', 'LightGBM/LR rewrite timed out; later generated fallback did not yield a returned solution.'),
    4: ('full_code_AST_diff_and_execution_receipts', 'Three format rejections, then early_stopping_rounds in fit caused TypeError; no new valid submission.'),
    5: ('full_code_and_execution_receipts', 'Reused existing predictions; selected minimum mean public-CV loss member, clipped/normalized and wrote submission. Exact manual-witness prediction recovered.'),
    6: ('full_code_AST_diff_and_execution_receipts', 'Moved early stopping to constructor after errors, but also changed XGBClassifier predict_proba to predict for stacking inputs. Improvement cannot be attributed solely to intended early stopping; not the manual witness.'),
    7: ('full_code_AST_diff_and_execution_receipts', 'Implemented public-CV member selection and recovered exact witness predictions, but unnecessarily refit original models rather than reuse existing arrays.'),
    8: ('rationale_and_execution_receipts', 'Two execution errors, then a valid improving model/stack rewrite. Not an isolated target modification.'),
    9: ('generated_AST_and_execution_receipts', 'LightGBM rewrite timed out; subsequent fallback did not yield a returned new solution.'),
    10: ('rationale_and_execution_receipts', 'Inspection/code errors followed by valid alternatives that did not beat the parent.'),
    11: ('generated_AST_and_execution_receipts', 'GradientBoosting/OOF rewrite then LR-view OOF rewrite produced shape errors; another repair generated but no new valid result.'),
}

def read(p):
    return json.loads(p.read_bytes())

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    out = R / 'readout-v1'
    assert sha(out / 'summary.json') == SUMMARY
    s = read(out / 'summary.json')
    assert read(out / 'verification.json')['status'] == 'PASS'
    assert read(R / 'closed.json')['service_closed']
    assert s['numerical_B_gate'] is False
    for name, digest in s['files'].items():
        assert sha(out / name) == digest
    for name, digest in s['input_hashes'].items():
        assert sha(R / name) == digest
    with (out / 'actions.csv').open(newline='') as f:
        actions = list(csv.DictReader(f))
    totals = {k: sum(a[k] == 'True' for a in actions)
              for k in ('requested', 'generated', 'started', 'returned', 'valid')}
    totals.update(
        format_rejects=sum(a['format_status'] == 'REJECT' for a in actions),
        new_valid=sum(a['step'] != '0' and a['valid'] == 'True' for a in actions),
        new_improved=sum(r['improved_candidates'] for r in s['runs']),
        improved_trajectories=sum(r['gain'] > 1e-12 for r in s['runs']),
        successful_checks=sum(r['successful_checks'] for r in s['runs']),
        unreturned_executions=sum(r['unreturned_executions'] for r in s['runs']),
        returned_execution_failures=sum(a['returned'] == 'True' and a['execution_success'] == 'False' for a in actions),
        budget_exhausted=sum(r['budget_exhausted'] for r in s['runs']))
    qp = read(Q / 'plan.json')
    rows = []
    for r in s['runs']:
        ep = R / f'episode-{r["index"]}'
        witness = next(a for a in qp['schedule'] if a['state'] == r['source_state'] and a['seed'] == 42 and a['arm'] == 'modified')
        selected = ep / f'action-{r["selected_step"]}/submission.private.csv'
        manual = Q / f'episode-{witness["index"]}/action-0/submission.private.csv'
        scope, note = NOTES[r['index']]
        rows.append(dict(index=r['index'], task=r['task'], arm=r['arm'], generation_seed=r['seed'],
            gain=r['gain'], selected_step=r['selected_step'], selected_sha256=sha(selected),
            manual_witness_sha256=sha(manual), matches_manual_witness_bytes=sha(selected) == sha(manual),
            initial_execution_seconds=read(ep / 'action-0/result.json')['execution_wall_seconds'],
            first_generation_seconds=[float(a['generation_seconds']) for a in actions
                if int(a['index']) == r['index'] and a['step'] == '1' and a['generation_seconds']],
            semantic_review_scope=scope, posthoc_semantic_note=note))
    assert {r['index'] for r in rows} == set(NOTES)
    assert [r['index'] for r in rows if r['matches_manual_witness_bytes']] == [5, 7]
    assert len({r['selected_sha256'] for r in rows if r['index'] in (5, 7)}) == 1
    supplement = read(Q.parent / 'natural-decoder-factorial-20261003-v1/verification.json')
    payload = dict(status='POSTHOC_MECHANISM_AUDIT', utc=datetime.now(timezone.utc).isoformat(),
        script_sha256=sha(Path(__file__)), summary_sha256=SUMMARY, totals=totals, runs=rows,
        numerical_B_gate=False, total_window_allocated_gpu_hours=s['accounting']['gpu_hours'] + supplement['total_allocated_gpu_hours'],
        paid_api_calls=0, agent_base_updates=0,
        decision='Do not expand fact-only recipe. Spooky establishes local instruction-conditioned capability, not an automatic new method or cross-task superiority.',
        limitations=[
            'All 12 assigned trajectories retained. Numeric verification is independent; semantic annotation is post-readout human review, not a blinded or exhaustive semantic proof.',
            'Two Spooky C generation seeds recovered one identical fixed-training-seed prediction, not two independent training samples.',
            'The precise modification requirements were human supplied. Information amount, attention and choice restriction are not separately identified.',
            'Previously used developer D_search, qualified states and adaptive retained-best selection do not constitute untouched confirmation.',
            'Conditional query bootstrap excludes source selection, training, new-task and adaptive-query uncertainty; it does not change the frozen gate.',
            'Returned failures and unreturned executions are distinct; generated actions that never start can consume budget through rollback/replay.',
            'Service startup and idle allocation included. Initial build times and first-generation times are reported; shared service/order effects remain possible.',
            'The current narrow Spooky fix is known model selection, not a novel correction; automatic specification discovery remains untested.',
        ])
    with (out / 'mechanism-audit.json').open('x') as f:
        json.dump(payload, f, sort_keys=True, indent=2, allow_nan=False)
    print(json.dumps(dict(status=payload['status'], rows=len(rows), totals=totals,
        total_gpu_hours=payload['total_window_allocated_gpu_hours'], sha256=sha(out / 'mechanism-audit.json'))))

if __name__ == '__main__':
    main()
