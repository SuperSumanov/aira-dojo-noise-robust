#!/usr/bin/env python3
"""Independent cohort and numerical verifier for prospective WL predictions."""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import itertools
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from phase1 import verify_fixed_decision_scorer as independent_static
from phase1.wl_code_graph_features import HASHED_DIMENSIONS, MAXIMUM_NODES, WL_ITERATIONS, wl_feature_dict


ARMS = (
    "step_only_lr",
    "wl_graph_lr",
    "wl_graph_static_lr",
    "wl_graph_static_tfidf_lr",
)
MODEL_FORMAT = "wl_graph_multiview_npz_v1"
PROTOCOL = "prospective-wl-graph-escrow-v1"
VERIFY_GRAPH_BATCH = 17
BLIND_KEYS = {
    "card_id", "task", "run_id", "code", "code_sha256", "lineage",
    "generation_started_at_utc", "source_sha256",
}
LINEAGE_KEYS = {"depth", "step", "n_siblings", "op", "parent"}
RUN_KEYS = {
    "run_id", "task", "drop_id", "flow_status", "endpoints",
    "generation_started_at_utc", "source_sha256",
}


class VerifyError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VerifyError(f"expected object: {path.name}")
    return value


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise VerifyError(f"blank JSONL line: {path.name}:{line_number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise VerifyError(f"non-object JSONL line: {path.name}:{line_number}")
            yield value


def require_sha(path: Path, expected: Any) -> None:
    if not isinstance(expected, str) or sha256_file(path) != expected:
        raise VerifyError(f"SHA mismatch: {path.name}")


def parse_utc(value: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise VerifyError("UTC timestamp must end in Z")
    return dt.datetime.fromisoformat(value[:-1] + "+00:00").astimezone(dt.timezone.utc)


def load_cohort(state_root: Path, snapshot_root: Path, expected_snapshot: str) -> tuple[dict[str, dict[str, Any]], list[tuple[str, str]]]:
    state_root = state_root.resolve()
    snapshot_root = snapshot_root.resolve()
    if snapshot_root.parent != state_root / "snapshots" or snapshot_root.name != expected_snapshot:
        raise VerifyError("snapshot path mismatch")
    registry = list(read_jsonl(snapshot_root / "intake_registry.jsonl"))
    all_cards: dict[str, dict[str, Any]] = {}
    run_drop: dict[str, str] = {}
    for entry in registry:
        if set(entry) != {"drop_id", "intake_dir", "summary_sha256"}:
            raise VerifyError("registry schema mismatch")
        drop_id = entry["drop_id"]
        intake = Path(entry["intake_dir"]).resolve()
        if not isinstance(drop_id, str) or intake.parent != state_root / "intakes" or intake.name != drop_id:
            raise VerifyError("registry intake binding mismatch")
        summary_path = intake / "summary.json"
        require_sha(summary_path, entry["summary_sha256"])
        summary = read_object(summary_path)
        outputs = summary.get("outputs")
        security = summary.get("security")
        blindness = summary.get("blindness")
        if not all(isinstance(value, dict) for value in (outputs, security, blindness)):
            raise VerifyError("intake contracts missing")
        if (
            security.get("env_members_read") is not False
            or security.get("live_event_journal_members_read") is not False
            or blindness.get("labels_used_for_run_selection") is not False
            or blindness.get("labels_used_for_endpoint_selection") is not False
            or blindness.get("metrics_computed") != []
        ):
            raise VerifyError("intake blindness mismatch")
        manifest = intake / "eligible_blind_manifest.jsonl"
        require_sha(manifest, outputs.get("eligible_blind_manifest_sha256"))
        for row in read_jsonl(manifest):
            if set(row) != BLIND_KEYS or not isinstance(row.get("lineage"), dict) or set(row["lineage"]) != LINEAGE_KEYS:
                raise VerifyError("blind manifest schema mismatch")
            identifier, run_id, code = row["card_id"], row["run_id"], row["code"]
            if (
                not all(isinstance(value, str) and value for value in (identifier, run_id, code, row["task"], row["lineage"]["parent"]))
                or identifier in all_cards
                or hashlib.sha256(code.encode()).hexdigest() != row["code_sha256"]
            ):
                raise VerifyError("blind endpoint invalid")
            owner = run_drop.setdefault(run_id, drop_id)
            if owner != drop_id:
                raise VerifyError("run spans drops")
            all_cards[identifier] = {
                "id": identifier,
                "task": row["task"],
                "run": run_id,
                "code": code,
                "code_sha256": row["code_sha256"],
                "parent": row["lineage"]["parent"],
                "lineage": {key: row["lineage"][key] for key in ("depth", "step", "n_siblings", "op")},
                "generation_started_at_utc": row["generation_started_at_utc"],
                "source_sha256": row["source_sha256"],
            }
    runs = list(read_jsonl(snapshot_root / "accumulator" / "provisional_runs.jsonl"))
    run_rows: dict[str, dict[str, Any]] = {}
    for row in runs:
        if (
            set(row) != RUN_KEYS
            or row.get("flow_status") != "scoreable"
            or row.get("run_id") in run_rows
            or row.get("drop_id") != run_drop.get(row.get("run_id"))
        ):
            raise VerifyError("provisional run mismatch")
        run_rows[row["run_id"]] = row
    if set(run_rows) != {card["run"] for card in all_cards.values()}:
        raise VerifyError("run/card support mismatch")
    endpoint_counts = collections.Counter(card["run"] for card in all_cards.values())
    for run_id, row in run_rows.items():
        if (
            row.get("endpoints") != endpoint_counts[run_id]
            or any(
                card["task"] != row["task"]
                or card["generation_started_at_utc"] != row["generation_started_at_utc"]
                or card["source_sha256"] != row["source_sha256"]
                for card in all_cards.values()
                if card["run"] == run_id
            )
        ):
            raise VerifyError("independent card/run accounting mismatch")
    ordered = sorted(
        runs,
        key=lambda row: (row["generation_started_at_utc"], row["source_sha256"], row["run_id"]),
    )
    selected_runs = {row["run_id"] for row in ordered[:960]}
    cards = {identifier: card for identifier, card in sorted(all_cards.items()) if card["run"] in selected_runs}
    groups: dict[tuple[str, str, str], list[str]] = collections.defaultdict(list)
    for identifier, card in cards.items():
        groups[(card["task"], card["run"], card["parent"])].append(identifier)
    pairs = [pair for group in sorted(groups) for pair in itertools.combinations(sorted(groups[group]), 2)]
    if not cards or not pairs:
        raise VerifyError("empty independently reconstructed cohort")
    return cards, pairs


def graph_matrix(cards: dict[str, dict[str, Any]], identifiers: list[str]):
    from scipy import sparse
    from sklearn.feature_extraction import FeatureHasher
    from sklearn.preprocessing import normalize

    hasher = FeatureHasher(n_features=HASHED_DIMENSIONS, input_type="dict", dtype=np.float64, alternate_sign=True)
    matrices = []
    modes: collections.Counter[str] = collections.Counter()
    truncated = 0
    for start in range(0, len(identifiers), VERIFY_GRAPH_BATCH):
        rows = []
        for identifier in identifiers[start : start + VERIFY_GRAPH_BATCH]:
            features, diagnostic = wl_feature_dict(cards[identifier]["code"])
            rows.append(features)
            modes[diagnostic.mode] += 1
            truncated += diagnostic.truncated
        matrices.append(normalize(hasher.transform(rows).tocsr(), norm="l2", axis=1, copy=False))
    matrix = sparse.vstack(matrices, format="csr")
    if matrix.shape != (len(identifiers), HASHED_DIMENSIONS) or not np.isfinite(matrix.data).all():
        raise VerifyError("independent graph matrix invalid")
    return matrix, {"mode_counts": dict(sorted(modes.items())), "truncated_endpoints": truncated}


def score_independently(cards: dict[str, dict[str, Any]], bundle: Path):
    from scipy import sparse
    from sklearn.feature_extraction.text import TfidfVectorizer

    required = {
        "format", "protocol", "seed", "wl_iterations", "maximum_nodes", "hashed_dimensions",
        "step_scale", "step_coef", "graph_coef", "static_feature_names", "static_scale",
        "graph_static_coef", "tfidf_terms", "tfidf_idf", "multiview_coef",
    }
    with np.load(bundle, allow_pickle=False) as data:
        if set(data.files) != required:
            raise VerifyError("bundle schema mismatch")
        arrays = {key: np.asarray(data[key]).copy() for key in data.files}
    if (
        str(arrays["format"][0]) != MODEL_FORMAT
        or str(arrays["protocol"][0]) != "wl-graph-multiview-extension-v1"
        or int(arrays["wl_iterations"][0]) != WL_ITERATIONS
        or int(arrays["maximum_nodes"][0]) != MAXIMUM_NODES
        or int(arrays["hashed_dimensions"][0]) != HASHED_DIMENSIONS
    ):
        raise VerifyError("bundle configuration mismatch")
    identifiers = sorted(cards)
    graph, diagnostics = graph_matrix(cards, identifiers)
    names = [str(value) for value in arrays["static_feature_names"].tolist()]
    static = np.asarray(
        [[independent_static.static_feature_dict(cards[identifier])[name] for name in names] for identifier in identifiers],
        dtype=np.float64,
    )
    static_scaled = sparse.csr_matrix(static / arrays["static_scale"])
    terms = [str(value) for value in arrays["tfidf_terms"].tolist()]
    vectorizer = TfidfVectorizer(
        analyzer="char_wb", dtype=np.float64, ngram_range=(3, 5), sublinear_tf=True,
        vocabulary={term: index for index, term in enumerate(terms)},
    )
    vectorizer.idf_ = np.asarray(arrays["tfidf_idf"], dtype=np.float64)
    tfidf = vectorizer.transform([independent_static.code_view(cards[identifier]["code"]) for identifier in identifiers])
    graph_static = sparse.hstack([graph, static_scaled], format="csr")
    multiview = sparse.hstack([graph, static_scaled, tfidf], format="csr")
    step_index = names.index("step")
    raw = {
        "step_only_lr": static[:, step_index] / arrays["step_scale"][0] * arrays["step_coef"][0],
        "wl_graph_lr": np.asarray(graph @ arrays["graph_coef"]).reshape(-1),
        "wl_graph_static_lr": np.asarray(graph_static @ arrays["graph_static_coef"]).reshape(-1),
        "wl_graph_static_tfidf_lr": np.asarray(multiview @ arrays["multiview_coef"]).reshape(-1),
    }
    if not all(np.isfinite(value).all() for value in raw.values()):
        raise VerifyError("non-finite independent score")
    return {
        identifier: {arm: float(raw[arm][index]) for arm in ARMS}
        for index, identifier in enumerate(identifiers)
    }, diagnostics


def verify(args: argparse.Namespace) -> dict[str, Any]:
    for path, expected in (
        (args.bundle, args.expect_bundle_sha256),
        (args.activation_receipt, args.expect_activation_receipt_sha256),
    ):
        require_sha(path, expected)
    activation = read_object(args.activation_receipt)
    if activation.get("status") != "PROSPECTIVE_WL_GRAPH_EXTENSION_ACTIVE":
        raise VerifyError("activation receipt status mismatch")
    activated_at = parse_utc(activation.get("activated_at_utc"))
    summary = read_object(args.artifact / "summary.json")
    manifest = read_object(args.artifact / "sha256_manifest.json")
    expected_manifest = {
        name: sha256_file(args.artifact / name)
        for name in ("endpoint_scores.csv", "pair_predictions.jsonl", "summary.json")
    }
    if (
        manifest != expected_manifest
        or summary.get("status") != "PROSPECTIVE_WL_GRAPH_PREDICTION_ESCROW_COMPLETE"
        or summary.get("scope", {}).get("prospective_outcomes_read") is not False
        or summary.get("scope", {}).get("effect_metrics_computed") != []
        or summary.get("inputs", {}).get("snapshot_sha256") != args.expect_snapshot_sha256
    ):
        raise VerifyError("artifact manifest/scope mismatch")
    cards, pairs = load_cohort(args.state_root, args.snapshot_root, args.expect_snapshot_sha256)
    scores, graph_diagnostics = score_independently(cards, args.bundle)

    observed: dict[str, dict[str, float]] = {}
    with (args.artifact / "endpoint_scores.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            identifier = row["card_id"]
            if identifier in observed:
                raise VerifyError("duplicate endpoint score")
            observed[identifier] = {arm: float(row[arm]) for arm in ARMS}
            card = cards.get(identifier)
            if (
                card is None
                or row["task"] != card["task"]
                or row["run_id"] != card["run"]
                or row["parent"] != card["parent"]
                or row["code_sha256"] != card["code_sha256"]
            ):
                raise VerifyError("endpoint identity mismatch")
            expected_stratum = (
                "strict_post_activation_primary"
                if parse_utc(card["generation_started_at_utc"]) > activated_at
                else "outcome_unread_support_only"
            )
            if row["temporal_stratum"] != expected_stratum:
                raise VerifyError("endpoint temporal stratum mismatch")
    if set(observed) != set(scores):
        raise VerifyError("endpoint score coverage mismatch")
    maximum = {
        arm: max(abs(observed[identifier][arm] - scores[identifier][arm]) for identifier in observed)
        for arm in ARMS
    }
    if any(not np.isfinite(value) or value > 1e-12 for value in maximum.values()):
        raise VerifyError(f"independent endpoint score mismatch: {maximum}")

    expected_pairs = set(pairs)
    observed_pairs: set[tuple[str, str]] = set()
    with (args.artifact / "pair_predictions.jsonl").open(encoding="utf-8") as handle:
        for row in map(json.loads, handle):
            pair = (row["left"], row["right"])
            if pair in observed_pairs or pair not in expected_pairs:
                raise VerifyError("pair identity mismatch")
            observed_pairs.add(pair)
            expected_stratum = (
                "strict_post_activation_primary"
                if parse_utc(cards[pair[0]]["generation_started_at_utc"]) > activated_at
                else "outcome_unread_support_only"
            )
            if row.get("temporal_stratum") != expected_stratum:
                raise VerifyError("pair temporal stratum mismatch")
            for arm in ARMS:
                margin = scores[pair[0]][arm] - scores[pair[1]][arm]
                selected = pair[0] if margin > 0 else pair[1] if margin < 0 else "tie"
                if abs(float(row[f"{arm}_margin_left_minus_right"]) - margin) > 1e-12:
                    raise VerifyError("pair margin mismatch")
                if row[f"{arm}_selected"] != selected:
                    raise VerifyError("pair selection mismatch")
    if observed_pairs != expected_pairs:
        raise VerifyError("pair coverage mismatch")
    return {
        "status": "INDEPENDENT_PROSPECTIVE_WL_GRAPH_ESCROW_VERIFIED",
        "artifact_summary_sha256": sha256_file(args.artifact / "summary.json"),
        "snapshot_sha256": args.expect_snapshot_sha256,
        "endpoints": len(observed),
        "pairs": len(observed_pairs),
        "maximum_absolute_score_difference": maximum,
        "independent_graph_diagnostics": graph_diagnostics,
        "producer_imported": False,
        "shared_pure_graph_feature_spec_only": "phase1.wl_code_graph_features",
        "prospective_outcomes_read": False,
        "effect_metrics_computed": [],
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--state-root", required=True, type=Path)
    value.add_argument("--snapshot-root", required=True, type=Path)
    value.add_argument("--expect-snapshot-sha256", required=True)
    value.add_argument("--bundle", required=True, type=Path)
    value.add_argument("--expect-bundle-sha256", required=True)
    value.add_argument("--activation-receipt", required=True, type=Path)
    value.add_argument("--expect-activation-receipt-sha256", required=True)
    value.add_argument("--artifact", required=True, type=Path)
    value.add_argument("--output", required=True, type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.output.exists():
        print("PROSPECTIVE_WL_VERIFY_ERROR: output exists", file=sys.stderr)
        return 2
    try:
        receipt = verify(args)
        args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    except (VerifyError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"PROSPECTIVE_WL_VERIFY_ERROR: {error}", file=sys.stderr)
        return 2
    print(
        receipt["status"],
        f"endpoints={receipt['endpoints']}",
        f"pairs={receipt['pairs']}",
        f"max_diff={max(receipt['maximum_absolute_score_difference'].values())}",
        "effect_metrics=0",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
