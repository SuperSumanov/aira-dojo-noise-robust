# Harness extension for the T1 main-line 3-arm evaluation-consistency experiment.
"""HCE externalized D_search / D_val evaluation.

Partitions the competition's *private* answers into D_search / D_val / D_test (fixed per task,
seeded by ``hce_split_seed``; identical across arms and run-seeds). Computes the search-time
fitness on D_search per arm:

  - ``full``        : score on the entire D_search                    (clean reference / ceiling)
  - ``naive``       : score on ONE cheap proxy subsample of D_search  (poor-compute naive baseline)
  - ``consistency`` : k cheap proxy subsamples -> mean -/+ lambda*std (proposed: variance-aware)

The variance penalty sign flips for lower-is-better metrics (instability is penalised either way).

Only the eval/selection protocol differs across arms; the solver and operators are untouched, so
the fairness contract holds. D_test is NEVER graded during the experiment.
"""
import numpy as np


def make_hce_split(n, search_frac, val_frac, split_seed):
    """Deterministic D_search/D_val/D_test partition of ``n`` answer rows (positions)."""
    n = int(n)
    rng = np.random.default_rng(int(split_seed))
    perm = rng.permutation(n)
    ns = int(round(n * float(search_frac)))
    nv = int(round(n * float(val_frac)))
    return {
        "search": np.sort(perm[:ns]),
        "val": np.sort(perm[ns:ns + nv]),
        "test": np.sort(perm[ns + nv:]),
    }


def _align_submission(submission_df, answers):
    """Reorder submission rows to match answers' row order, keyed by the first (id) column.

    After alignment, row position i of the returned frame corresponds to row i of ``answers`` for
    BOTH id-merge graders (e.g. accuracy) and positional graders (e.g. nomad RMSLE)."""
    id_col = answers.columns[0]
    if id_col in submission_df.columns:
        return submission_df.set_index(id_col).reindex(answers[id_col]).reset_index()
    return submission_df.reset_index(drop=True)


def grade_subset(grader, aligned_submission, answers, idx):
    """Grade the (id-aligned) submission against answers restricted to positions ``idx``.

    Returns a float, or None if the grader rejects the subset (degenerate/invalid)."""
    a_sub = answers.iloc[idx].reset_index(drop=True)
    s_sub = aligned_submission.iloc[idx].reset_index(drop=True)
    score = grader(s_sub, a_sub)  # mlebench Grader.__call__ -> rounded float, or None on invalid
    return None if score is None else float(score)


def _categorical_target(answers):
    """Heuristic: a single non-id column with few unique values => classification (stratify)."""
    tcols = list(answers.columns[1:])
    if len(tcols) == 1 and answers[tcols[0]].nunique(dropna=True) <= 20:
        return tcols[0]
    return None


def _proxy_subsample(idx, frac, answers, rng):
    """A cheap proxy subsample of D_search positions. Stratified by label for classification so
    AUC/accuracy stay well-defined, while still injecting 'lucky-sample' eval noise."""
    idx = np.asarray(idx)
    n = max(2, int(round(len(idx) * float(frac))))
    tcol = _categorical_target(answers)
    if tcol is not None:
        labs = answers.iloc[idx][tcol].to_numpy()
        classes = np.unique(labs)
        per = max(1, n // len(classes))
        picks = []
        for c in classes:
            pool = idx[labs == c]
            if len(pool):
                picks.append(rng.choice(pool, min(per, len(pool)), replace=False))
        if picks:
            return np.sort(np.concatenate(picks))
    return np.sort(rng.choice(idx, n, replace=False))


def dsearch_fitness(grader, submission_df, answers, split, arm,
                    proxy_frac=0.1, k=3, lam=1.0, maximize=True, eval_seed=0):
    """Compute the search-time fitness on D_search for the given arm.

    Returns ``(fitness_or_None, info)``; ``fitness`` is the value the search selects on."""
    aligned = _align_submission(submission_df, answers)
    sidx = np.asarray(split["search"])
    rng = np.random.default_rng([int(x) for x in np.atleast_1d(eval_seed)])

    if arm == "full":
        v = grade_subset(grader, aligned, answers, sidx)
        return v, {"arm": "full", "raw": ([] if v is None else [v]), "mean": v, "std": 0.0}

    def one_proxy():
        for _ in range(5):  # resample guard against degenerate subsets (e.g. one-class AUC)
            sub = _proxy_subsample(sidx, proxy_frac, answers, rng)
            s = grade_subset(grader, aligned, answers, sub)
            if s is not None:
                return s
        return None

    if arm == "naive":
        v = one_proxy()
        return v, {"arm": "naive", "raw": ([] if v is None else [v]), "mean": v, "std": 0.0}

    if arm == "consistency":
        raw = [r for r in (one_proxy() for _ in range(int(k))) if r is not None]
        if not raw:
            return None, {"arm": "consistency", "raw": [], "mean": None, "std": None}
        mean = float(np.mean(raw))
        std = float(np.std(raw))
        fit = (mean - lam * std) if maximize else (mean + lam * std)
        return float(fit), {"arm": "consistency", "raw": raw, "mean": mean, "std": std, "lambda": float(lam)}

    raise ValueError(f"unknown HCE arm: {arm}")
