"""A1 -- mechanism: can a small hand-feature CHECKLIST reproduce what the frozen code-only probe reads?

Zero-GPU. From each card's code we extract ~16 legible ML-practice features (regex): model family, CV,
regularization, ensembling, hyperparam search, leakage guard, feature engineering, code size. We then
ask, on per-task 5-fold OOF:
  - does the checklist predict the true grade as well as the frozen probe?
  - does the checklist REPRODUCE the probe's ranking (Spearman vs probe output)?
  - does the probe carry signal BEYOND the checklist (residualize probe on checklist, still predict grade)?
Verdict feeds three decisions at once: paper mechanism (P2); whether generation-side steering can work
(if the probe just reads things the frozen model already does -> steering likely a no-op); whether SAE is
needed (only if the probe has large signal beyond the checklist).
"""
import re
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.b1_detector import _z, _spear, _dual_ridge

CACHE = "phase1/_cache_b1_feats.npz"
LAM = 3.0


def feats(code):
    c = code or ""
    def has(p):
        return 1.0 if re.search(p, c, re.I) else 0.0
    m = re.search(r"n_splits\s*=\s*(\d+)", c)
    return {
        "xgb": has(r"xgboost|xgb\.|XGB(Regressor|Classifier)"),
        "lgbm": has(r"lightgbm|lgb\.|LGBM(Regressor|Classifier)"),
        "catboost": has(r"catboost|CatBoost"),
        "sk_gbm": has(r"GradientBoosting|HistGradientBoosting"),
        "linear": has(r"LinearRegression|LogisticRegression|\bRidge\b|\bLasso\b|ElasticNet"),
        "nn": has(r"\btorch\b|tensorflow|keras|nn\.Module|Sequential\("),
        "rf": has(r"RandomForest|ExtraTrees"),
        "cv": has(r"KFold|StratifiedKFold|cross_val|cross_validate|TimeSeriesSplit|GroupKFold"),
        "n_folds": float(m.group(1)) if m else 0.0,
        "hp_search": has(r"optuna|GridSearchCV|RandomizedSearchCV|BayesSearch|hyperopt"),
        "ensemble": has(r"Voting(Classifier|Regressor)|Stacking(Classifier|Regressor)|blend|np\.average"),
        "n_fits": float(len(re.findall(r"\.fit\(", c))),
        "reg": has(r"early_stopping|reg_alpha|reg_lambda|max_depth|min_child|dropout|weight_decay|l1_ratio"),
        "leak_guard": has(r"Pipeline\(|ColumnTransformer|\.fit\(\s*X_train|\.fit\(\s*x_train"),
        "feat_eng": has(r"groupby|target_encod|TargetEncoder|get_dummies|OneHotEncoder|PolynomialFeatures|\.agg\("),
        "code_len": float(np.log(max(len(c), 1))),
        "n_lines": float(np.log(max(c.count("\n"), 1))),
        "n_imports": float(len(re.findall(r"(?m)^\s*(?:import |from )", c))),
    }


def ridge_oof(H, y, tasks, seed=0, folds=5):
    pred = np.full(len(y), np.nan)
    for t in np.unique(tasks):
        idx = np.where(tasks == t)[0]
        if len(idx) < folds + 2:
            continue
        order = np.random.default_rng(seed).permutation(idx)
        for f in np.array_split(order, folds):
            tr = np.setdiff1d(idx, f)
            mu = H[tr].mean(0); sd = H[tr].std(0); sd[sd < 1e-8] = 1.0
            Xtr = (H[tr] - mu) / sd; Xte = (H[f] - mu) / sd
            w = np.linalg.solve(Xtr.T @ Xtr + LAM * np.eye(Xtr.shape[1]), Xtr.T @ y[tr])
            pred[f] = Xte @ w
    return pred


def probe_oof(X, y, tasks, seed=0, folds=5):
    pred = np.full(len(y), np.nan)
    for t in np.unique(tasks):
        idx = np.where(tasks == t)[0]
        if len(idx) < folds + 2:
            continue
        order = np.random.default_rng(seed).permutation(idx)
        for f in np.array_split(order, folds):
            tr = np.setdiff1d(idx, f)
            pred[f] = _dual_ridge(X[tr], y[tr], X[f])
    return pred


def pts(pred, y, tasks):
    vals = [_spear(pred[tasks == t], y[tasks == t]) for t in np.unique(tasks)
            if (tasks == t).sum() >= 6 and not np.isnan(pred[tasks == t]).any()]
    return float(np.mean(vals)) if vals else float("nan")


def resid(a, b):
    """residual of a after regressing out b (per-task z), pooled."""
    b1 = np.column_stack([np.ones(len(b)), b])
    beta, *_ = np.linalg.lstsq(b1, a, rcond=None)
    return a - b1 @ beta


def main():
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))
    y = np.array([c.y for c in cards], float)
    tasks = np.array([c.task.name for c in cards])
    names = list(feats(cards[0].code).keys())
    H = np.array([[feats(c.code)[k] for k in names] for c in cards], float)
    print(f"N={len(cards)}, {H.shape[1]} hand features: {names}", flush=True)
    # prevalence of the binary practice flags
    print("\nprevalence of key practices (fraction of cards):", flush=True)
    for k in ["cv", "reg", "hp_search", "ensemble", "leak_guard", "feat_eng", "xgb", "lgbm", "nn"]:
        print(f"  {k:10s} {H[:, names.index(k)].mean():.2f}", flush=True)

    XA = np.load(CACHE)["XA"]
    yhat = probe_oof(XA, y, tasks)                       # frozen code-only probe
    h_y = ridge_oof(H, y, tasks)                         # checklist -> grade
    h_p = ridge_oof(H, yhat, tasks)                      # checklist -> probe output

    print("\n=== per-task 5-fold OOF Spearman ===", flush=True)
    print(f"  probe (frozen code-LLM)   vs true grade : {pts(yhat, y, tasks):+.3f}   <- H1's number", flush=True)
    print(f"  checklist (hand features) vs true grade : {pts(h_y, y, tasks):+.3f}   <- does a checklist predict grade?", flush=True)
    print(f"  checklist                 vs probe out  : {pts(h_p, yhat, tasks):+.3f}   <- does checklist REPRODUCE the probe?", flush=True)

    # does the probe read anything BEYOND the checklist?
    keep = ~np.isnan(yhat) & ~np.isnan(h_y)
    pr = np.full(len(y), np.nan)
    for t in np.unique(tasks):                            # residualize probe on checklist within task
        m = (tasks == t) & keep
        if m.sum() >= 6:
            pr[m] = resid(_z(yhat[m]), _z(h_y[m]))
    print(f"\n  probe residualized-vs-checklist, still predicts grade : {pts(pr, y, tasks):+.3f}", flush=True)
    print(f"  (>~0.15 => probe carries legible-beyond signal => SAE justified; ~0 => checklist captures it)", flush=True)

    # standardized coefficients: which practices drive grade
    mu = H.mean(0); sd = H.std(0); sd[sd < 1e-8] = 1.0
    Hs = (H - mu) / sd
    w = np.linalg.solve(Hs.T @ Hs + LAM * np.eye(Hs.shape[1]), Hs.T @ _z(y))
    order = np.argsort(-np.abs(w))
    print("\n=== top standardized coefficients (hand feature -> grade, all-data ridge) ===", flush=True)
    for i in order[:10]:
        print(f"  {names[i]:12s} {w[i]:+.3f}", flush=True)
    print("\n=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
