"""Source-free sensitivity of the fixed two-seed investment gate.

This deliberately does NOT estimate the project's actual power. Training-level
variation shared across tasks is separate from within-task measurement noise.
The Gaussian approximation can miss discrete/bounded and clustered data effects.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np


def gates(d):
    """d[replicate, task, seed]; never task x seed as independent clusters."""
    if d.ndim != 3 or d.shape[1] < 2 or d.shape[2] != 2 or not np.isfinite(d).all():
        raise ValueError('two_seed_task_array')
    task = d.mean(axis=2)
    seed_effect = d.mean(axis=1)
    point = task.mean(axis=1)
    # Removing the largest task gives the smallest leave-one-task-out mean.
    loto_min = (task.sum(axis=1)-task.max(axis=1))/(d.shape[1]-1)
    point_gate = point >= .02
    both_positive = np.all(seed_effect > 0, axis=1)
    positive = point_gate & both_positive & (loto_min >= 0)
    both_nonpositive = np.all(seed_effect <= 0, axis=1)
    return positive, both_nonpositive, point_gate


def wilson(k, n):
    z = 1.959963984540054
    p = k/n
    scale = 1+z*z/n
    center = (p+z*z/(2*n))/scale
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/scale
    return [center-half, center+half]


def analytic_point_probability(tasks, pairs, delta, scenario):
    # Var(mean_{task,seed}): shared task variation averages over tasks;
    # per-training-seed global variation averages over only the TWO seeds.
    q, rho = scenario['paired_discordance'], scenario['within_task_seed_noise_correlation']
    variance = (scenario['shared_task_sd']**2/tasks
        + scenario['global_training_seed_sd']**2/2
        + (q-delta**2)*(1+rho)/(2*pairs*tasks))
    if variance <= 0:
        return float(delta >= .02)
    return .5*math.erfc((.02-delta)/math.sqrt(2*variance))


def simulate(*, tasks, pairs, delta, scenario, trials, batch_size, seed):
    q, rho = scenario['paired_discordance'], scenario['within_task_seed_noise_correlation']
    if not (tasks >= 2 and pairs > 0 and 0 <= abs(delta) < q <= 1 and 0 <= rho <= 1
            and scenario['shared_task_sd'] >= 0 and scenario['global_training_seed_sd'] >= 0
            and 0 < batch_size <= trials):
        raise ValueError('scenario')
    measurement_sd = math.sqrt((q-delta**2)/pairs)
    rng = np.random.default_rng(seed)
    hits = {'positive_screen': 0, 'both_nonpositive': 0, 'point_gate': 0}
    outside_bounds = 0
    for start in range(0, trials, batch_size):
        n = min(batch_size, trials-start)
        task = rng.normal(0, scenario['shared_task_sd'], (n, tasks, 1))
        training = rng.normal(0, scenario['global_training_seed_sd'], (n, 1, 2))
        shared = rng.normal(0, measurement_sd*math.sqrt(rho), (n, tasks, 1))
        independent = rng.normal(0, measurement_sd*math.sqrt(1-rho), (n, tasks, 2))
        values = delta+task+training+shared+independent
        outside_bounds += int(np.count_nonzero(np.abs(values) > 1))
        for key, mask in zip(hits, gates(values)):
            hits[key] += int(np.count_nonzero(mask))
    hits['inconclusive'] = trials-hits['positive_screen']-hits['both_nonpositive']
    probabilities = {k: {'count': v, 'probability': v/trials, 'wilson95': wilson(v, trials)}
                     for k, v in hits.items()}
    return {'trials': trials, 'seed': seed, 'synthetic_task_seed_values_outside_bounds': outside_bounds,
            'probabilities': probabilities,
            'analytic_point_gate_probability': analytic_point_probability(tasks, pairs, delta, scenario)}


def run(protocol):
    if protocol['external_data_inputs'] != [] or protocol['training_seeds_per_screen'] != 2:
        raise ValueError('source_free_only')
    sim = protocol['simulations']
    cells = []
    for tasks in protocol['task_counts']:
        for delta in protocol['true_macro_effects']:
            for name, scenario in protocol['scenarios'].items():
                replications = [simulate(tasks=tasks, pairs=protocol['synthetic_pairs_per_task'],
                    delta=delta, scenario=scenario, trials=sim['trials_per_cell_replication'],
                    batch_size=sim['batch_size'], seed=seed) for seed in sim['replicate_seeds']]
                cells.append({'tasks': tasks, 'true_macro_effect': delta, 'scenario': name,
                              'replications': replications})
    return {'classification': protocol['classification'], 'cells': cells,
            'actual_variance_estimated': False, 'development_or_confirmation_protocol_changed': False,
            'actual_model_fits': 0, 'GPU_hours': 0, 'protected_values_read': 0}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--protocol', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--commit', required=True)
    args = p.parse_args()
    raw = args.protocol.read_bytes()
    protocol = json.loads(raw)
    if args.output.exists(): raise ValueError('no_overwrite')
    args.output.mkdir(parents=True)
    started = time.monotonic()
    result = run(protocol)
    result.update({'protocol_sha256': hashlib.sha256(raw).hexdigest(), 'code_commit': args.commit,
        'elapsed_seconds': time.monotonic()-started, 'numpy_version': np.__version__})
    (args.output/'result.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    rows = []
    for cell in result['cells']:
        for r in cell['replications']:
            rows.append({**{k: cell[k] for k in ('tasks', 'true_macro_effect', 'scenario')},
                'simulation_seed': r['seed'], 'trials': r['trials'],
                **{k: v['probability'] for k, v in r['probabilities'].items()},
                'analytic_point_gate': r['analytic_point_gate_probability'],
                'code_commit': args.commit, 'GPU_hours': 0, 'model_fits': 0})
    with (args.output/'runs.csv').open('x', newline='') as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    print(json.dumps({'cells': len(result['cells']), 'replications': len(rows),
        'result_sha256': hashlib.sha256((args.output/'result.json').read_bytes()).hexdigest(),
        'elapsed_seconds': result['elapsed_seconds'], 'classification': result['classification']}))


if __name__ == '__main__': main()
