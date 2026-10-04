"""Record post-closure semantic review and explicitly posthoc pair availability.

Does not execute candidates, refit, change the frozen ABC gate, or impute an
initial result. Comments are a condition-aware human/assistant review, not an
independent blinded semantic test.
"""
import hashlib
import json
from pathlib import Path
import re
import statistics

R = Path('/research/d7/spc/yzyang4/diagnostic-information-20261004-v1')
PLAN = '63322ce2f5e38ac22c2a98b2c7bae5fa27334c4d5f3052297938418c26627679'
SUMMARY = 'cac2383749899ff1ae5ec34adf7ef4eec6446d30f485c0ee5b1ddb594b7c6675'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+\S{12,})')
NOTES = {
 0: 'Selected step1 intersects numeric columns with query, lowers learning rate, removes XGB/stack and uses fixed numeric/text mixture. Multiple changes. Rationale cites misleading high numeric CV; improvement does not validate that explanation.',
 1: 'Parent retained; all four generated responses rejected by the frozen standalone-mode contract.',
 2: 'Selected step3 changes numeric fitting, adds numeric LR and changes text/ngram and stacking. Not a single scope correction; reference numeric CV is not the corrected diagnostic score.',
 3: 'Parent retained. Returned step1 code execution timed out; worker exhausted deadline. No new valid submission.',
 4: 'Parent retained. One returned candidate failed on ndarray.tocsr; other generated responses rejected by mode format.',
 5: 'Parent retained; all four generated responses rejected by the frozen standalone-mode contract.',
 6: 'Two new valid candidates, neither improves parent. Final returned prediction is byte-identical to parent.',
 7: 'Parent retained. Returned step2 code execution timed out; worker exhausted deadline. No new valid submission.',
 8: 'Selected step3 uses common numeric schema, modified boosting, denser text branch and OOF-derived mixture weights. Prior step2 failed on len(int), not the sparse-LightGBM diagnosis asserted by the next rationale.',
 9: 'Selected step2 fits word/char/combined LR mixtures across regularization strengths. Verified new prediction and lower loss. Later rationale calls the lower loss worse; retained-best scoring prevents that narrative from overwriting the better submission.',
 10: 'Selected step4 changes features/model/mixture and fixes XGB early-stopping parameter placement after the actual TypeError. Query-compatible feature intersection remains. Not isolated report-scope correction.',
 11: 'Initial parent did not execute: kernel-readiness failure was mislabeled as five-minute code timeout by the frozen interpreter. Subsequent live LR reconstruction and CV C-selection yield valid final submission, but initial/gain remain missing.'
}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(p):
    raw = p.read_bytes()
    assert not SECRET.search(raw), 'credential shape; no content emitted'
    return json.loads(raw)

def pairwise(runs):
    rows, stats = [], []
    for task in sorted({r['task'] for r in runs}):
        seeds = sorted({r['seed'] for r in runs if r['task'] == task})
        for left, right in (('B','A'), ('C','A'), ('C','B')):
            values = []
            for seed in seeds:
                group = {r['arm']:r for r in runs if r['task'] == task and r['seed'] == seed}
                a,b = group[left],group[right]
                comparable = (a['initial'] is not None and b['initial'] is not None
                    and a['initial_sha256'] == b['initial_sha256']
                    and a['gain'] is not None and b['gain'] is not None)
                delta = a['gain']-b['gain'] if comparable else None
                if comparable:
                    values.append(delta)
                rows.append(dict(task=task, seed=seed, contrast=left+'_minus_'+right,
                    comparable=comparable, delta=delta,
                    reason=None if comparable else 'own_initial_missing_or_not_identical'))
            stats.append(dict(task=task, contrast=left+'_minus_'+right, paired=len(values),
                values=values, median=statistics.median(values) if values else None,
                sample_variance=statistics.variance(values) if len(values)>1 else None))
    return dict(rows=rows, contrasts=stats,
        boundary='POSTHOC descriptive available-pair supplement. Frozen analysis requires complete ABC triples and is unchanged. No missing B initial is filled, no success-conditioned exclusion from the assigned table, no confirmatory p-value or gate rescue.')

def main():
    assert sha(R/'plan.json') == PLAN and sha(R/'readout-v1/summary.json') == SUMMARY
    assert (R/'all-closed.json').exists() and read(R/'closed.json')['service_closed']
    summary = read(R/'readout-v1/summary.json')
    verified = read(R/'readout-v1/verification.json')
    assert verified['status'] == 'PASS' and verified['summary_sha256'] == SUMMARY
    assert verified['numerical_C_gate'] is False
    checks = {(r['index'],r['step']):r for r in verified['score_checks']}
    rows = []
    for r in summary['runs']:
        key = (r['index'],r['selected_step'])
        selected = checks[key]
        result = read(R/f'episode-{key[0]}/action-{key[1]}/result.json')
        assert selected['metric'] == r['selected'] and result['execution_success']
        rows.append(dict(index=r['index'], task=r['task'], arm=r['arm'], seed=r['seed'],
            selected_step=r['selected_step'], selected_code_sha256=result['code_sha256'],
            selected_submission_sha256=selected['submission_sha256'],
            differs_from_own_initial=(None if r['initial'] is None else selected['submission_sha256'] != r['initial_sha256']),
            own_initial_available=r['initial'] is not None, review=NOTES[r['index']]))
    assert len(rows) == 12 and {r['index'] for r in rows} == set(NOTES)
    timeout = read(R/'episode-11/action-0/node.private.json')
    assert 'Kernel did not become ready in time.' in timeout['terminal']
    assert 'Execution exceeded the time limit of 5 minutes' in timeout['terminal']
    src = R/'source/src/dojo/core/interpreters/jupyter'
    assert sha(src/'jupyter_code_executor.py') == '99681e6a519a14bcdcc0c56caacfb108760b73e98af71c5b054efe5dead9efc0'
    assert sha(src/'jupyter_interpreter.py') == 'd60eb92f48457b6f1f1e8a69665a2c689b3340be1efa8f66a7b9cc242446e47c'
    review = dict(plan_sha256=PLAN, summary_sha256=SUMMARY, assigned=12,
        reviewer='condition-aware assistant; all45 rationale briefs and six selected-new-code bodies inspected; no independent blinded annotation',
        script_sha256=sha(Path(__file__)), rows=rows,
        timeout_evidence=dict(index=11, step=0, phase='kernel_readiness',
            node_sha256=sha(R/'episode-11/action-0/node.private.json'),
            executor_sha256=sha(src/'jupyter_code_executor.py'),
            interpreter_sha256=sha(src/'jupyter_interpreter.py'),
            boundary='Exact frozen code returns before candidate execute when readiness fails; why readiness failed is not established. Original failure retained; no retry or frozen-source modification.'),
        conclusion='Local report-versus-no-report signal exists, but corrected report does not consistently exceed original-scope report. Frozen expansion gate false; no new GPU or rescue seeds.',
        limits=['Two reused development parents, not cross-task confirmation.',
            'Strict mode format rejected23 of45 generations; not23 missing or invalid Python blocks.',
            'Report conditions also change prompt length/content; this is a packet intervention, not isolated truthfulness.',
            'Reports were manually constructed from prior executed diagnostics; no autonomous correction or complete cost-parity claim.',
            'Changes are multicomponent; better score does not validate stated mechanism.',
            'Current ordinary arm is a short local27B baseline, not a strong external system reproduction.'])
    supplement = pairwise(summary['runs'])
    supplement.update(plan_sha256=PLAN, summary_sha256=SUMMARY, assigned=12)
    assert next(r for r in summary['runs'] if r['index']==11)['gain'] is None
    assert next(r for r in supplement['contrasts'] if r['task']=='spooky-author-identification' and r['contrast']=='C_minus_A')['paired'] == 2
    for path, obj in ((R/'mechanism-review.json', review), (R/'readout-v1/posthoc-available-pairs.json', supplement)):
        raw = (json.dumps(obj, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()
        assert not SECRET.search(raw)
        with path.open('xb') as f:
            f.write(raw)
    print(json.dumps(dict(status='RECORDED', assigned=12, numerical_C_gate=False,
        mechanism_review_sha256=sha(R/'mechanism-review.json'),
        supplement_sha256=sha(R/'readout-v1/posthoc-available-pairs.json'),
        available_pair_descriptives=supplement['contrasts'])))

if __name__ == '__main__':
    main()
