#!/usr/bin/env python3
"""Frozen, run-clean audit of 120-second pristine-score observability.

This is a mechanism diagnostic, not a selector.  The only learned inputs are code and,
for the declared primary model, task identity.  All execution outcomes are forbidden
as features.  See the paired preregistration before running this on real data.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import platform
import random
import shutil
import subprocess
import sys
import tempfile
import zlib
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import scipy
import sklearn
from scipy.sparse import hstack
from scipy.stats import binomtest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import OneHotEncoder

SEED = 9173
OUTER_SEEDS = [9173, 9174, 9175, 9176, 9177]
N_BOOT = 20_000
TIE_EPS = 1e-12
EXPECTED = {
    "manifest_sha256": "77f696828010e2d6ae10a9b9de2d9ec05d44975b1285ea763d9850a7f30ca4ef",
    "results_sha256": "b1266d04912596b1e37e13f79ce2387a962f5510cfa264aa1a97b7a1c443180d",
    "run_map_sha256": "3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30",
    "cards": 230,
    "replays": 460,
    "runs": 52,
    "tasks": 19,
    "usable": 86,
}


def sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception as exc:
                raise RuntimeError(f"invalid JSON {path}:{lineno}: {exc}") from exc
            if not isinstance(row, dict):
                raise RuntimeError(f"non-object JSON {path}:{lineno}")
            rows.append(row)
    return rows


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def load_locked(manifest_path: Path, results_path: Path, run_map_path: Path) -> list[dict]:
    actual = {
        "manifest_sha256": sha256(manifest_path),
        "results_sha256": sha256(results_path),
        "run_map_sha256": sha256(run_map_path),
    }
    for key, expected in EXPECTED.items():
        if key.endswith("sha256") and actual[key] != expected:
            raise RuntimeError(f"SHA mismatch {key}: {actual[key]} != {expected}")

    manifest = read_jsonl(manifest_path)
    replay = read_jsonl(results_path)
    run_map = json.loads(run_map_path.read_text(encoding="utf-8"))
    if len(manifest) != EXPECTED["cards"] or len(replay) != EXPECTED["replays"]:
        raise RuntimeError(f"count mismatch manifest={len(manifest)} replay={len(replay)}")
    if not isinstance(run_map, dict):
        raise RuntimeError("run map must be a dict")

    mids = [str(r.get("card_id", "")) for r in manifest]
    if "" in mids or len(set(mids)) != len(mids):
        raise RuntimeError("manifest card_id missing or duplicated")
    mby = {str(r["card_id"]): r for r in manifest}

    by_cap: dict[tuple[str, int], dict] = {}
    for row in replay:
        cid = str(row.get("card_id", ""))
        cap = row.get("cap")
        if cid not in mby or not isinstance(cap, int):
            raise RuntimeError(f"bad replay identity cid={cid!r} cap={cap!r}")
        key = (cid, cap)
        if key in by_cap:
            raise RuntimeError(f"duplicate replay {key}")
        by_cap[key] = row
    if Counter(cap for _, cap in by_cap) != Counter({30: 230, 120: 230}):
        raise RuntimeError(f"unexpected cap counts: {Counter(cap for _, cap in by_cap)}")

    rows = []
    for cid in mids:
        m = mby[cid]
        r = by_cap[(cid, 120)]
        task = str(m.get("competition", ""))
        if not task or str(r.get("competition", "")) != task:
            raise RuntimeError(f"task mismatch {cid}")
        if cid not in run_map or not isinstance(run_map[cid], str) or not run_map[cid]:
            raise RuntimeError(f"run map missing {cid}")
        code = m.get("code")
        if not isinstance(code, str):
            raise RuntimeError(f"code is not text {cid}")
        y = int(finite(r.get("sub_score")))
        sub_exists = int(bool(r.get("sub_exists", False)))
        if y and not sub_exists:
            raise RuntimeError(f"finite score without submission artifact {cid}")
        rows.append(
            {
                "card_id": cid,
                "code": code[:20_000],
                "task": task,
                "run_id": run_map[cid],
                "y": y,
                "sub_exists": sub_exists,
                "code_truncated": int(len(code) > 20_000),
            }
        )

    if len({r["run_id"] for r in rows}) != EXPECTED["runs"]:
        raise RuntimeError("physical-run count mismatch")
    if len({r["task"] for r in rows}) != EXPECTED["tasks"]:
        raise RuntimeError("task count mismatch")
    if sum(r["y"] for r in rows) != EXPECTED["usable"]:
        raise RuntimeError("usable-score count mismatch")
    return rows


def make_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer="char",
        ngram_range=(3, 5),
        min_df=2,
        max_features=20_000,
        sublinear_tf=True,
        norm="l2",
        dtype=np.float64,
    )


def make_lr() -> LogisticRegression:
    return LogisticRegression(
        C=1.0,
        solver="liblinear",
        max_iter=2_000,
        random_state=SEED,
    )


def fit_predict_outer(
    rows: list[dict], split_seed: int = SEED
) -> tuple[np.ndarray, dict[str, np.ndarray], np.ndarray]:
    y = np.asarray([r["y"] for r in rows], dtype=int)
    groups = np.asarray([r["run_id"] for r in rows], dtype=object)
    tasks = np.asarray([r["task"] for r in rows], dtype=object)
    codes = np.asarray([r["code"] for r in rows], dtype=object)
    folds = np.full(len(rows), -1, dtype=int)
    pred = {name: np.full(len(rows), np.nan) for name in (
        "global_prevalence", "task_prevalence", "code_tfidf", "code_task_tfidf"
    )}

    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=split_seed)
    for fold, (tr, te) in enumerate(splitter.split(np.zeros(len(rows)), y, groups)):
        if set(groups[tr]) & set(groups[te]):
            raise RuntimeError(f"run leakage in fold {fold}")
        if len(np.unique(y[tr])) != 2 or len(np.unique(y[te])) != 2:
            raise RuntimeError(f"single-class fold {fold}")
        folds[te] = fold
        global_p = float(y[tr].mean())
        pred["global_prevalence"][te] = global_p

        task_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for idx in tr:
            task_counts[str(tasks[idx])][1] += 1
            task_counts[str(tasks[idx])][0] += int(y[idx])
        for idx in te:
            pos, n = task_counts.get(str(tasks[idx]), [0, 0])
            pred["task_prevalence"][idx] = (pos + 5.0 * global_p) / (n + 5.0)

        vec = make_vectorizer()
        xtr_code = vec.fit_transform(codes[tr].tolist())
        xte_code = vec.transform(codes[te].tolist())

        code_lr = make_lr().fit(xtr_code, y[tr])
        pred["code_tfidf"][te] = code_lr.predict_proba(xte_code)[:, 1]

        enc = OneHotEncoder(handle_unknown="ignore", sparse_output=True, dtype=np.float64)
        xtr_task = enc.fit_transform(tasks[tr].reshape(-1, 1))
        xte_task = enc.transform(tasks[te].reshape(-1, 1))
        joint_lr = make_lr().fit(hstack([xtr_code, xtr_task], format="csr"), y[tr])
        pred["code_task_tfidf"][te] = joint_lr.predict_proba(
            hstack([xte_code, xte_task], format="csr")
        )[:, 1]

    if np.any(folds < 0) or any(np.any(~np.isfinite(v)) for v in pred.values()):
        raise RuntimeError("incomplete OOF predictions")
    run_fold = defaultdict(set)
    for run, fold in zip(groups, folds, strict=True):
        run_fold[str(run)].add(int(fold))
    if any(len(v) != 1 for v in run_fold.values()):
        raise RuntimeError("physical run assigned to multiple folds")
    return y, pred, folds


def fit_predict_loto(rows: list[dict], y: np.ndarray) -> np.ndarray:
    tasks = np.asarray([r["task"] for r in rows], dtype=object)
    codes = np.asarray([r["code"] for r in rows], dtype=object)
    pred = np.full(len(rows), np.nan)
    for held in sorted(set(tasks.tolist())):
        te = np.flatnonzero(tasks == held)
        tr = np.flatnonzero(tasks != held)
        if len(np.unique(y[tr])) != 2:
            raise RuntimeError(f"single-class LOTO train for {held}")
        vec = make_vectorizer()
        xtr = vec.fit_transform(codes[tr].tolist())
        xte = vec.transform(codes[te].tolist())
        pred[te] = make_lr().fit(xtr, y[tr]).predict_proba(xte)[:, 1]
    if np.any(~np.isfinite(pred)):
        raise RuntimeError("incomplete LOTO predictions")
    return pred


def metric_bundle(y: np.ndarray, p: np.ndarray, weights: np.ndarray | None = None) -> dict[str, float]:
    clipped = np.clip(p, 1e-12, 1 - 1e-12)
    return {
        "auc": float(roc_auc_score(y, p, sample_weight=weights)),
        "average_precision": float(average_precision_score(y, p, sample_weight=weights)),
        "brier": float(brier_score_loss(y, p, sample_weight=weights)),
        "log_loss": float(log_loss(y, clipped, sample_weight=weights, labels=[0, 1])),
    }


def cluster_bootstrap(
    y: np.ndarray,
    p_main: np.ndarray,
    p_task: np.ndarray,
    clusters: np.ndarray,
    seed: int,
    n_boot: int = N_BOOT,
) -> dict[str, list[float] | int]:
    unique = np.asarray(sorted(set(clusters.tolist())), dtype=object)
    cluster_index = {c: i for i, c in enumerate(unique)}
    row_cluster = np.asarray([cluster_index[c] for c in clusters], dtype=int)
    rng = np.random.default_rng(seed)
    aucs, auc_diffs, brier_gains = [], [], []
    skipped = 0
    for _ in range(n_boot):
        draw = rng.integers(0, len(unique), size=len(unique))
        mult = np.bincount(draw, minlength=len(unique)).astype(float)
        w = mult[row_cluster]
        mask = w > 0
        if len(np.unique(y[mask])) < 2:
            skipped += 1
            continue
        auc_main = roc_auc_score(y, p_main, sample_weight=w)
        auc_task = roc_auc_score(y, p_task, sample_weight=w)
        aucs.append(float(auc_main))
        auc_diffs.append(float(auc_main - auc_task))
        brier_main = brier_score_loss(y, p_main, sample_weight=w)
        brier_task = brier_score_loss(y, p_task, sample_weight=w)
        brier_gains.append(float(brier_task - brier_main))

    def ci(values: list[float]) -> list[float]:
        if not values:
            raise RuntimeError("all bootstrap replicates invalid")
        return [float(x) for x in np.quantile(values, [0.025, 0.975])]

    return {
        "auc_ci": ci(aucs),
        "auc_vs_task_ci": ci(auc_diffs),
        "brier_gain_vs_task_ci": ci(brier_gains),
        "valid_replicates": len(aucs),
        "skipped_replicates": skipped,
    }


def loto_task_bootstrap(
    y: np.ndarray, pred: np.ndarray, tasks: np.ndarray, n_boot: int = N_BOOT
) -> dict:
    unique = np.asarray(sorted(set(tasks.tolist())), dtype=object)
    index = {c: i for i, c in enumerate(unique)}
    row_cluster = np.asarray([index[c] for c in tasks], dtype=int)
    rng = np.random.default_rng(SEED + 2)
    values, skipped = [], 0
    for _ in range(n_boot):
        draw = rng.integers(0, len(unique), size=len(unique))
        mult = np.bincount(draw, minlength=len(unique)).astype(float)
        w = mult[row_cluster]
        mask = w > 0
        if len(np.unique(y[mask])) < 2:
            skipped += 1
            continue
        values.append(float(roc_auc_score(y, pred, sample_weight=w)))
    return {
        "auc_ci": [float(x) for x in np.quantile(values, [0.025, 0.975])],
        "valid_replicates": len(values),
        "skipped_replicates": skipped,
    }


def sign_test_brier_gain(
    y: np.ndarray, p_main: np.ndarray, p_task: np.ndarray, clusters: np.ndarray
) -> dict[str, int | float]:
    gains = []
    for cluster in sorted(set(clusters.tolist())):
        idx = np.flatnonzero(clusters == cluster)
        gain = float(np.mean((y[idx] - p_task[idx]) ** 2 - (y[idx] - p_main[idx]) ** 2))
        gains.append(gain)
    pos = sum(g > TIE_EPS for g in gains)
    neg = sum(g < -TIE_EPS for g in gains)
    ties = len(gains) - pos - neg
    pvalue = float(binomtest(pos, pos + neg, 0.5, alternative="two-sided").pvalue) if pos + neg else 1.0
    return {"positive": pos, "negative": neg, "ties": ties, "pvalue": pvalue}


def decide(summary: dict) -> str:
    main = summary["models"]["code_task_tfidf"]
    run_boot = summary["bootstrap"]["run"]
    task_boot = summary["bootstrap"]["task"]
    sign = summary["run_brier_sign"]
    loto = summary["loto"]
    controls = summary["controls"]
    sensitivity = summary["split_seed_sensitivity"]
    if controls["label_oracle_auc"] != 1.0:
        return "KILL"
    if main["auc"] <= 0.50 or run_boot["auc_ci"][1] <= 0.50:
        return "KILL"
    go = (
        main["auc"] >= 0.65
        and run_boot["auc_ci"][0] > 0.50
        and task_boot["auc_ci"][0] > 0.50
        and summary["brier_gain_vs_task"] > 0.0
        and run_boot["brier_gain_vs_task_ci"][0] > 0.0
        and task_boot["brier_gain_vs_task_ci"][0] > 0.0
        and sign["pvalue"] < 0.05
        and sign["positive"] > sign["negative"]
        and loto["pooled_auc"] >= 0.60
        and loto["task_bootstrap"]["auc_ci"][0] > 0.50
        and sensitivity["median_auc"] >= 0.65
        and sensitivity["min_auc"] > 0.50
    )
    return "GO-FEASIBLE" if go else "BORDERLINE"


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_csv_atomic(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def self_test() -> None:
    rng = np.random.default_rng(123)
    rows = []
    for run in range(30):
        task = f"task{run % 5}"
        for card in range(4):
            signal = int((run + card) % 3 == 0)
            y = int(rng.random() < (0.75 if signal else 0.20))
            rows.append({
                "card_id": f"c{run}_{card}",
                "code": ("write_submission " if signal else "debug_loop ") + f"feature_{card}",
                "task": task,
                "run_id": f"run{run}",
                "y": y,
                "sub_exists": y,
            })
    y, pred, folds = fit_predict_outer(rows)
    loto = fit_predict_loto(rows, y)
    assert len(set(folds.tolist())) == 5
    assert np.all(np.isfinite(loto))
    assert metric_bundle(y, pred["code_tfidf"])["auc"] > 0.5
    boot = cluster_bootstrap(
        y,
        np.where(y == 1, 0.9, 0.1),
        np.full(len(y), 0.5),
        np.asarray([r["run_id"] for r in rows], dtype=object),
        seed=123,
        n_boot=200,
    )
    assert boot["valid_replicates"] > 0
    assert boot["auc_ci"] == [1.0, 1.0]
    sign = sign_test_brier_gain(
        y,
        np.where(y == 1, 0.9, 0.1),
        np.full(len(y), 0.5),
        np.asarray([r["run_id"] for r in rows], dtype=object),
    )
    assert sign["positive"] == 30 and sign["negative"] == 0 and sign["pvalue"] < 0.05
    gate = {
        "models": {"code_task_tfidf": {"auc": 0.70}},
        "bootstrap": {
            "run": {"auc_ci": [0.60, 0.80], "brier_gain_vs_task_ci": [0.01, 0.03]},
            "task": {"auc_ci": [0.55, 0.82], "brier_gain_vs_task_ci": [0.005, 0.04]},
        },
        "run_brier_sign": {"positive": 10, "negative": 1, "ties": 0, "pvalue": 0.01},
        "loto": {"pooled_auc": 0.62, "task_bootstrap": {"auc_ci": [0.51, 0.75]}},
        "controls": {"label_oracle_auc": 1.0},
        "brier_gain_vs_task": 0.02,
        "split_seed_sensitivity": {"median_auc": 0.68, "min_auc": 0.61},
    }
    assert decide(gate) == "GO-FEASIBLE"
    gate["models"]["code_task_tfidf"]["auc"] = 0.50
    assert decide(gate) == "KILL"
    print("SELF_TEST_PASS", len(rows), len(set(r["run_id"] for r in rows)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--results", type=Path)
    ap.add_argument("--run-map", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--git-commit")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    if not all((args.manifest, args.results, args.run_map, args.out, args.git_commit)):
        ap.error("--manifest --results --run-map --out --git-commit are required")
    if args.out.exists():
        raise RuntimeError(f"refusing existing output directory: {args.out}")

    random.seed(SEED)
    np.random.seed(SEED)
    repo = Path(__file__).resolve().parents[1]
    actual_commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_commit != args.git_commit:
        raise RuntimeError(f"git commit mismatch {actual_commit} != {args.git_commit}")
    rows = load_locked(args.manifest, args.results, args.run_map)
    y, pred, folds = fit_predict_outer(rows)
    repeat_predictions = []
    seed_metrics = []
    for split_seed in OUTER_SEEDS:
        sy, spred, sfolds = fit_predict_outer(rows, split_seed=split_seed)
        if not np.array_equal(sy, y):
            raise RuntimeError(f"label order changed for split seed {split_seed}")
        sm = metric_bundle(y, spred["code_task_tfidf"])
        seed_metrics.append({"seed": split_seed, **sm})
        for i, row in enumerate(rows):
            repeat_predictions.append({
                "split_seed": split_seed,
                "card_id": row["card_id"],
                "run_id": row["run_id"],
                "fold": int(sfolds[i]),
                "pred_global": f"{spred['global_prevalence'][i]:.17g}",
                "pred_task": f"{spred['task_prevalence'][i]:.17g}",
                "pred_code": f"{spred['code_tfidf'][i]:.17g}",
                "pred_code_task": f"{spred['code_task_tfidf'][i]:.17g}",
            })
    loto_pred = fit_predict_loto(rows, y)
    tasks = np.asarray([r["task"] for r in rows], dtype=object)
    runs = np.asarray([r["run_id"] for r in rows], dtype=object)
    oracle = y.astype(float)
    random_control = np.asarray([
        (zlib.crc32(r["card_id"].encode("utf-8")) & 0xFFFFFFFF) / 2**32 for r in rows
    ])

    models = {name: metric_bundle(y, values) for name, values in pred.items()}
    primary = pred["code_task_tfidf"]
    task_pred = pred["task_prevalence"]
    run_boot = cluster_bootstrap(y, primary, task_pred, runs, SEED)
    task_boot = cluster_bootstrap(y, primary, task_pred, tasks, SEED + 1)
    sign = sign_test_brier_gain(y, primary, task_pred, runs)

    per_task_auc = {}
    for task in sorted(set(tasks.tolist())):
        idx = np.flatnonzero(tasks == task)
        if len(np.unique(y[idx])) == 2:
            per_task_auc[task] = float(roc_auc_score(y[idx], loto_pred[idx]))
    loto_boot = loto_task_bootstrap(y, loto_pred, tasks)

    summary = {
        "protocol": {
            "seed": SEED,
            "outer_seeds": OUTER_SEEDS,
            "n_boot": N_BOOT,
            "outer": "StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=9173)",
            "primary_model": "code_task_tfidf",
            "git_commit": actual_commit,
            "argv": sys.argv,
            "versions": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "sklearn": sklearn.__version__,
            },
        },
        "counts": {
            "cards": len(rows),
            "usable": int(y.sum()),
            "sub_exists": int(sum(r["sub_exists"] for r in rows)),
            "code_truncated": int(sum(r["code_truncated"] for r in rows)),
            "runs": len(set(runs.tolist())),
            "tasks": len(set(tasks.tolist())),
            "folds": len(set(folds.tolist())),
        },
        "input_sha256": {
            "manifest": sha256(args.manifest),
            "results": sha256(args.results),
            "run_map": sha256(args.run_map),
        },
        "models": models,
        "brier_gain_vs_task": float(
            models["task_prevalence"]["brier"] - models["code_task_tfidf"]["brier"]
        ),
        "bootstrap": {"run": run_boot, "task": task_boot},
        "run_brier_sign": sign,
        "loto": {
            "pooled_auc": float(roc_auc_score(y, loto_pred)),
            "macro_task_auc": float(np.mean(list(per_task_auc.values()))),
            "eligible_task_count": len(per_task_auc),
            "per_task_auc": per_task_auc,
            "task_bootstrap": loto_boot,
        },
        "controls": {
            "label_oracle_auc": float(roc_auc_score(y, oracle)),
            "crc32_auc": float(roc_auc_score(y, random_control)),
        },
    }
    seed_aucs = np.asarray([row["auc"] for row in seed_metrics], dtype=float)
    summary["split_seed_sensitivity"] = {
        "per_seed": seed_metrics,
        "median_auc": float(np.median(seed_aucs)),
        "sample_variance_auc": float(np.var(seed_aucs, ddof=1)),
        "min_auc": float(np.min(seed_aucs)),
    }
    summary["decision"] = decide(summary)

    out_rows = []
    for i, row in enumerate(rows):
        out_rows.append({
            "card_id": row["card_id"],
            "task": row["task"],
            "run_id": row["run_id"],
            "fold": int(folds[i]),
            "usable_score_120": int(y[i]),
            "sub_exists_120": row["sub_exists"],
            "pred_global": f"{pred['global_prevalence'][i]:.17g}",
            "pred_task": f"{pred['task_prevalence'][i]:.17g}",
            "pred_code": f"{pred['code_tfidf'][i]:.17g}",
            "pred_code_task": f"{pred['code_task_tfidf'][i]:.17g}",
            "pred_code_loto": f"{loto_pred[i]:.17g}",
            "control_crc32": f"{random_control[i]:.17g}",
            "control_oracle": int(y[i]),
        })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = Path(tempfile.mkdtemp(prefix=f".{args.out.name}.tmp-", dir=args.out.parent))
    try:
        write_csv_atomic(tmp_out / "per_card_predictions.csv", list(out_rows[0]), out_rows)
        write_csv_atomic(
            tmp_out / "per_repeat_predictions.csv",
            list(repeat_predictions[0]),
            repeat_predictions,
        )
        per_run_rows = []
        for run in sorted(set(runs.tolist())):
            idx = np.flatnonzero(runs == run)
            brier_task = float(np.mean((y[idx] - task_pred[idx]) ** 2))
            brier_main = float(np.mean((y[idx] - primary[idx]) ** 2))
            per_run_rows.append({
                "run_id": run,
                "n_cards": len(idx),
                "n_usable": int(y[idx].sum()),
                "brier_task": f"{brier_task:.17g}",
                "brier_main": f"{brier_main:.17g}",
                "brier_gain": f"{brier_task - brier_main:.17g}",
            })
        write_csv_atomic(tmp_out / "per_run_brier.csv", list(per_run_rows[0]), per_run_rows)
        atomic_write_text(tmp_out / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")

        m = summary["models"]["code_task_tfidf"]
        lines = [
            f"VERIFIED cards={len(rows)} usable={int(y.sum())} runs={len(set(runs))} tasks={len(set(tasks))}",
            f"PRIMARY auc={m['auc']:.4f} runCI=[{run_boot['auc_ci'][0]:.4f},{run_boot['auc_ci'][1]:.4f}] taskCI=[{task_boot['auc_ci'][0]:.4f},{task_boot['auc_ci'][1]:.4f}]",
            f"BRIER_GAIN_VS_TASK delta={summary['brier_gain_vs_task']:+.4f} runCI=[{run_boot['brier_gain_vs_task_ci'][0]:+.4f},{run_boot['brier_gain_vs_task_ci'][1]:+.4f}] taskCI=[{task_boot['brier_gain_vs_task_ci'][0]:+.4f},{task_boot['brier_gain_vs_task_ci'][1]:+.4f}] sign_p={sign['pvalue']:.6f}",
            f"LOTO pooled_auc={summary['loto']['pooled_auc']:.4f} taskCI=[{loto_boot['auc_ci'][0]:.4f},{loto_boot['auc_ci'][1]:.4f}] macro_task_auc={summary['loto']['macro_task_auc']:.4f}",
            f"SPLIT_SEEDS median_auc={summary['split_seed_sensitivity']['median_auc']:.4f} variance={summary['split_seed_sensitivity']['sample_variance_auc']:.8f} min_auc={summary['split_seed_sensitivity']['min_auc']:.4f}",
            f"DECISION {summary['decision']}",
        ]
        atomic_write_text(tmp_out / "run.txt", "\n".join(lines) + "\n")
        os.replace(tmp_out, args.out)
    except Exception:
        shutil.rmtree(tmp_out, ignore_errors=True)
        raise
    print("\n".join(lines))


if __name__ == "__main__":
    main()
