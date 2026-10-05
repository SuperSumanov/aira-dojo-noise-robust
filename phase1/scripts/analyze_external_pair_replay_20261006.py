"""One descriptive readout after all original-code replays are closed."""
import csv
import math
import os
import statistics
import subprocess
from external_pair_replay_20261006 import B, R, D, TASKS, check, load, read, schedule, sha, write


def difference(task, p, c):
    assert task in TASKS
    if p is None or c is None:
        return None
    assert all(math.isfinite(x) for x in (p, c))
    return (c-p) * (1 if task == TASKS[0] else -1)


def tests():
    assert difference(TASKS[0], .5, .75) == .25
    assert difference(TASKS[1], .75, .5) == .25
    assert difference(TASKS[1], None, .5) is None
    assert difference(TASKS[0], .75, .5) == -.25
    assert difference(TASKS[1], .5, None) is None
    assert difference(TASKS[1], .5, .5) == 0
    try:
        difference('unknown-task', .5, .6)
    except AssertionError:
        pass
    else:
        raise AssertionError('unknown task must fail closed')
    return dict(status='PASS', orientation_and_missing_fixtures=7)


def independent(task, prediction, spec):
    import numpy as np
    from sklearn.metrics import roc_auc_score
    manifest = B/spec['view']/'manifest.json'
    assert sha(manifest) == spec['view_sha']
    labels = B/spec['source']/'private/dsearch.csv'
    assert sha(labels) == read(manifest)['source_dsearch_sha256']
    with labels.open(newline='', encoding='utf-8-sig') as f:
        truth = list(csv.DictReader(f))
    with prediction.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    p = {r[spec['id']]:r for r in rows}
    assert len(p) == len(rows) == len(truth)
    assert set(p) == {r[spec['id']] for r in truth}
    if task == TASKS[0]:
        return float(roc_auc_score([int(r[spec['label']]) for r in truth],
                                  [float(p[r[spec['id']]][spec['label']]) for r in truth]))
    values = np.array([float(p[r['id']][r['author']]) for r in truth])
    assert np.isfinite(values).all()
    return float(-np.log(np.maximum(values, 1e-15)).mean())


def main():
    plan = check()
    job = read(R/'launch.json')['job']
    assert read(R/'closed.json')['assigned'] == 6
    assert all((R/f'episode-{i}/closed.json').exists() for i in range(6))
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    assert not subprocess.check_output(['squeue','-j',job,'-h','-o','%i'], env=env, text=True, timeout=20).strip()
    account = subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o',
        'JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'], env=env, text=True, timeout=20).strip().splitlines()
    assert len(account) == 1
    jid, state, elapsed, tres, exitcode, *_ = account[0].split('|')
    assert jid == job and 'gres/gpu=1' in tres
    assert state.startswith(('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY'))
    out = R/'readout-v1'
    out.mkdir(mode=0o700, exist_ok=False)
    freeze = {str(p.relative_to(R)):sha(p) for p in R.glob('episode-*/action-0/submission.private.csv')}
    write(out/'prediction-freeze.json', freeze)
    rows, errors = [], []
    for s in schedule():
        ep = R/f"episode-{s['index']}"
        pred = ep/'action-0/submission.private.csv'
        done = read(ep/'completed.json') if (ep/'completed.json').exists() else {}
        row = dict(**s, completed=bool(done), valid=False, dev_metric=None,
            metric='auc' if s['task'] == TASKS[0] else 'log_loss',
            seconds=done.get('seconds'), exec_seconds=done.get('exec_seconds'),
            timed_out=done.get('timed_out'), error_type=done.get('error_type'),
            step_returncode=read(ep/'closed.json')['returncode'], prediction_sha256=None,
            source_commit=plan['source_commit'])
        if done.get('valid_execution') and row['step_returncode'] == 0:
            assert sha(pred) == done['prediction_sha256']
            cfg = read(R/'configs'/f"{s['index']}.json")
            scorer = cfg['task']['search_only_dev_scorer_path']
            assert sha(scorer) == cfg['task']['search_only_dev_scorer_sha256']
            m = load('external_replay_scorer', scorer)
            try:
                result = m.score(s['task'], pred)
            except m.InvalidSubmissionError:
                row['error_type'] = 'InvalidSubmissionError'
            else:
                v = result[row['metric']]
                v2 = independent(s['task'], pred, m.SPEC[s['task']])
                assert math.isfinite(v) and abs(v-v2) < 1e-12
                errors.append(abs(v-v2))
                row.update(valid=True, dev_metric=v, prediction_sha256=sha(pred))
        rows.append(row)
    pairs = []
    for case in range(3):
        q = {r['arm']:r for r in rows if r['case'] == case}
        assert set(q) == {'P','C'}
        p, c = q['P'], q['C']
        pairs.append(dict(case=case, task=p['task'], complete=p['valid'] and c['valid'],
            P=p['dev_metric'], C=c['dev_metric'],
            child_minus_parent_oriented=difference(p['task'], p['dev_metric'], c['dev_metric']),
            parent_seconds=p['seconds'], child_seconds=c['seconds'],
            same_prediction_hash=(p['prediction_sha256']==c['prediction_sha256']) if p['valid'] and c['valid'] else None))
    by_task = []
    for task in TASKS:
        vals = [p['child_minus_parent_oriented'] for p in pairs if p['task'] == task and p['complete']]
        by_task.append(dict(task=task, complete_pairs=len(vals),
            median=statistics.median(vals) if vals else None,
            sample_variance=statistics.variance(vals) if len(vals)>1 else None))
    for rel, h in freeze.items():
        assert sha(R/rel) == h
    summary = dict(protocol=plan['protocol'], source_commit=plan['source_commit'],
        plan_sha256=sha(R/'plan.json'), analysis_sha256=sha(__file__), tests=tests(),
        job=job, state=state, exitcode=exitcode, allocation_seconds=int(elapsed),
        allocated_gpu_hours=int(elapsed)/3600, assigned=6, source_excluded_pairs=1,
        complete_programs=sum(r['valid'] for r in rows), independent_scores=len(errors),
        max_absolute_verifier_error=max(errors, default=None), pairs=pairs, per_task=by_task,
        automatic_expansion=False, new_method_confirmed=False, protected_opened=False,
        limitation=plan['limitation']+' '+plan['budget']+' Published source may already be adapted to these benchmark tasks; source originality is not data independence.')
    write(out/'summary.json', summary)
    with (out/'runs.csv').open('x', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    write(out/'export-receipt.json', {p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print(__import__('json').dumps(summary))


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--tests']: print(__import__('json').dumps(tests()))
    else:
        assert not sys.argv[1:]
        main()
