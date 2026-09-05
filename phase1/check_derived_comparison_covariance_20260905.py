"""Analytic counterexample, not corpus analysis, model fitting or BTL theorem.

z = theta + Gaussian endpoint noise; derived continuous observations are B z. A graph
Laplacian alone is not the information matrix when edges reuse this same z.
No files are read, no random draws or parameter fitting, no GPU/model imports.
"""
import itertools
import json
import argparse
import hashlib
from pathlib import Path

import numpy as np


def incidence(n, edges):
    b = np.zeros((len(edges), n))
    for row, (i, j) in enumerate(edges):
        b[row, i], b[row, j] = 1., -1.
    return b


def pinv(a):
    return np.linalg.pinv(a, rcond=1e-12, hermitian=True)


def fisher(b, sigma, mode):
    covariance = b @ sigma @ b.T
    if mode == "independent_edges":
        covariance = np.diag(np.diag(covariance))
    elif mode != "shared_endpoint_record":
        raise ValueError("unknown_noise_model")
    return b.T @ pinv(covariance) @ b


def mean_contrast_variance(info):
    covariance = pinv(info)
    values = []
    for i, j in itertools.combinations(range(len(info)), 2):
        contrast = np.eye(len(info))[i] - np.eye(len(info))[j]
        assert np.allclose(info @ covariance @ contrast, contrast, atol=1e-10)
        values.append(float(contrast @ covariance @ contrast))
    return float(np.mean(values))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    n = 4
    forest = incidence(n, [(0, 1), (1, 2), (2, 3)])
    complete = incidence(n, list(itertools.combinations(range(n), 2)))
    repeated = np.tile(forest, (20, 1))
    rows = []
    largest_invariance_error = 0.
    for noise_name, sigma in (("homoscedastic", np.eye(n)),
                              ("heteroscedastic", np.diag([.5, 1., 2., 4.]))):
        reference = fisher(forest, sigma, "shared_endpoint_record")
        for graph_name, b in (("forest", forest), ("complete", complete), ("forest_copied_20_times", repeated)):
            actual = fisher(b, sigma, "shared_endpoint_record")
            naive = fisher(b, sigma, "independent_edges")
            error = float(np.max(np.abs(actual - reference)))
            largest_invariance_error = max(largest_invariance_error, error)
            assert np.allclose(actual, reference, atol=1e-10, rtol=1e-10)
            expected = float(np.mean([sigma[i, i] + sigma[j, j] for i, j in itertools.combinations(range(n), 2)]))
            actual_variance = mean_contrast_variance(actual)
            assert abs(actual_variance - expected) < 1e-10
            rows.append({"endpoint_noise": noise_name, "graph": graph_name, "derived_rows": len(b),
                         "independent_execution_vectors": 1,
                         "naive_mean_contrast_variance": mean_contrast_variance(naive),
                         "covariance_aware_mean_contrast_variance": actual_variance,
                         "fisher_difference_from_forest": error})
        # A genuinely independent second vector z' doubles information. It is
        # not a second use of z, and incurs new execution measurements.
        before = mean_contrast_variance(reference)
        after = mean_contrast_variance(2 * reference)
        assert abs(after / before - .5) < 1e-10
        rows.append({"endpoint_noise": noise_name, "graph": "forest_two_independent_execution_vectors",
                     "derived_rows": 2 * len(forest), "independent_execution_vectors": 2,
                     "naive_mean_contrast_variance": None,
                     "covariance_aware_mean_contrast_variance": after,
                     "fisher_difference_from_forest": None})

    # Do not overgeneralize continuous-difference sufficiency to binary signs:
    # a > b and a > c do NOT reveal whether b > c. A derived third comparison
    # can add ordinal constraints despite using no new execution record.
    star = incidence(3, [(0, 1), (0, 2)])
    triangle = incidence(3, [(0, 1), (0, 2), (1, 2)])
    z1, z2 = np.array([3., 2., 1.]), np.array([3., 1., 2.])
    same_star_signs = bool(np.array_equal(np.sign(star @ z1), np.sign(star @ z2)))
    different_complete_signs = not np.array_equal(np.sign(triangle @ z1), np.sign(triangle @ z2))
    assert same_star_signs and different_complete_signs
    # Constant parent subtraction cannot improve scalar sibling ordering.
    for parent in (-5., 0., 7.):
        assert np.array_equal(np.sign(z1[:, None] - z1[None, :]),
                              np.sign((z1 - parent)[:, None] - (z1 - parent)[None, :]))
    result = {
        "classification": "ANALYTIC_COUNTEREXAMPLE_NOT_EMPIRICAL_EFFECT",
        "noise_model": "z=theta+epsilon, epsilon~N(0,Sigma); continuous differences Bz have covariance=B Sigma B^T",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "numpy": np.__version__, "cases": rows,
        "largest_covariance_aware_fisher_invariance_error": largest_invariance_error,
        "ordinal_control": {"forest_signs_do_not_determine_full_signs": True,
                            "same_independent_execution_count": True},
        "parent_subtraction_control": "same-parent subtraction preserves sibling ranking",
        "scope": {"real_data_read": False, "model_fits": 0, "gpu_jobs": 0,
                  "bt_binary_efficiency_theorem_claimed": False,
                  "full_global_comparisons_declared_useless": False},
    }
    raw = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(raw)
    print(raw, end="")


if __name__ == "__main__":
    main()
