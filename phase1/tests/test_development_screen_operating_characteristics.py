import math

import numpy as np
import pytest

from phase1.development_screen_operating_characteristics import analytic_point_probability, gates, simulate


def scenario(**kw):
    return dict(paired_discordance=.2, shared_task_sd=.01,
                global_training_seed_sd=.005, within_task_seed_noise_correlation=.5, **kw)


def test_boundaries_and_nonpositive():
    x = np.array([[[.02, .02], [.02, .02]], [[0., 0.], [0., 0.]],
                  [[.06, -.01], [.06, -.01]], [[.2, .2], [-.1, -.1]]])
    pos, nonpos, point = gates(x)
    assert pos.tolist() == [True, False, False, False]
    assert nonpos.tolist() == [False, True, False, False]
    assert point.tolist() == [True, False, True, True]


def test_loto_independent_literal_deletion():
    rng = np.random.default_rng(18)
    x = rng.normal(.02, .04, (500, 7, 2))
    a, b, c = gates(x)
    for i, values in enumerate(x):
        mean = sum(float(v) for v in values.flat)/14
        seeds = [sum(float(v) for v in values[:, s])/7 for s in (0, 1)]
        loto = [np.delete(values, t, axis=0).mean() for t in range(7)]
        assert bool(a[i]) == (mean >= .02 and min(seeds) > 0 and min(loto) >= 0)
        assert bool(b[i]) == all(v <= 0 for v in seeds)
        assert bool(c[i]) == (mean >= .02)


def test_analytic_midpoint_and_training_variation_does_not_average_over_tasks():
    s = scenario()
    assert analytic_point_probability(6, 100, .02, s) == .5
    s['global_training_seed_sd'] = .02
    observed = analytic_point_probability(100000000, 100, 0., s)
    assert abs(observed - .5*math.erfc(1)) < 1e-7


def test_determinism_accounting_and_large_positive_control():
    kw = dict(tasks=6, pairs=100, delta=.15, scenario=scenario(), trials=1000, batch_size=100, seed=7)
    a = simulate(**kw); assert a == simulate(**kw)
    p = a['probabilities']
    assert sum(p[k]['count'] for k in ('positive_screen', 'both_nonpositive', 'inconclusive')) == 1000
    assert p['positive_screen']['probability'] > .99


@pytest.mark.parametrize('x', [np.zeros((2, 1, 2)), np.zeros((2, 3, 3)), np.full((2, 3, 2), np.nan)])
def test_bad_arrays(x):
    with pytest.raises(ValueError): gates(x)
