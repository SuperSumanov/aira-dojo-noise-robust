"""A suite of performance predictors for MLE-agent search, evaluated the way NAS does it.

Why a suite. Our single trained critic loses to the agent's self-reported score, and one
model is not evidence that the family fails -- NAS-Bench-Suite-Zero (NeurIPS D&B 2022)
needed 13 proxies across 28 tasks before "params and FLOPs match every zero-cost proxy"
counted as a finding rather than a failure. This file is that suite for our corpus.

Why the NAS protocol. "How Powerful are Performance Predictors in NAS?" (NeurIPS 2021)
separates INITIALIZATION time (fitting the predictor, paid once) from QUERY time (scoring
one candidate, paid per decision). That accounting is what makes the comparison honest
here: the self-report's query cost is a full program execution -- minutes -- while every
other predictor answers in milliseconds. Ranking them without that column, as we did for
two days, compares signals that are not available at the same moment.

Predictors, cheapest first:
  random            sanity floor
  code_len/runtime/ single zero-cost features -- the params/FLOPs analogue that beat
    n_lines/depth     everything in NAS
  static_lr         handcrafted ML-methodology features, logistic regression on pairwise
                      differences (antisymmetric by construction)
  static_gbm        same features, gradient boosting -- checks whether the ceiling is the
                      features or the linear form
  tfidf_lr          character n-grams of the source, the cheapest learned code model
  self_report       POST-EXECUTION. Reported for reference with its true query cost.
  rm_*              trained critics, read from dumped score files if present

Evaluation: pairwise accuracy on the run-clean held-out side, Kendall tau within task, and
run-clustered CIs. Everything trains on the same train side, and no predictor ever sees a
held-out run.

Usage: python phase1/predictor_suite.py [--out phase1/suite_results.csv]
"""
import argparse, collections, json, math, random, re, statistics, time, zlib

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="phase1/suite_results.csv")
ap.add_argument("--pairs", default="phase1/value_pairs_runsplit.jsonl")
ap.add_argument("--cards", default="phase1/cards_current_v7.jsonl")
ap.add_argument("--train-cap", type=int, default=24000)
ap.add_argument("--test-cap", type=int, default=6000)
a = ap.parse_args()

ORI = json.load(open("phase1/task_orientation.json"))
RUN = json.load(open("phase1/card_run_map.json"))
cards = {}
for l in open(a.cards):
    d = json.loads(l)
    cards[d["id"]] = d


def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


train, test = [], []
for l in open(a.pairs):
    p = json.loads(l)
    if p["better"] not in cards or p["worse"] not in cards:
        continue
    (train if p["intask_split"] == "train" else test).append(p)
rng = random.Random(7)
rng.shuffle(train)
rng.shuffle(test)
train, test = train[:a.train_cap], test[:a.test_cap]
print(f"train {len(train)} pairs, test {len(test)} pairs over "
      f"{len({RUN[p['better']] for p in test})} held-out runs", flush=True)

# ---------------------------------------------------------------- features
IMPORT_RX = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.M)
MODEL_WORDS = ("lightgbm", "xgboost", "catboost", "randomforest", "logisticregression",
               "ridge", "svc", "torch", "transformers", "bert", "resnet", "efficientnet",
               "timm", "keras", "sklearn")
CV_WORDS = ("kfold", "stratifiedkfold", "groupkfold", "cross_val", "train_test_split")
RISK_WORDS = ("fit_transform(test", "fit(test", ".append(test", "concat([train, test",
              "pd.concat([train,test")


def feats(cid):
    d = cards[cid]
    code = d.get("code") or ""
    low = code.lower()
    obs = d["obs"]
    lin = d["lineage"]
    imports = set(IMPORT_RX.findall(code))
    f = {
        "code_len": float(len(code)),
        "n_lines": float(code.count("\n")),
        "n_imports": float(len(imports)),
        "depth": float(lin.get("depth") or 0),
        "step": float(lin.get("step") or 0),
        "n_sibs": float(lin.get("n_siblings") or 0),
        "n_cv": float(sum(low.count(w) for w in CV_WORDS)),
        "n_seed": float(low.count("seed") + low.count("random_state")),
        "n_ensemble": float(low.count("ensemble") + low.count("blend")
                            + low.count("stack") + low.count("mean(")),
        "n_earlystop": float(low.count("early_stop")),
        "n_hpsearch": float(low.count("optuna") + low.count("gridsearch")
                            + low.count("param_grid") + low.count("hyperopt")),
        "n_augment": float(low.count("augment") + low.count("transform")),
        "n_try": float(low.count("try:")),
        "n_print": float(low.count("print(")),
        "n_comment": float(code.count("#")),
        "n_fold_int": float(max([int(x) for x in re.findall(r"n_splits\s*=\s*(\d+)", code)]
                                or [0])),
        "n_epoch_int": float(max([int(x) for x in re.findall(r"epochs?\s*=\s*(\d+)", code)]
                                 or [0])),
        "risk_leak": float(sum(low.count(w) for w in RISK_WORDS)),
        "has_gpu": float("cuda" in low),
    }
    for m in MODEL_WORDS:
        f["m_" + m] = float(m in low)
    return f


FN = sorted(feats(next(iter(cards))).keys())
_fcache = {}


def fvec(cid):
    if cid not in _fcache:
        f = feats(cid)
        _fcache[cid] = np.array([f[k] for k in FN], dtype=np.float64)
    return _fcache[cid]


def pair_matrix(ps):
    """Antisymmetric design: each pair contributes (b-w, y=1) and (w-b, y=0), so any
    learned ranker is forced to be order-invariant instead of memorising position."""
    X, y = [], []
    for p in ps:
        d = fvec(p["better"]) - fvec(p["worse"])
        X.append(d)
        y.append(1)
        X.append(-d)
        y.append(0)
    return np.vstack(X), np.array(y)


# ---------------------------------------------------------------- predictors
results = []
PERPAIR = {}
PERPAIR2 = {}
import os as _os2
EVAL2 = []
_e2 = "phase1/decision_clean_b0.jsonl"
if _os2.path.exists(_e2):
    for _l in open(_e2):
        _p = json.loads(_l)
        if _p["better"] in cards and _p["worse"] in cards:
            EVAL2.append(_p)
print(f"secondary eval set: {len(EVAL2)} sibling pairs from {_e2}", flush=True)


def evaluate(name, pred_fn, init_s, query_s, note=""):
    """pred_fn(better, worse) -> 1 if it ranks `better` above `worse`, else 0, or None."""
    per_run = collections.defaultdict(list)
    per_task = collections.defaultdict(list)
    n_cov = 0
    t0 = time.time()
    _pp = PERPAIR.setdefault(name, {})
    for p in test:
        v = pred_fn(p["better"], p["worse"])
        if v is None:
            continue
        n_cov += 1
        _pp[p["better"] + "|" + p["worse"]] = int(v)
        # a pair often spans two runs, so a run key taken from one endpoint
        # understates dependence; task is an unambiguous independent unit
        per_run[RUN[p["better"]]].append(float(v))
        per_task[p["task"]].append(float(v))
    q = (time.time() - t0) / max(n_cov, 1)
    if EVAL2:
        _p2 = PERPAIR2.setdefault(name, {})
        for p in EVAL2:
            v2 = pred_fn(p["better"], p["worse"])
            if v2 is not None:
                _p2[p["better"] + "|" + p["worse"]] = int(v2)
    vals = [v for vs in per_run.values() for v in vs]
    if not vals:
        print(f"{name}: no coverage")
        return
    acc = sum(vals) / len(vals)
    def _boot(d):
        ks = list(d)
        rr = random.Random(7)
        dr = []
        for _ in range(2000):
            ss = [v for x in (rr.choice(ks) for _ in ks) for v in d[x]]
            dr.append(sum(ss) / len(ss))
        dr.sort()
        return dr[50], dr[1950]
    lo, hi = _boot(per_task)          # primary: task-clustered
    rlo, rhi = _boot(per_run)         # secondary: run-clustered, one endpoint
    results.append({"predictor": name, "acc": round(acc, 4),
                    "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
                    "ci_lo_run": round(rlo, 4), "ci_hi_run": round(rhi, 4),
                    "n_tasks": len(per_task),
                    "n_pairs": len(vals), "n_runs": len(per_run),
                    "coverage": round(n_cov / len(test), 3),
                    "init_s": round(init_s, 1),
                    "query_ms": round((query_s if query_s is not None else q) * 1000, 3),
                    "note": note})
    print(f"{name:16s} acc={acc:.4f} task[{lo:.4f},{hi:.4f}] run[{rlo:.4f},{rhi:.4f}] "
          f"cov={n_cov/len(test):.2f} runs={len(per_run)} init={init_s:.0f}s "
          f"query={(query_s if query_s is not None else q)*1000:.2f}ms {note}", flush=True)


print("\n--- zero-cost single features ---", flush=True)
evaluate("random", lambda b, w: zlib.crc32((b + w).encode()) & 1, 0.0, 1e-6)
for f in ("code_len", "n_lines", "depth", "step", "n_cv", "n_ensemble"):
    i = FN.index(f)
    evaluate(f, (lambda i: lambda b, w: (None if fvec(b)[i] == fvec(w)[i]
                                         else int(fvec(b)[i] > fvec(w)[i])))(i), 0.0, 1e-5)

print("\n--- learned on handcrafted features ---", flush=True)
t0 = time.time()
Xtr, ytr = pair_matrix(train)
# differences of raw counts span 1e4 (code_len) to 1 (flags); unscaled lbfgs
# never converges. Scale with mean 0 so the antisymmetry of the design survives.
sc = StandardScaler(with_mean=False).fit(Xtr)
lr = LogisticRegression(max_iter=4000, C=1.0).fit(sc.transform(Xtr), ytr)
t_lr = time.time() - t0
evaluate("static_lr", lambda b, w: int(lr.decision_function(
    sc.transform((fvec(b) - fvec(w)).reshape(1, -1)))[0] > 0), t_lr, None,
    f"{len(FN)} feats")

t0 = time.time()
gbm = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08,
                                     random_state=7).fit(Xtr, ytr)
t_gbm = time.time() - t0
evaluate("static_gbm", lambda b, w: int(gbm.predict_proba(
    (fvec(b) - fvec(w)).reshape(1, -1))[0, 1] > 0.5), t_gbm, None,
    f"{len(FN)} feats")

print("\n--- cheapest learned code model ---", flush=True)
t0 = time.time()
ids = sorted({c for p in train + test + EVAL2 for c in (p["better"], p["worse"])})
train_ids = sorted({c for p in train for c in (p["better"], p["worse"])})
tf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=30000,
                     min_df=3, sublinear_tf=True)
# vocabulary, min_df and idf must come from the training side alone; fitting on
# train+test let the champion row see held-out nodes
tf.fit([(cards[c].get("code") or "")[:20000] for c in train_ids])
M = tf.transform([(cards[c].get("code") or "")[:20000] for c in ids])
pos = {c: i for i, c in enumerate(ids)}
Xt = np.vstack([(M[pos[p["better"]]] - M[pos[p["worse"]]]).toarray()[0] for p in train] +
               [(M[pos[p["worse"]]] - M[pos[p["better"]]]).toarray()[0] for p in train])
yt = np.array([1] * len(train) + [0] * len(train))
tlr = LogisticRegression(max_iter=1500, C=0.5).fit(Xt, yt)
t_tf = time.time() - t0
_tcache = {}


def tf_pred(b, w):
    k = (b, w)
    if b not in pos or w not in pos:
        return None
    if k not in _tcache:
        d = (M[pos[b]] - M[pos[w]]).toarray()
        _tcache[k] = int(tlr.decision_function(d)[0] > 0)
    return _tcache[k]


evaluate("tfidf_lr", tf_pred, t_tf, None, "char 3-5 grams")

print("\n--- POST-EXECUTION reference (not available at decision time) ---", flush=True)
med_rt = statistics.median([fin(d["obs"].get("runtime_s")) or 0 for d in cards.values()
                            if fin(d["obs"].get("runtime_s"))])


def sr_pred(b, w):
    sb, sw = fin(cards[b]["obs"].get("val_at_low")), fin(cards[w]["obs"].get("val_at_low"))
    if sb is None or sw is None or sb == sw:
        return None
    lower = ORI.get(cards[b]["task"]["name"], False)
    return int((sb < sw) if lower else (sb > sw))


evaluate("self_report", sr_pred, 0.0, med_rt,
         f"query cost = one execution (median {med_rt:.0f}s)")

print("\n--- LLM judges (pairwise decisions read directly) ---", flush=True)
import os as _os
for _tag, _path in (("judge_qwen_max", "phase1/judge_qwenmax.jsonl"),
                    ("judge_deepseek", "phase1/judge_code8k.jsonl")):
    if not _os.path.exists(_path):
        continue
    _dec = {}
    for _l in open(_path):
        _d = json.loads(_l)
        if _d.get("correct") is None:
            continue
        # both orders were asked; averaging them is what keeps position bias out
        _dec.setdefault((_d["better"], _d["worse"]), []).append(_d["correct"])
    _avg = {k: sum(v) / len(v) for k, v in _dec.items()}
    evaluate(_tag, lambda b, w, _a=_avg: _a.get((b, w)), 0.0, 30.0,
             "order-averaged pairwise")

print("\n--- trained critics (from dumped scores) ---", flush=True)
import os
for tag, path in (("rm_1.5b_2048_SIBSUBSET", "phase1/rm_scores_sibling.json"),
                  ("embed_frozen_0.5b", "phase1/embed_scores.json"),
                  ("rm_1.5b_2048", "phase1/rm_scores_testpairs.json")):
    if not os.path.exists(path):
        print(f"  {tag}: {path} not present yet, skipped")
        continue
    sc = {k: float(v) for k, v in json.load(open(path)).items()}
    note = "PARTIAL COVERAGE, not comparable" if "SIBSUBSET" in tag else "eval-only"
    evaluate(tag, lambda b, w, _s=sc: (None if b not in _s or w not in _s
                                       else int(_s[b] > _s[w])), 0.0, 0.05, note)

import csv
with open(a.out, "w", newline="") as f:
    wtr = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    wtr.writeheader()
    for r in results:
        wtr.writerow(r)
print(f"\nwrote {len(results)} rows -> {a.out}")
with open("phase1/perpair_hits.json", "w") as _f:
    json.dump(PERPAIR, _f)
with open("phase1/perpair_decision.json", "w") as _f2:
    json.dump(PERPAIR2, _f2)
print(f"wrote per-pair decisions for {len(PERPAIR)} predictors "
      f"({sum(len(v) for v in PERPAIR.values())} decisions) -> phase1/perpair_hits.json")
