import hashlib
import json
from pathlib import Path

import pytest

from phase1.materialize_g_reuse_blinded_margins import (
    ARMS, SEEDS, MarginMaterializationError, load_protocol, materialize, write,
)
from phase1.verify_g_reuse_blinded_margins import IndependentMarginError, verify


def h(value):
    return hashlib.sha256(value.encode()).hexdigest()


PROTOCOL = Path(__file__).parents[1] / "g_reuse_blinded_margin_materialization_v1.json"


def files(tmp_path):
    pair_path = tmp_path / "pairs.jsonl"; score_path = tmp_path / "scores.jsonl"
    pairs = []
    for left, right, task in (("a", "b", 0), ("a", "c", 1)):
        pairs.append({"left_endpoint_id": left, "right_endpoint_id": right,
                      "pair_sha256": h(left + "\0" + right), "task_sha256": h(f"task:{task}"),
                      "parent_sha256": h(f"parent:{task}"), "run_sha256": h(f"run:{task}")})
    pair_path.write_text("".join(json.dumps(row) + "\n" for row in pairs), encoding="utf-8")
    scores = []
    for index, endpoint in enumerate(("a", "b", "c")):
        values = {"tfidf": index / 10}
        values.update({f"{arm}|{seed}": index + seed / 10 for arm in ARMS for seed in SEEDS})
        scores.append({"endpoint_id": endpoint, "scores": values})
    score_path.write_text("".join(json.dumps(row) + "\n" for row in scores), encoding="utf-8")
    return pair_path, score_path


def test_materializer_and_independent_verifier_match(tmp_path):
    pairs, scores = files(tmp_path); output = tmp_path / "output.jsonl"
    rows = materialize(pairs, scores); write(output, rows)
    receipt = verify(PROTOCOL, pairs, scores, output)
    assert receipt == {"verification_pass": True, "pair_count": 2, "endpoint_count": 3,
                       "raw_endpoint_identity_written": False, "truth_or_outcome_written": False}
    assert set(rows[0]) == {"pair_sha256", "task_sha256", "parent_sha256", "run_sha256", "margins"}
    serialized = output.read_text(encoding="utf-8")
    assert '"left_endpoint_id"' not in serialized and '"right_endpoint_id"' not in serialized
    assert '"truth' not in serialized and '"outcome' not in serialized


def test_frozen_protocol_is_accepted_and_drift_rejected(tmp_path):
    source = PROTOCOL
    assert load_protocol(source)["protocol"] == "g-reuse-blinded-margin-materialization-v1"
    drift = tmp_path / "drift.json"
    value = json.loads(source.read_text(encoding="utf-8")); value["required_seeds"] = [6, 7, 9]
    drift.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(MarginMaterializationError, match="protocol_seeds"):
        load_protocol(drift)


@pytest.mark.parametrize("case", ["orientation", "truth", "missing", "extra", "nan", "pair_hash", "duplicate"])
def test_invalid_inputs_fail_closed(tmp_path, case):
    pairs, scores = files(tmp_path)
    pair_rows = [json.loads(line) for line in pairs.read_text().splitlines()]
    score_rows = [json.loads(line) for line in scores.read_text().splitlines()]
    if case == "orientation": pair_rows[0]["left_endpoint_id"], pair_rows[0]["right_endpoint_id"] = "b", "a"
    elif case == "truth": pair_rows[0]["truth_sign"] = 1
    elif case == "missing": score_rows.pop()
    elif case == "extra": score_rows.append({"endpoint_id": "z", "scores": score_rows[0]["scores"]})
    elif case == "nan": score_rows[0]["scores"]["L1|6"] = float("nan")
    elif case == "pair_hash": pair_rows[0]["pair_sha256"] = "0" * 64
    else: score_rows.append(score_rows[0])
    pairs.write_text("".join(json.dumps(row) + "\n" for row in pair_rows), encoding="utf-8")
    scores.write_text("".join(json.dumps(row) + "\n" for row in score_rows), encoding="utf-8")
    with pytest.raises(MarginMaterializationError):
        materialize(pairs, scores)


def test_verifier_rejects_tampered_margin(tmp_path):
    pairs, scores = files(tmp_path); output = tmp_path / "output.jsonl"
    result = materialize(pairs, scores); result[0]["margins"]["L1|6"] += 1; write(output, result)
    with pytest.raises(IndependentMarginError, match="output_mismatch"):
        verify(PROTOCOL, pairs, scores, output)
