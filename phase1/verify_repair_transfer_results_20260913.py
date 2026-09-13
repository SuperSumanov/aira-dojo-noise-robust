"""Independent arithmetic over the closed public T1 export; no private data access.

Does not import the selection, worker, or primary reader. The paired sign test is
an additional descriptive check, not a replacement for the frozen development gate.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics


ARMS = ('no_external_memory', 'retrieved_repair', 'random_repair')
TASKS = ('leaf-classification', 'spaceship-titanic')


def check(condition, message):
    if not condition:
        raise ValueError(message)


def near(a, b):
    return a is b if a is None or b is None else math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10)


def compare(rows, control):
    paired = {(r['case'], r['arm']): r for r in rows}
    differences = []
    for case in sorted({r['case'] for r in rows}):
        a, b = (paired[case, arm]['repair_success'] for arm in ('retrieved_repair', control))
        if a is not None and b is not None:
            differences.append(int(a) - int(b))
    counts = Counter(differences)
    wins, losses = counts[1], counts[-1]
    discordant = wins + losses
    p = min(1.0, 2 * sum(math.comb(discordant, k) for k in range(min(wins, losses) + 1)) / 2 ** discordant)
    return dict(right=control, planned_pairs=len(rows)//3, known_pairs=len(differences),
                unknown_pairs=len(rows)//3-len(differences), wins=wins, losses=losses,
                ties=counts[0], mean_paired_success_difference=statistics.mean(differences) if differences else None,
                descriptive_two_sided_sign_p=p)


def verify(directory):
    closure = json.loads((directory/'readout-finished.json').read_text())
    hashes = {}
    for filename, key in (('summary.json', 'summary_sha256'), ('runs.csv', 'csv_sha256')):
        hashes[filename] = hashlib.sha256((directory/filename).read_bytes()).hexdigest()
        check(hashes[filename] == closure[key], filename+' closure hash')
    summary = json.loads((directory/'summary.json').read_text())
    rows = summary['rows']
    check(len(rows) == 24 and {r['index'] for r in rows} == set(range(24)), '24 planned unique rows')
    check({r['case'] for r in rows} == set(range(8)), '8 planned cases')
    check({r['task'] for r in rows} == set(TASKS), 'fixed tasks')
    check(len({(r['case'], r['arm']) for r in rows}) == 24, 'unique paired arm')
    for case in range(8):
        group = [r for r in rows if r['case'] == case]
        check({r['arm'] for r in group} == set(ARMS), 'complete three-arm case')
        check(len({(r['task'], r['seed'], r['target_code_sha256']) for r in group}) == 1, 'shared target/seed')
    for r in rows:
        check(r['repair_success'] is None or type(r['repair_success']) is bool, 'success type')
        expected = None if r['status'] in ('infrastructure_error', 'not_executed') else r['status'] == 'valid'
        check(r['repair_success'] is expected, 'fixed failure/unknown rule')
        check(math.isfinite(r['score']) if expected is True else r['score'] is None, 'score eligibility')
    with (directory/'runs.csv').open(newline='') as f:
        csv_rows = list(csv.DictReader(f))
    check(len(csv_rows) == len(rows), 'CSV denominator')
    for expected, observed in zip(rows, csv_rows):
        check(set(expected) == set(observed), 'CSV columns')
        check(all(observed[k] == ('' if v is None else str(v)) for k, v in expected.items()), 'CSV exact values/order')
    for task in TASKS:
        for arm in ARMS:
            group = [r for r in rows if (r['task'], r['arm']) == (task, arm)]
            check(len(group) == 4, 'four cases per task/arm')
            entries = [g for g in summary['groups'] if (g['task'], g['arm']) == (task, arm)]
            check(len(entries) == 1, 'one group summary')
            g = entries[0]
            success = sum(r['repair_success'] is True for r in group)
            failure = sum(r['repair_success'] is False for r in group)
            unknown = sum(r['repair_success'] is None for r in group)
            check((g['planned'], g['success'], g['known_failure'], g['unknown']) == (4, success, failure, unknown), 'group counts')
            check(near(g['conservative_success_fraction'], success/4), 'fixed denominator success')
            scores = [r['score'] for r in group if r['repair_success'] is True]
            check(near(g['conditional_score_median'], statistics.median(scores) if scores else None), 'score median')
            check(near(g['conditional_score_sample_sd'], statistics.stdev(scores) if len(scores)>1 else None), 'score SD')
            for output, field in (('api_cost_usd','cost_usd'), ('generation_seconds','generation_seconds'), ('execution_wall_seconds','execution_wall_seconds')):
                check(near(g[output], math.fsum(r[field] or 0 for r in group)), output)
    comparisons = [compare(rows, arm) for arm in ('no_external_memory', 'random_repair')]
    task_comparisons = [dict(task=task, **compare([r for r in rows if r['task']==task], arm)) for task in TASKS for arm in ('no_external_memory', 'random_repair')]
    for computed, originals in ((comparisons, summary['comparisons']), (task_comparisons, summary['task_comparisons'])):
        check(len(computed) == len(originals), 'comparison cardinality')
        for c, original in zip(computed, originals):
            for k, v in c.items():
                if k != 'descriptive_two_sided_sign_p':
                    check(near(v, original[k]) if isinstance(v, (int,float)) or v is None else v == original[k], 'paired '+k)
    gate = all(c['unknown_pairs']==0 and c['wins']>c['losses'] for c in comparisons) and all(c['wins']>=c['losses'] for c in task_comparisons)
    check(gate is summary['development_expansion_gate'], 'unchanged development gate')
    same_memory = []
    for case in range(8):
        pair = [r for r in rows if r['case']==case and r['arm'] in ('retrieved_repair','random_repair')]
        if pair[0]['memory_diff_sha256'] == pair[1]['memory_diff_sha256']:
            same_memory.append(dict(case=case, same_code=pair[0]['generated_code_sha256']==pair[1]['generated_code_sha256'], same_success=pair[0]['repair_success'] is pair[1]['repair_success']))
    return dict(verified=True, hashes=hashes, planned=24, cases=8, comparisons=comparisons,
                task_comparisons=task_comparisons, development_expansion_gate=gate,
                same_memory_cases=same_memory, api_cost_usd=math.fsum(r['cost_usd'] or 0 for r in rows),
                caveat='Independent public arithmetic, not a second execution, learning-integrity audit, multiplicity-adjusted test, or confirmatory e2e evidence.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    result = verify(args.directory)
    with (args.directory/'independent-arithmetic.json').open('x') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps(result, ensure_ascii=False))
