"""Post-hoc origin accounting for CLOSED18253 only; no causal ablation.

No candidate/prompt/prediction text leaves the process. Unknown or ambiguous
code-to-journal links remain unknown. Does not read the running18269 cohort.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path('/research/d7/spc/yzyang4/scheduling-weight-effort-20261014-v4')
PLAN = 'cba9bad500a106b8c44f18116c491a1744edb50c3744c7f7ef1f498e45cdbd4f'
PRIMARY = 'bdcfbf37e185f92204584d94c503a72b7ece274d83d01a32b8d15589da5058c0'
SECRET = re.compile(r'sk-[A-Za-z0-9_.-]{12,}|(?:AKIA|ASIA)[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def origin(nodes, code_sha):
    matches = [n for n in nodes if isinstance(n.get('code'), str)
               and hashlib.sha256(n['code'].encode()).hexdigest() == code_sha]
    roles = set()
    for node in matches:
        code_roles = [r for r in node.get('operators_used', []) if r in ('draft', 'improve', 'debug', 'crossover')]
        if len(code_roles) != 1:
            return 'ambiguous'
        roles.add(code_roles[0])
    return next(iter(roles)) if len(roles) == 1 else ('unmatched' if not roles else 'ambiguous')


def main(dest):
    assert sha(ROOT/'plan.json') == PLAN
    primary_path = ROOT/'readout-20261014-v1/summary.json'
    assert sha(primary_path) == PRIMARY
    assert read(ROOT/'closed.json')['complete']
    primary = read(primary_path)
    assert primary['assigned'] == primary['complete'] == 32
    plan = read(ROOT/'plan.json')
    original_rows = {r['index']: r for r in read(ROOT/'readout-20261014-v1/runs.json')}
    warm = read(ROOT/'warm-receipt.json')
    rows, endpoints, sources = [], [], []
    for spec in plan['schedule']:
        ep = ROOT/f"episode-{spec['index']}"
        journal = ep/'checkpoint/journal.jsonl'
        raw = journal.read_text()
        if SECRET.search(raw):
            raise ValueError('credential_shape_hit_no_content_export')
        nodes = [json.loads(s) for s in raw.splitlines() if s.strip()]
        sources.append(dict(index=spec['index'], journal_sha256=sha(journal), nodes=len(nodes)))
        sign = 1 if spec['task'] == 'aerial-cactus-identification' else -1
        initial = warm[spec['task']]['score']
        own = []
        for path in sorted(ep.glob('candidate-*.json')):
            if '.private.' in path.name:
                continue
            c = read(path)
            timely = c['elapsed_seconds'] <= plan['run_seconds']
            valid = (timely and c['valid'] is True and c['exit_code'] == 0 and not c['timed_out']
                     and type(c.get('score')) in (int, float) and math.isfinite(c['score']))
            role = origin(nodes, c['code_sha256'])
            row = dict(index=spec['index'], task=spec['task'], arm=spec['arm'],
                       candidate=int(path.stem.split('-')[-1]), origin=role,
                       elapsed_seconds=c['elapsed_seconds'], timely=timely, valid=valid,
                       score=c['score'] if valid else None,
                       above_common_warm=bool(valid and sign*(c['score']-initial) > 0))
            rows.append(row)
            own.append(row)
        best = max([initial]+[r['score'] for r in own if r['valid']], key=lambda x: sign*x)
        assert abs(best-original_rows[spec['index']]['score']) <= 1e-12
        winners = sorted({r['origin'] for r in own if r['valid'] and r['score'] == best}) if best != initial else ['warm']
        endpoints.append(dict(index=spec['index'], task=spec['task'], arm=spec['arm'],
                              best=best, best_origins=winners))
    groups = []
    for arm in ('old_fast', 'old_medium', 'new_fast', 'new_medium'):
        for task in sorted(warm):
            own = [r for r in rows if (r['arm'], r['task']) == (arm, task)]
            ends = [r for r in endpoints if (r['arm'], r['task']) == (arm, task)]
            assert len(ends) == 4
            sign = 1 if task == 'aerial-cactus-identification' else -1
            best = max((r['best'] for r in ends), key=lambda x: sign*x)
            winners = sorted({role for r in ends if r['best'] == best for role in r['best_origins']})
            counts = {role: dict(returned=sum(r['origin'] == role for r in own),
                                valid=sum(r['origin'] == role and r['valid'] for r in own),
                                above_warm=sum(r['origin'] == role and r['above_common_warm'] for r in own))
                      for role in sorted({r['origin'] for r in own})}
            groups.append(dict(arm=arm, task=task, assigned=4, pool_best=best,
                               pool_best_origins=winners, origins=counts))
    result = dict(kind='closed_posthoc_origin_diagnostic', assigned=32,
                  plan_sha256=PLAN, primary_summary_sha256=PRIMARY, source_sha256=sha(__file__),
                  rows=rows, endpoints=endpoints, groups=groups, sources=sources,
                  candidate_returns=len(rows), origin_counts=dict(Counter(r['origin'] for r in rows)),
                  all_endpoint_scores_reproduced=True, no_new_execution=True,
                  no_training_data_read=True, original_quality_gate=primary['quality_gate'],
                  limits=['Code-hash/recorded-role association is descriptive, not the effect of removing Debug.',
                          'Shared archive and nonidentical initial prompts forbid clean weight or role causality.',
                          'Return counts omit interrupted requests; per-run allocation costs remain in the primary readout.',
                          'Not the senior training dataset or a test of its sampler/loss.'])
    with Path(dest).open('x') as handle:
        json.dump(result, handle, sort_keys=True, indent=2, allow_nan=False)
    print(json.dumps({k: v for k, v in result.items() if k not in ('rows', 'endpoints', 'sources')}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('out')
    main(parser.parse_args().out)
