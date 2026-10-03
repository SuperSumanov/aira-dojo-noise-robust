"""Read-only, zero-fit descriptive audit AFTER the qualification gate closed.

Not a new gate, rescue, significance test, or independent confirmation. Only the
already-open Pizza development split is read; no protected cohort or final test.
Print aggregate results; never print individual labels, predictions, or IDs.
"""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path('/research/d7/spc/yzyang4/executable-evidence-20261004-v1')
LABEL = Path('/research/d7/spc/yzyang4/pizza-dsearch-dev-20260925-ZQOMNpt5/split-v1/private/dsearch.csv')
EXPECTED = {
    'plan.json': 'f5aba6d06b20a1c4037abc52c373842bae70f6672d3a2ac7b20c8bb3fc82dd3c',
    'readout-v1/runs.csv': '2824c004bcf79b4fd47e31dc9a1aaa26c605ebff8e305876b62aced4b5774b68',
    'safe-export-v1/verification.json': 'dcb892f5377806ffde988c5103ce58add8060219687eff1da36d4706ea59e960',
}
LABEL_SHA = '1d540e3c56bcc47c8db885b5cf8d4fcc9ba9148cc3700afdc9d863d29cdc24f8'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as file:
        return list(csv.DictReader(file))


def rank_auc(truth, pred, omitted=None):
    ordered = sorted((pred[k], truth[k]) for k in truth if k != omitted)
    npos = sum(y for _, y in ordered)
    total = 0.0
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j][0] == ordered[i][0]:
            j += 1
        total += ((i + 1 + j) / 2) * sum(y for _, y in ordered[i:j])
        i = j
    return (total - npos * (npos + 1) / 2) / (npos * (len(ordered) - npos))


def main():
    for name, digest in EXPECTED.items():
        assert sha(ROOT / name) == digest, name
    assert sha(LABEL) == LABEL_SHA
    runs = rows(ROOT / 'readout-v1/runs.csv')
    receipt = json.loads((ROOT / 'safe-export-v1/verification.json').read_bytes())
    # Export re-encodes JSON. Bind the published bytes and separately require
    # content equality with the raw verifier output; do not silently accept drift.
    assert receipt == json.loads((ROOT / 'readout-v1/verification.json').read_bytes())
    groups = []
    for task, arm in sorted({(r['task'], r['arm']) for r in runs}):
        group = [r for r in runs if (r['task'], r['arm']) == (task, arm)]
        ids = {int(r['index']) for r in group}
        parents = {r['initial_sha256'] for r in group}
        assert len(parents) == 1
        parent = next(iter(parents))
        scores = [r for r in receipt['score_checks'] if r['index'] in ids and r['step'] > 0]
        assert len(scores) == sum(int(r['valid_candidates']) for r in group)
        different = [r for r in scores if r['submission_sha256'] != parent]
        groups.append(dict(task=task, arm=arm, assigned_runs=len(group), valid_new_actions=len(scores),
                           exact_parent_prediction_repeats=len(scores)-len(different),
                           nonparent_actions=len(different),
                           distinct_nonparent_prediction_files=len({r['submission_sha256'] for r in different})))
    labels = rows(LABEL)
    truth = {r['request_id']: int(r['requester_received_pizza']) for r in labels}
    assert len(truth) == len(labels) and set(truth.values()) == {0, 1}
    pos = [k for k in truth if truth[k] == 1]
    neg = [k for k in truth if truth[k] == 0]
    results = []
    checked = 0
    maximum_error = 0.0
    for seed in sorted({r['seed'] for r in runs if r['task'] == 'random-acts-of-pizza'}):
        curves = {}
        for arm in 'ABC':
            run = next(r for r in runs if r['task'] == 'random-acts-of-pizza' and r['seed'] == seed and r['arm'] == arm)
            path = ROOT / f"episode-{run['index']}" / f"action-{run['selected_step']}" / 'submission.private.csv'
            values = rows(path)
            pred = {r['request_id']: float(r['requester_received_pizza']) for r in values}
            assert len(pred) == len(values) and set(pred) == set(truth)
            assert all(math.isfinite(v) and 0 <= v <= 1 for v in pred.values())
            win = {(a, b): float(pred[a] > pred[b]) + .5 * float(pred[a] == pred[b]) for a in pos for b in neg}
            total = math.fsum(win.values())
            full = total / (len(pos) * len(neg))
            assert math.isclose(full, float(run['selected']), rel_tol=0, abs_tol=1e-12)
            deleted = {a: (total - math.fsum(win[a, b] for b in neg)) / ((len(pos)-1) * len(neg)) for a in pos}
            deleted.update({b: (total - math.fsum(win[a, b] for a in pos)) / (len(pos) * (len(neg)-1)) for b in neg})
            for omitted, value in [(None, full), *deleted.items()]:
                error = abs(value - rank_auc(truth, pred, omitted))
                assert error < 1e-12
                maximum_error = max(maximum_error, error)
                checked += 1
            curves[arm] = (full, deleted, sha(path))
        for x, y in [('C', 'A'), ('B', 'A'), ('C', 'B')]:
            differences = [curves[x][1][k] - curves[y][1][k] for k in truth]
            results.append(dict(seed=int(seed), contrast=x+'_minus_'+y,
                                full_difference=curves[x][0]-curves[y][0],
                                single_row_deletion_min=min(differences), single_row_deletion_max=max(differences),
                                deletion_positive=sum(v > 1e-12 for v in differences),
                                deletion_zero=sum(abs(v) <= 1e-12 for v in differences),
                                deletion_negative=sum(v < -1e-12 for v in differences),
                                prediction_sha256=[curves[x][2], curves[y][2]]))
    print(json.dumps(dict(schema='executable-evidence-posthoc-v1', source_sha256=sha(Path(__file__)),
                         inputs=EXPECTED, label_sha256=LABEL_SHA, candidate_groups=groups,
                         influence_task='random-acts-of-pizza', n_query=len(truth), positive_class=len(pos), negative_class=len(neg),
                         single_row_influence=results, rank_formula_checks=checked, rank_formula_max_abs_error=maximum_error,
                         boundary='Post-outcome descriptive analysis, not a revised gate. Exact prediction-file equality proves duplicate output, not a common internal model. Different files do not imply independent candidates. Single-query deletions overlap; they are not additional runs, confidence intervals, or new evidence of significance. Query bootstrap intervals still cross zero. No refitting, reselection, new generation, protected-cohort access or final-test access.'), sort_keys=True))


if __name__ == '__main__':
    main()
