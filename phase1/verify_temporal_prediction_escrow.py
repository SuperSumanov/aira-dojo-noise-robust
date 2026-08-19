#!/usr/bin/env python3
"""Independent numerical verifier for the temporal prediction escrow."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from . import verify_fixed_decision_scorer as independent_scorer


class VerifyError(RuntimeError):
    pass


def score_independently(cards: dict[str, dict], bundle: Path) -> dict[str, dict[str, float]]:
    from sklearn.feature_extraction.text import TfidfVectorizer

    required = {
        "format",
        "protocol",
        "seed",
        "static_feature_names",
        "static_scale",
        "static_coef",
        "tfidf_terms",
        "tfidf_idf",
        "tfidf_coef",
    }
    with np.load(bundle, allow_pickle=False) as data:
        if set(data.files) != required:
            raise VerifyError("bundle schema mismatch")
        arrays = {key: np.asarray(data[key]).copy() for key in data.files}
    if str(arrays["format"][0]) != independent_scorer.MODEL_FORMAT:
        raise VerifyError("bundle format mismatch")
    ids = sorted(cards)
    names = [str(value) for value in arrays["static_feature_names"].tolist()]
    matrix = np.asarray(
        [[independent_scorer.static_feature_dict(cards[card_id])[name] for name in names] for card_id in ids],
        dtype=np.float64,
    )
    static_scores = (matrix / arrays["static_scale"]) @ arrays["static_coef"]
    terms = [str(value) for value in arrays["tfidf_terms"].tolist()]
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        dtype=np.float64,
        ngram_range=(3, 5),
        sublinear_tf=True,
        vocabulary={term: index for index, term in enumerate(terms)},
    )
    vectorizer.idf_ = np.asarray(arrays["tfidf_idf"], dtype=np.float64)
    tfidf = vectorizer.transform([independent_scorer.code_view(cards[card_id]["code"]) for card_id in ids])
    tfidf_scores = np.asarray(tfidf @ arrays["tfidf_coef"], dtype=np.float64).reshape(-1)
    if not np.isfinite(static_scores).all() or not np.isfinite(tfidf_scores).all():
        raise VerifyError("non-finite independent score")
    return {
        card_id: {"static_lr": float(static_scores[index]), "char_tfidf_lr": float(tfidf_scores[index])}
        for index, card_id in enumerate(ids)
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(args: argparse.Namespace) -> int:
    for path, expected in (
        (args.blind_views, args.expect_blind_views_sha256),
        (args.structure, args.expect_structure_sha256),
        (args.bundle, args.expect_bundle_sha256),
    ):
        if sha256_file(path) != expected.lower():
            raise VerifyError(f"locked input mismatch: {path.name}")
    summary = json.loads((args.artifact / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((args.artifact / "sha256_manifest.json").read_text(encoding="utf-8"))
    expected_manifest = {
        name: sha256_file(args.artifact / name)
        for name in ("endpoint_scores.csv", "pair_predictions.jsonl", "summary.json")
    }
    if manifest != expected_manifest or summary.get("scope", {}).get("label_vault_read") is not False:
        raise VerifyError("artifact manifest/scope mismatch")

    cards = {}
    with args.blind_views.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            code = row["code"]
            if hashlib.sha256(code.encode()).hexdigest() != row["code_sha256"]:
                raise VerifyError("code SHA mismatch")
            lineage = row["lineage"]
            cards[row["card_id"]] = {
                "id": row["card_id"],
                "task": row["task"],
                "run": row["run_id"],
                "code": code,
                "lineage": {key: lineage[key] for key in ("depth", "step", "n_siblings", "op")},
                "parent": lineage["parent"],
            }
    recomputed = score_independently(cards, args.bundle)
    observed = {}
    with (args.artifact / "endpoint_scores.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            observed[row["card_id"]] = {
                "static_lr": float(row["static_lr"]),
                "char_tfidf_lr": float(row["char_tfidf_lr"]),
            }
    if set(observed) != set(recomputed):
        raise VerifyError("endpoint score coverage mismatch")
    max_abs = {
        arm: max(abs(observed[card_id][arm] - recomputed[card_id][arm]) for card_id in observed)
        for arm in ("static_lr", "char_tfidf_lr")
    }
    if any(not np.isfinite(value) or value > 1e-12 for value in max_abs.values()):
        raise VerifyError(f"independent numerical mismatch: {max_abs}")

    pair_count = 0
    with (args.artifact / "pair_predictions.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            pair_count += 1
            for arm in ("static_lr", "char_tfidf_lr"):
                margin = recomputed[row["left"]][arm] - recomputed[row["right"]][arm]
                selected = row["left"] if margin > 0 else row["right"] if margin < 0 else "tie"
                if abs(float(row[f"{arm}_margin_left_minus_right"]) - margin) > 1e-12:
                    raise VerifyError("pair margin mismatch")
                if row[f"{arm}_selected"] != selected:
                    raise VerifyError("pair selection mismatch")
    if pair_count != summary.get("inventory", {}).get("pairs"):
        raise VerifyError("pair count mismatch")
    result = {
        "status": "VERIFIED_TEMPORAL_PREDICTION_ESCROW",
        "artifact_summary_sha256": sha256_file(args.artifact / "summary.json"),
        "endpoints": len(observed),
        "pairs": pair_count,
        "max_abs_score_difference": max_abs,
        "label_vault_read": False,
    }
    if args.output.exists():
        raise VerifyError("output exists")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blind-views", required=True, type=Path)
    parser.add_argument("--expect-blind-views-sha256", required=True)
    parser.add_argument("--structure", required=True, type=Path)
    parser.add_argument("--expect-structure-sha256", required=True)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--expect-bundle-sha256", required=True)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    try:
        return verify(parser.parse_args())
    except (VerifyError, OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"TEMPORAL_PREDICTION_ESCROW_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
