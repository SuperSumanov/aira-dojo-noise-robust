"""Post-hoc conditional uncertainty and fixed-signature failure classification.

Not a fresh test, a correction for repeated development, or training-seed variance.
No program is repaired/replayed; all incomplete pairs stay incomplete.
"""
import csv
import json
import os
import re
import signal
import time

from analyze_external_pair_replay_20261006 import independent
from external_pair_replay_20261006 import B, R, TASKS, load, read, sha, write


def main():
    import numpy as np
    from sklearn.metrics import roc_auc_score
    started = time.monotonic()
    def alarm(*args): raise TimeoutError('bounded descriptive analysis')
    signal.signal(signal.SIGALRM, alarm); signal.alarm(180)
    summary_path = R/'readout-v1/summary.json'
    assert sha(summary_path) == '27d98bf626ad2a6bc9186bd370ca9ffe7d04f60ffbbb9e6ef0cc41e1873867fb'
    summary = read(summary_path)
    with (R/'readout-v1/runs.csv').open(newline='') as f:
        runs = list(csv.DictReader(f))
    out = R/'supplement-v1'; out.mkdir(mode=0o700, exist_ok=False)
    write(out/'plan.json', dict(summary_sha256=sha(summary_path), source_sha256=sha(__file__),
        seed=116299, replicates=2000, confidence=.95, posthoc=True,
        selection='Every complete original pair; no new executions or repaired endpoints.',
        boundary=__doc__))
    contrasts = []
    for pair in summary['pairs']:
        if not pair['complete']: continue
        group = {r['arm']:r for r in runs if int(r['case']) == pair['case']}
        task = pair['task']; assert task == TASKS[0], 'Only AUC complete in frozen primary readout'
        cfg = read(R/'configs'/f"{group['P']['index']}.json")['task']
        assert sha(cfg['search_only_dev_scorer_path']) == cfg['search_only_dev_scorer_sha256']
        scorer = load('external_replay_supplement_scorer', cfg['search_only_dev_scorer_path'])
        spec = scorer.SPEC[task]
        truth_path = B/spec['source']/'private/dsearch.csv'
        manifest = B/spec['view']/'manifest.json'
        assert sha(manifest) == spec['view_sha']
        assert sha(truth_path) == read(manifest)['source_dsearch_sha256']
        with truth_path.open(newline='', encoding='utf-8-sig') as f: truth = list(csv.DictReader(f))
        y = np.array([int(r[spec['label']]) for r in truth])
        values = []
        for arm in ['P','C']:
            row = group[arm]
            path = R/f"episode-{row['index']}/action-0/submission.private.csv"
            assert sha(path) == row['prediction_sha256']
            assert abs(independent(task,path,spec)-float(row['dev_metric'])) < 1e-12
            with path.open(newline='', encoding='utf-8-sig') as f: rr = list(csv.DictReader(f))
            pred = {r[spec['id']]:float(r[spec['label']]) for r in rr}
            assert len(pred) == len(rr) == len(truth)
            values.append(np.array([pred[r[spec['id']]] for r in truth]))
        rng = np.random.default_rng(116299)
        groups = [np.flatnonzero(y == label) for label in [0,1]]
        draws = []
        for _ in range(2000):
            ix = np.concatenate([rng.choice(g,len(g),replace=True) for g in groups])
            draws.append(roc_auc_score(y[ix],values[1][ix])-roc_auc_score(y[ix],values[0][ix]))
        lo, hi = np.quantile(draws,[.025,.975])
        contrasts.append(dict(case=pair['case'], task=task, n=len(y), estimate=pair['child_minus_parent_oriented'],
            conditional_low=float(lo), conditional_high=float(hi)))
    failures = []
    for row in runs:
        if row['valid'] == 'True': continue
        path = R/f"episode-{row['index']}/action-0/terminal.private.json"
        terminal = read(path)['terminal'] if path.exists() else ''
        classes = sorted(set(re.findall(r'(?m)^([A-Za-z_][A-Za-z_0-9]*(?:Error|Exception)):',terminal)))
        keywords = sorted(set(re.findall(r'''unexpected keyword argument ['"]([a-zA-Z_][a-zA-Z_0-9]*)['"]''',terminal)))
        failures.append(dict(index=int(row['index']), case=int(row['case']), arm=row['arm'],
            terminal_sha256=sha(path) if path.exists() else None, exception_classes=classes,
            unexpected_keyword_names=keywords, timed_out=row['timed_out'], no_repair=True))
    write(out/'summary.json',dict(plan_sha256=sha(out/'plan.json'), contrasts=contrasts,
        failures=failures, elapsed_seconds=time.monotonic()-started, boundary=__doc__,
        model_executions=0, all_missing_preserved=True, new_method_confirmed=False))
    print(json.dumps(read(out/'summary.json')))


if __name__ == '__main__':
    os.umask(0o077); main()
