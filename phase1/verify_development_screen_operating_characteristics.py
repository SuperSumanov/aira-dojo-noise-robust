"""Independently check counts, Monte Carlo error and the marginal analytic gate.

Does not import or rerun the simulator. No real data or protected files.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist


def require(x, reason):
    if not x: raise ValueError(reason)


def close(a, b):
    return math.isfinite(a) and math.isfinite(b) and abs(a-b) < 1e-12


def verify(protocol_path, result_path):
    protocol_raw = protocol_path.read_bytes()
    p = json.loads(protocol_raw); raw = result_path.read_bytes(); r = json.loads(raw)
    require(r['protocol_sha256'] == hashlib.sha256(protocol_raw).hexdigest(), 'protocol_hash')
    require(r['classification'] == p['classification'] and r['actual_variance_estimated'] is False
            and r['development_or_confirmation_protocol_changed'] is False, 'classification')
    require(r['actual_model_fits'] == r['GPU_hours'] == r['protected_values_read'] == 0, 'resources')
    expected = {(t, d, s) for t in p['task_counts'] for d in p['true_macro_effects'] for s in p['scenarios']}
    seen = set(); analytic_errors = []; replication_errors = []; half_widths = []
    for cell in r['cells']:
        key = cell['tasks'], cell['true_macro_effect'], cell['scenario']
        require(key in expected and key not in seen, 'matrix'); seen.add(key)
        t, d, name = key; s = p['scenarios'][name]; n = p['synthetic_pairs_per_task']
        # Sum covariance contributions before dividing by the squared 2*T terms.
        measurement_variance = (s['paired_discordance']-d*d)/n
        sum_variance = (4*t*s['shared_task_sd']**2
            + 2*t*t*s['global_training_seed_sd']**2
            + 2*t*measurement_variance*(1+s['within_task_seed_noise_correlation']))
        standard_error = math.sqrt(sum_variance)/(2*t)
        point_probability = NormalDist(mu=d, sigma=standard_error).cdf(2*d-.02)
        rep = cell['replications']; require(len(rep) == 2, 'replication_count')
        for index, row in enumerate(rep):
            require(row['seed'] == p['simulations']['replicate_seeds'][index]
                    and row['trials'] == p['simulations']['trials_per_cell_replication'], 'simulation_identity')
            require(row['synthetic_task_seed_values_outside_bounds'] == 0, 'gaussian_bound_excursion')
            prob = row['probabilities']; trials = row['trials']
            require(set(prob) == {'positive_screen', 'both_nonpositive', 'point_gate', 'inconclusive'}, 'categories')
            require(sum(prob[k]['count'] for k in ('positive_screen', 'both_nonpositive', 'inconclusive')) == trials,
                    'partition_count')
            require(prob['positive_screen']['count'] <= prob['point_gate']['count'], 'subset_gate')
            for x in prob.values():
                k = x['count']; require(type(k) is int and 0 <= k <= trials, 'count')
                estimate = k/trials
                require(close(estimate, x['probability']), 'ratio')
                z2 = NormalDist().inv_cdf(.975)**2
                # Wilson bounds are the roots of the inverted score quadratic.
                aa = trials+z2; bb = -(2*k+z2); cc = k*k/trials
                discriminant = max(0., bb*bb-4*aa*cc)
                low = (-bb-math.sqrt(discriminant))/(2*aa)
                high = (-bb+math.sqrt(discriminant))/(2*aa)
                require(close(low, x['wilson95'][0]) and close(high, x['wilson95'][1]), 'wilson')
                half_widths.append((high-low)/2)
            require(close(row['analytic_point_gate_probability'], point_probability), 'analytic_formula')
            analytic_errors.append(abs(prob['point_gate']['probability']-point_probability))
        for category in rep[0]['probabilities']:
            replication_errors.append(abs(rep[0]['probabilities'][category]['probability']
                                          -rep[1]['probabilities'][category]['probability']))
    require(seen == expected, 'complete_matrix')
    gates = p['verification']
    require(max(analytic_errors) <= gates['point_gate_vs_analytic_absolute_tolerance'], 'analytic_mc_gate')
    require(max(replication_errors) <= gates['replication_probability_difference_tolerance'], 'replication_gate')
    require(max(half_widths) <= gates['maximum_mc_wilson_half_width'], 'mc_precision')
    return {'classification': p['classification'], 'verification_pass': True, 'cells': len(seen),
        'max_point_mc_analytic_error': max(analytic_errors), 'max_replication_difference': max(replication_errors),
        'max_mc_wilson_half_width': max(half_widths), 'result_sha256': hashlib.sha256(raw).hexdigest(),
        'protocol_sha256': hashlib.sha256(protocol_raw).hexdigest(), 'actual_power_estimated': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    r = verify(args.protocol, args.result)
    with args.output.open('x') as f: json.dump(r, f, indent=2, sort_keys=True)
    print(json.dumps(r, sort_keys=True))


if __name__ == '__main__': main()
