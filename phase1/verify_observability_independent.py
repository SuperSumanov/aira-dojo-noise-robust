#!/usr/bin/env python3
"""Independent point-estimate/integrity verifier; does not import the main audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tempfile
import zlib
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import binomtest
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

EXPECTED_SHA = {
    "manifest": "77f696828010e2d6ae10a9b9de2d9ec05d44975b1285ea763d9850a7f30ca4ef",
    "results": "b1266d04912596b1e37e13f79ce2387a962f5510cfa264aa1a97b7a1c443180d",
    "run_map": "3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def finite(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    return {
        "auc": float(roc_auc_score(y, p)),
        "average_precision": float(average_precision_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, np.clip(p, 1e-12, 1 - 1e-12), labels=[0, 1])),
    }


def close(a: object, b: object, tol: float = 1e-12) -> bool:
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)


def atomic_write(path: Path, text: str) -> None:
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--run-map", type=Path, required=True)
    ap.add_argument("--result-dir", type=Path, required=True)
    args = ap.parse_args()

    actual_sha = {
        "manifest": sha256(args.manifest),
        "results": sha256(args.results),
        "run_map": sha256(args.run_map),
    }
    if actual_sha != EXPECTED_SHA:
        raise RuntimeError(f"input SHA mismatch: {actual_sha}")

    manifest = load_jsonl(args.manifest)
    replays = load_jsonl(args.results)
    run_map = json.loads(args.run_map.read_text(encoding="utf-8"))
    with (args.result_dir / "per_card_predictions.csv").open(encoding="utf-8", newline="") as f:
        pred_rows = list(csv.DictReader(f))
    with (args.result_dir / "per_repeat_predictions.csv").open(encoding="utf-8", newline="") as f:
        repeat_rows = list(csv.DictReader(f))
    with (args.result_dir / "per_run_brier.csv").open(encoding="utf-8", newline="") as f:
        per_run_rows = list(csv.DictReader(f))
    summary = json.loads((args.result_dir / "summary.json").read_text(encoding="utf-8"))

    mby = {str(r["card_id"]): r for r in manifest}
    r120 = {str(r["card_id"]): r for r in replays if r.get("cap") == 120}
    pby = {r["card_id"]: r for r in pred_rows}
    if not (len(mby) == len(r120) == len(pby) == 230):
        raise RuntimeError("card counts or uniqueness differ")
    if set(mby) != set(r120) or set(mby) != set(pby):
        raise RuntimeError("card identity sets differ")

    ordered = pred_rows
    y = np.asarray([int(r["usable_score_120"]) for r in ordered], dtype=int)
    expected_y = np.asarray([int(finite(r120[r["card_id"]].get("sub_score"))) for r in ordered])
    if not np.array_equal(y, expected_y) or int(y.sum()) != 86:
        raise RuntimeError("label mismatch")
    for row in ordered:
        source = r120[row["card_id"]]
        if int(row["sub_exists_120"]) != int(bool(source.get("sub_exists", False))):
            raise RuntimeError(f"sub_exists mismatch {row['card_id']}")
        if int(row["usable_score_120"]) and not int(row["sub_exists_120"]):
            raise RuntimeError(f"finite score without artifact {row['card_id']}")

    run_folds: dict[str, set[int]] = defaultdict(set)
    for row in ordered:
        cid = row["card_id"]
        if row["task"] != str(mby[cid]["competition"]):
            raise RuntimeError(f"task mismatch {cid}")
        if row["run_id"] != str(run_map[cid]):
            raise RuntimeError(f"run mismatch {cid}")
        run_folds[row["run_id"]].add(int(row["fold"]))
    if len(run_folds) != 52 or any(len(v) != 1 for v in run_folds.values()):
        raise RuntimeError("run/fold isolation mismatch")
    if set(int(r["fold"]) for r in ordered) != set(range(5)):
        raise RuntimeError("fold identities mismatch")
    if len(repeat_rows) != 5 * 230:
        raise RuntimeError("repeat prediction count mismatch")
    expected_seeds = [9173, 9174, 9175, 9176, 9177]
    repeat_metrics = []
    for seed in expected_seeds:
        selected = [r for r in repeat_rows if int(r["split_seed"]) == seed]
        if len(selected) != 230 or {r["card_id"] for r in selected} != set(mby):
            raise RuntimeError(f"repeat identity mismatch seed={seed}")
        seed_run_folds: dict[str, set[int]] = defaultdict(set)
        selected_by_id = {r["card_id"]: r for r in selected}
        for row in selected:
            seed_run_folds[row["run_id"]].add(int(row["fold"]))
        if len(seed_run_folds) != 52 or any(len(v) != 1 for v in seed_run_folds.values()):
            raise RuntimeError(f"repeat run leakage seed={seed}")
        p_seed = np.asarray([float(selected_by_id[r["card_id"]]["pred_code_task"]) for r in ordered])
        repeat_metrics.append(metrics(y, p_seed))
    stated_sensitivity = summary["split_seed_sensitivity"]
    seed_aucs = np.asarray([m["auc"] for m in repeat_metrics])
    for i, (expected, stated) in enumerate(
        zip(repeat_metrics, stated_sensitivity["per_seed"], strict=True)
    ):
        if int(stated["seed"]) != expected_seeds[i]:
            raise RuntimeError(f"split seed order mismatch index={i}")
        for metric, value in expected.items():
            if not close(value, stated[metric]):
                raise RuntimeError(f"split sensitivity mismatch {stated['seed']}.{metric}")
    if not close(np.median(seed_aucs), stated_sensitivity["median_auc"]):
        raise RuntimeError("split median mismatch")
    if not close(np.var(seed_aucs, ddof=1), stated_sensitivity["sample_variance_auc"]):
        raise RuntimeError("split variance mismatch")

    columns = {
        "global_prevalence": "pred_global",
        "task_prevalence": "pred_task",
        "code_tfidf": "pred_code",
        "code_task_tfidf": "pred_code_task",
    }
    recalculated = {}
    for name, column in columns.items():
        p = np.asarray([float(r[column]) for r in ordered])
        if np.any(~np.isfinite(p)) or np.any((p < 0) | (p > 1)):
            raise RuntimeError(f"bad probability {name}")
        recalculated[name] = metrics(y, p)
        for metric, value in recalculated[name].items():
            if not close(value, summary["models"][name][metric]):
                raise RuntimeError(f"metric mismatch {name}.{metric}")

    p_task = np.asarray([float(r["pred_task"]) for r in ordered])
    p_main = np.asarray([float(r["pred_code_task"]) for r in ordered])
    gain = float(brier_score_loss(y, p_task) - brier_score_loss(y, p_main))
    if not close(gain, summary["brier_gain_vs_task"]):
        raise RuntimeError("Brier gain mismatch")

    signs = []
    runs = np.asarray([r["run_id"] for r in ordered], dtype=object)
    for run in sorted(set(runs.tolist())):
        idx = np.flatnonzero(runs == run)
        signs.append(float(np.mean((y[idx] - p_task[idx]) ** 2 - (y[idx] - p_main[idx]) ** 2)))
    pos = sum(v > 1e-12 for v in signs)
    neg = sum(v < -1e-12 for v in signs)
    ties = len(signs) - pos - neg
    pvalue = float(binomtest(pos, pos + neg, 0.5).pvalue) if pos + neg else 1.0
    stated = summary["run_brier_sign"]
    if (pos, neg, ties) != (stated["positive"], stated["negative"], stated["ties"]):
        raise RuntimeError("sign counts mismatch")
    if not close(pvalue, stated["pvalue"]):
        raise RuntimeError("sign p mismatch")

    oracle = np.asarray([float(r["control_oracle"]) for r in ordered])
    crc = np.asarray([
        (zlib.crc32(r["card_id"].encode("utf-8")) & 0xFFFFFFFF) / 2**32 for r in ordered
    ])
    stored_crc = np.asarray([float(r["control_crc32"]) for r in ordered])
    if not np.array_equal(oracle, y) or roc_auc_score(y, oracle) != 1.0:
        raise RuntimeError("oracle control mismatch")
    stated_crc = summary["controls"]["crc32_auc"]
    if not close(roc_auc_score(y, crc), stated_crc):
        raise RuntimeError("CRC control mismatch")
    if not np.allclose(crc, stored_crc, rtol=0, atol=1e-17):
        raise RuntimeError("stored CRC predictions mismatch")

    if len(per_run_rows) != 52 or {r["run_id"] for r in per_run_rows} != set(runs.tolist()):
        raise RuntimeError("per-run rows mismatch")
    run_row_map = {r["run_id"]: r for r in per_run_rows}
    for run in sorted(set(runs.tolist())):
        idx = np.flatnonzero(runs == run)
        expected_task = float(np.mean((y[idx] - p_task[idx]) ** 2))
        expected_main = float(np.mean((y[idx] - p_main[idx]) ** 2))
        stated_run = run_row_map[run]
        if int(stated_run["n_cards"]) != len(idx) or int(stated_run["n_usable"]) != int(y[idx].sum()):
            raise RuntimeError(f"per-run count mismatch {run}")
        if not close(stated_run["brier_task"], expected_task) or not close(stated_run["brier_main"], expected_main):
            raise RuntimeError(f"per-run Brier mismatch {run}")

    loto = np.asarray([float(r["pred_code_loto"]) for r in ordered])
    if not close(roc_auc_score(y, loto), summary["loto"]["pooled_auc"]):
        raise RuntimeError("LOTO pooled AUC mismatch")

    main_auc = recalculated["code_task_tfidf"]["auc"]
    run_auc_ci = summary["bootstrap"]["run"]["auc_ci"]
    if summary["controls"]["label_oracle_auc"] != 1.0:
        independent_decision = "KILL"
    elif main_auc <= 0.50 or run_auc_ci[1] <= 0.50:
        independent_decision = "KILL"
    else:
        rb = summary["bootstrap"]["run"]
        tb = summary["bootstrap"]["task"]
        lb = summary["loto"]["task_bootstrap"]
        go = (
            main_auc >= 0.65 and rb["auc_ci"][0] > 0.50 and tb["auc_ci"][0] > 0.50
            and gain > 0 and rb["brier_gain_vs_task_ci"][0] > 0
            and tb["brier_gain_vs_task_ci"][0] > 0 and pvalue < 0.05 and pos > neg
            and summary["loto"]["pooled_auc"] >= 0.60 and lb["auc_ci"][0] > 0.50
            and stated_sensitivity["median_auc"] >= 0.65
            and stated_sensitivity["min_auc"] > 0.50
        )
        independent_decision = "GO-FEASIBLE" if go else "BORDERLINE"
    if independent_decision != summary["decision"]:
        raise RuntimeError("decision mismatch")

    result = {
        "pass": True,
        "cards": len(ordered),
        "runs": len(run_folds),
        "tasks": len(set(r["task"] for r in ordered)),
        "main_auc": main_auc,
        "brier_gain_vs_task": gain,
        "run_sign": {"positive": pos, "negative": neg, "ties": ties, "pvalue": pvalue},
        "decision": independent_decision,
    }
    atomic_write(
        args.result_dir / "independent_verify.json",
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
    )
    atomic_write(
        args.result_dir / "independent_verify.txt",
        f"INDEPENDENT_OBSERVABILITY_VERIFY_PASS {json.dumps(result, sort_keys=True)}\n",
    )
    print("INDEPENDENT_OBSERVABILITY_VERIFY_PASS", result)


if __name__ == "__main__":
    main()
