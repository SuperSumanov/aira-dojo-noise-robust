"""Four-fit development-screen statistics, not a confirmation or unseal tool.

No files, checkpoint loaders, selection or model fitting. Callers must pin all
four final checkpoints and the same-pair predictions before supplying admitted
development labels. This kernel cannot certify that provenance or timing.
The original five-arm, three-seed hierarchy remains a separate implementation.
"""
from collections import defaultdict
from fractions import Fraction
import math

from phase1.g_reuse_effect_readout_statistics import bootstrap, credit, is_sha, require


FULL = 'G-reuse-to-L-full'
SEEDS = (6, 7)
ARMS = ('Lbudget', FULL)
KEYS = {f'{arm}|{seed}' for arm in ARMS for seed in SEEDS}|{'tfidf'}
ROW_KEYS = {'pair_sha256', 'task_sha256', 'parent_sha256', 'run_sha256', 'truth_sign', 'margins'}
PROTOCOL_SHA256 = 'd599bbc74c7ca93f970bc5eb746e099f6edcba29f10d176307d6482f0bfdff59'


def validate(rows, *, protocol_sha256):
    require(protocol_sha256 == PROTOCOL_SHA256, 'development_protocol_drift')
    require(type(rows) is list and len(rows) > 0, 'development_empty_rows')
    seen = set(); tasks = set(); run_task = {}; parent_context = {}
    for row in rows:
        require(type(row) is dict and set(row) == ROW_KEYS, 'development_row_schema')
        require(all(is_sha(row[key]) for key in ROW_KEYS-{'truth_sign', 'margins'}), 'development_identity_shape')
        pair, task, run, parent = (row[k] for k in ('pair_sha256', 'task_sha256', 'run_sha256', 'parent_sha256'))
        require(pair not in seen, 'development_duplicate_pair')
        seen.add(pair); tasks.add(task)
        require(run_task.setdefault(run, task) == task, 'development_run_cross_task')
        require(parent_context.setdefault(parent, (run, task)) == (run, task), 'development_parent_cross_run')
        require(type(row['truth_sign']) is int and row['truth_sign'] in (-1, 1), 'development_truth_sign')
        require(type(row['margins']) is dict and set(row['margins']) == KEYS, 'development_same_pool_matrix')
        require(all(type(x) in (int, float) and math.isfinite(float(x)) for x in row['margins'].values()),
                'development_finite_margin')
    require(len(tasks) >= 2, 'development_task_support')


def comparison(grouped, right, name):
    task_seed = {}; task_effect = {}; accuracies = {}
    for task in sorted(grouped):
        rows = grouped[task]
        exact = {key: Fraction(sum(int(2*credit(r['margins'][key], r['truth_sign'])) for r in rows), 2*len(rows))
                 for key in sorted(KEYS)}
        accuracies[task] = {key: float(value) for key, value in exact.items()}
        task_seed[task] = {str(seed): exact[f'{FULL}|{seed}']-
            exact['tfidf' if right == 'tfidf' else f'{right}|{seed}'] for seed in SEEDS}
        task_effect[task] = sum(task_seed[task].values())/len(SEEDS)
    tasks = sorted(grouped)
    seed_effects = {str(s): float(sum(task_seed[t][str(s)] for t in tasks)/len(tasks)) for s in SEEDS}
    point = float(sum(task_effect.values())/len(tasks))
    loto = {t: float(sum(task_effect[x] for x in tasks if x != t)/(len(tasks)-1)) for t in tasks}
    return {'point': point, 'seed_effects': seed_effects,
        'task_clustered_descriptive_ci95': bootstrap({t: float(x) for t, x in task_effect.items()}, comparison=name, seed=20260905, replicates=20000),
        'loto_minimum': min(loto.values()),
        'per_task': [{'task_sha256': t, 'pairs': len(grouped[t]), 'effect': float(task_effect[t]),
            'seed_effects': {s: float(x) for s, x in task_seed[t].items()}, 'accuracies': accuracies[t],
            'effect_without_task': loto[t]} for t in tasks]}


def evaluate_development(rows, *, protocol_sha256, fit_status):
    """Descriptive screen only; statuses do not admit or authenticate inputs."""
    validate(rows, protocol_sha256=protocol_sha256)
    require(type(fit_status) is dict and set(fit_status) == KEYS-{'tfidf'}, 'development_fit_coverage')
    require(all(value == 'COMPLETED' for value in fit_status.values()), 'development_incomplete_fit_not_effect')
    grouped = defaultdict(list)
    for row in sorted(rows, key=lambda r: r['pair_sha256']): grouped[row['task_sha256']].append(row)
    primary = comparison(grouped, 'Lbudget', 'full_minus_lbudget')
    tfidf = comparison(grouped, 'tfidf', 'full_minus_tfidf')
    seeds = list(primary['seed_effects'].values())
    positive = all(x > 0 for x in seeds) and primary['point'] >= .02 and primary['loto_minimum'] >= 0
    decision = ('POSITIVE_DEVELOPMENT_SCREEN_ONLY' if positive else
                'BOTH_SEEDS_NONPOSITIVE_NO_ESCALATION' if all(x <= 0 for x in seeds) else
                'INCONCLUSIVE_NO_AUTOMATIC_EXPANSION')
    return {'classification': 'DEVELOPMENT_SCREEN_NOT_CONFIRMATORY', 'protocol_sha256': protocol_sha256,
        'pairs': len(rows), 'tasks': len(grouped), 'training_seeds': list(SEEDS),
        'primary_full_minus_lbudget': primary, 'descriptive_full_minus_tfidf': tfidf,
        'decision': decision, 'confirmatory_claim_allowed': False, 'automatic_gpu_expansion_allowed': False,
        'source_and_checkpoint_admission_verified_by_statistics': False,
        'note': 'Two training seeds are not extra task clusters. A positive screen is investment evidence, not mechanism/scaling/search utility.'}
