"""All32 denominator; predeclared medium primary, fast secondary cannot rescue it.

Reuse the already independently checked external-score/identity/cleanup reader.
Exact-count source transformations keep donor originals immutable and fail on drift.
"""
import argparse
import inspect
from pathlib import Path
import long_effort_readout_20261013 as prior
from weight_effort_policy_20261014 import ARMS, ORDER, RUN, SLOT, CAP, effort, model

TASKS, SIGN = prior.TASKS, prior.SIGN


def quality(scores):
    contrasts = [dict(task=t, mode=mode, primary=(mode == 'medium'),
        reference='old_'+mode, method='new_'+mode,
        method_best=scores['new_'+mode, t], reference_best=scores['old_'+mode, t],
        oriented_delta=SIGN[t]*(scores['new_'+mode, t]-scores['old_'+mode, t]))
        for mode in ('medium', 'fast') for t in TASKS]
    passed = all(r['oriented_delta'] >= (.001 if r['task'] == TASKS[1] else -1e-12)
                 for r in contrasts if r['primary'])
    return contrasts, passed


source = inspect.getsource(prior.analyze)
def replace(a, b):
    global source
    assert source.count(a) == 1, a[:80]
    source = source.replace(a, b)
replace("p['planned'] == 24", "p['planned'] == 32")
replace('dict(assigned=24,', 'dict(assigned=32,')
replace('for b in range(3):', 'for b in range(4):')
replace("expected = effort(s['arm'], e['role'])", "expected = effort(s['arm'], e['role'])\n                assert e['model_id'] == model(s['arm'])")
replace("spec, warm = read(root/'dev-views/spec.json'), read(root/'warm-receipt.json')",
        """spec, warm = read(root/'dev-views/spec.json'), read(root/'warm-receipt.json')
    assert sha(root/'warm.private.json') == p['common_start_sha256']
    assert sha(root/'warm-receipt.json') == p['common_start_receipt_sha256']
    if (root/'adapter-service-qualification.json').exists():
        qualification = read(root/'adapter-service-qualification.json')
        assert {x['model_id'] for x in qualification['rows']} == {model('old_medium'), model('new_medium')}
        assert all(x['response_received'] for x in qualification['rows'])
    else:
        assert closed['complete'] == 0, 'adapter qualification missing after runs began'""")
namespace = dict(vars(prior), ARMS=ARMS, ORDER=ORDER, RUN=RUN, SLOT=SLOT, CAP=CAP,
                 effort=effort, model=model, quality=quality, __file__=__file__)
exec(compile(source, __file__, 'exec'), namespace)
analyze = namespace['analyze']

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('root'); ap.add_argument('out')
    ap.add_argument('--gpu-seconds', type=int, required=True)
    a = ap.parse_args(); analyze(a.root, a.out, a.gpu_seconds)
