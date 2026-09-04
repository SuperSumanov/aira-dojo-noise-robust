import hashlib
import json
from pathlib import Path

import pytest

from phase1.validate_g_reuse_prediction_escrow_v1 import ARMS, SEEDS, EscrowError, validate


CONTRACT = Path("phase1/g_reuse_prediction_escrow_contract_v1.json")


def h(value):
    return hashlib.sha256(value.encode()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def refresh_manifest(root, manifest_path):
    manifest = json.loads(manifest_path.read_text())
    for item in manifest["artifacts"]:
        raw = (root / item["path"]).read_bytes()
        item["bytes"] = len(raw); item["sha256"] = hashlib.sha256(raw).hexdigest()
    write(manifest_path, manifest)


def package(tmp_path):
    root = tmp_path / "escrow"; root.mkdir()
    checkpoints = []
    for arm in ARMS:
        for seed in SEEDS:
            checkpoints.append({"arm": arm, "seed": seed, "checkpoint_sha256": h(f"cp:{arm}:{seed}"),
                                "training_manifest_sha256": h(f"train:{arm}:{seed}"),
                                "config_sha256": h(f"config:{arm}:{seed}"), "final_optimizer_step": 10,
                                "complete": True, "selection_metric_read": False,
                                "frozen_evaluation_read": False})
    write(root / "checkpoints.json", {"protocol": "g-reuse-locked-checkpoints-v1",
                                      "checkpoints": checkpoints})
    checkpoint_sha = hashlib.sha256((root / "checkpoints.json").read_bytes()).hexdigest()
    access = {"protocol": "g-reuse-model-access-receipt-v1", "blinded_pair_manifest_sha256": h("blind"),
              "cards_sha256": h("cards"), "checkpoint_manifest_sha256": checkpoint_sha,
              "model_process_label_reads": 0, "model_process_outcome_reads": 0,
              "model_process_forbidden_open_count": 0, "accuracy_computed": False,
              "utility_computed": False, "raw_identity_output": False}
    write(root / "access.json", access)
    margins = {"tfidf": 0.0}
    margins.update({f"{arm}|{seed}": float(seed) for arm in ARMS for seed in SEEDS})
    pair_path = root / "pairs.jsonl"
    pair_path.write_text("".join(json.dumps({"pair_sha256": h(f"pair:{i}"),
                                              "task_sha256": h(f"task:{i}"),
                                              "parent_sha256": h(f"parent:{i}"),
                                              "run_sha256": h(f"run:{i}"), "margins": margins},
                                             sort_keys=True) + "\n" for i in range(2)), encoding="utf-8")
    pair_sha = hashlib.sha256(pair_path.read_bytes()).hexdigest()
    contract_sha = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
    summary = {"protocol": "g-reuse-prediction-escrow-v1",
               "status": "G_REUSE_PREDICTION_ESCROW_COMPLETE_OUTCOME_BLIND",
               "contract_sha256": contract_sha, "source_package_manifest_sha256": h("source"),
               "blinded_pair_manifest_sha256": h("blind"), "checkpoint_manifest_sha256": checkpoint_sha,
               "access_receipt_sha256": hashlib.sha256((root / "access.json").read_bytes()).hexdigest(),
               "pair_predictions_sha256": pair_sha, "tfidf_receipt_sha256": h("tfidf"),
               "pair_count": 2, "task_count": 2, "arms": list(ARMS), "seeds": list(SEEDS),
               "accuracy_computed": False, "labels_read": False, "outcomes_read": False,
               "utility_computed": False}
    write(root / "summary.json", summary)
    names = {"pair_predictions": "pairs.jsonl", "checkpoint_manifest": "checkpoints.json",
             "access_receipt": "access.json", "summary": "summary.json"}
    artifacts = []
    for role, name in names.items():
        raw = (root / name).read_bytes()
        artifacts.append({"role": role, "path": name, "bytes": len(raw),
                          "sha256": hashlib.sha256(raw).hexdigest()})
    manifest_path = root / "manifest.json"
    write(manifest_path, {"protocol": "g-reuse-prediction-escrow-manifest-v1",
                          "contract_sha256": contract_sha, "artifacts": artifacts})
    return root, manifest_path


def test_valid_synthetic_escrow_is_not_effect_eligible(tmp_path):
    root, manifest = package(tmp_path)
    result = validate(root, CONTRACT, manifest)
    assert result["checkpoint_count"] == 15 and result["pair_count"] == 2
    assert result["classification"] == "PREDICTION_ESCROW_HASH_BOUND_NOT_EFFECT_READOUT_ELIGIBLE"
    assert result["protected_values_read"] == 0


@pytest.mark.parametrize("case", ["missing_checkpoint", "label_read", "boolean_read_count", "truth_field",
                                  "nan", "hash_drift", "bad_checkpoint_hash_type"])
def test_fail_closed_cases(tmp_path, case):
    root, manifest = package(tmp_path)
    if case == "missing_checkpoint":
        path = root / "checkpoints.json"; value = json.loads(path.read_text()); value["checkpoints"].pop(); write(path, value)
        refresh_manifest(root, manifest)
    elif case in ("label_read", "boolean_read_count"):
        path = root / "access.json"; value = json.loads(path.read_text())
        value["model_process_label_reads"] = 1 if case == "label_read" else False
        write(path, value)
        refresh_manifest(root, manifest)
    elif case in ("truth_field", "nan"):
        path = root / "pairs.jsonl"; rows = [json.loads(line) for line in path.read_text().splitlines()]
        if case == "truth_field": rows[0]["truth_sign"] = 1
        else: rows[0]["margins"]["L1|6"] = float("nan")
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
        refresh_manifest(root, manifest)
    elif case == "hash_drift":
        (root / "pairs.jsonl").write_text("{}\n", encoding="utf-8")
    else:
        path = root / "checkpoints.json"; value = json.loads(path.read_text())
        value["checkpoints"][0]["checkpoint_sha256"] = 7; write(path, value)
        refresh_manifest(root, manifest)
    with pytest.raises(EscrowError):
        validate(root, CONTRACT, manifest)


def test_duplicate_json_key_rejected(tmp_path):
    root, manifest = package(tmp_path)
    (root / "access.json").write_text('{"protocol":"a","protocol":"b"}', encoding="utf-8")
    refresh_manifest(root, manifest)
    with pytest.raises(EscrowError, match="duplicate_json_key"):
        validate(root, CONTRACT, manifest)


def test_unlisted_hardlink_rejected(tmp_path):
    root, manifest = package(tmp_path)
    outside = tmp_path / "outside"; outside.write_bytes((root / "pairs.jsonl").read_bytes())
    (root / "pairs.jsonl").unlink(); (root / "pairs.jsonl").hardlink_to(outside)
    refresh_manifest(root, manifest)
    with pytest.raises(EscrowError, match="unsafe_artifact"):
        validate(root, CONTRACT, manifest)


def test_symlink_artifact_rejected(tmp_path):
    root, manifest_path = package(tmp_path)
    alias = root / "pairs-link.jsonl"
    try:
        alias.symlink_to(root / "pairs.jsonl")
    except OSError:
        pytest.skip("symlink creation unavailable")
    manifest = json.loads(manifest_path.read_text())
    item = next(row for row in manifest["artifacts"] if row["role"] == "pair_predictions")
    item["path"] = alias.name
    raw = alias.read_bytes(); item["bytes"] = len(raw); item["sha256"] = hashlib.sha256(raw).hexdigest()
    write(manifest_path, manifest)
    with pytest.raises(EscrowError, match="symlink"):
        validate(root, CONTRACT, manifest_path)


def test_credential_shape_rejected_before_receipt_parse(tmp_path):
    root, manifest = package(tmp_path)
    path = root / "access.json"
    path.write_text('{"credential":"sk-' + 'x' * 24 + '"}', encoding="utf-8")
    refresh_manifest(root, manifest)
    with pytest.raises(EscrowError, match="json_size_or_credential"):
        validate(root, CONTRACT, manifest)


def test_duplicate_pair_rejected(tmp_path):
    root, manifest = package(tmp_path)
    path = root / "pairs.jsonl"; first = path.read_text().splitlines()[0]
    path.write_text(first + "\n" + first + "\n", encoding="utf-8")
    refresh_manifest(root, manifest)
    with pytest.raises(EscrowError, match="duplicate_pair"):
        validate(root, CONTRACT, manifest)
