import hashlib
import json
from pathlib import Path

import pytest

from phase1.g_reuse_anonymous_truth_join import AnonymousJoinError, compose
from phase1.verify_g_reuse_anonymous_truth_join import IndependentJoinError, verify


JOIN_PATH = Path("phase1/g_reuse_anonymous_truth_join_v1.json")
READOUT_PATH = Path("phase1/g_reuse_effect_readout_protocol_v1.json")


def h(value):
    return hashlib.sha256(value.encode()).hexdigest()


def inputs(full=1.0, baseline=-1.0):
    predictions, truths = [], []
    for task in range(4):
        for pair in range(3):
            sign = 1 if (task + pair) % 2 == 0 else -1
            margins = {"tfidf": baseline * sign}
            for seed in (6, 7, 8):
                for arm in ("L1", "Lbudget", "G-reuse-budget", "Ghash-reuse-to-L-full"):
                    margins[f"{arm}|{seed}"] = baseline * sign
                margins[f"G-reuse-to-L-full|{seed}"] = full * sign
            common = {"pair_sha256": h(f"pair:{task}:{pair}"), "task_sha256": h(f"task:{task}"),
                      "parent_sha256": h(f"parent:{task}:{pair // 2}"),
                      "run_sha256": h(f"run:{task}:{pair // 2}")}
            predictions.append({**common, "margins": margins})
            truths.append({**common, "truth_sign": sign})
    return predictions, truths


def protocols():
    return JOIN_PATH.read_bytes(), READOUT_PATH.read_bytes()


def test_positive_join_and_independent_recomputation_hide_rows():
    predictions, truths = inputs(); join_protocol, readout = protocols()
    observed = compose(list(reversed(predictions)), truths, join_protocol, readout)
    receipt = verify(predictions, list(reversed(truths)), observed, join_protocol, readout)
    assert receipt["verification_pass"] is True and receipt["pair_count"] == 12
    assert observed["statistics"]["gates"]["core_positive"] is True
    raw = json.dumps(observed, sort_keys=True)
    assert '"truth_sign":' not in raw and '"margins":' not in raw and '"joined_rows":' not in raw


@pytest.mark.parametrize("case", ["missing", "extra", "cluster", "duplicate", "truth_field", "nan"])
def test_join_fail_closed(case):
    predictions, truths = inputs(); join_protocol, readout = protocols()
    if case == "missing": truths.pop()
    elif case == "extra":
        extra = dict(truths[-1]); extra["pair_sha256"] = h("extra"); truths.append(extra)
    elif case == "cluster": truths[0]["run_sha256"] = h("other-run")
    elif case == "duplicate": predictions.append(predictions[0])
    elif case == "truth_field": truths[0]["score"] = 1.0
    else: predictions[0]["margins"]["L1|6"] = float("nan")
    with pytest.raises(AnonymousJoinError):
        compose(predictions, truths, join_protocol, readout)


def test_protocol_drift_and_tampered_aggregate_rejected():
    predictions, truths = inputs(); join_protocol, readout = protocols()
    drift = join_protocol.replace(b'"truth_sign_values": [-1, 1]', b'"truth_sign_values": [0, 1]')
    assert drift != join_protocol
    with pytest.raises(AnonymousJoinError, match="join_protocol_sha"):
        compose(predictions, truths, drift, readout)
    observed = compose(predictions, truths, join_protocol, readout)
    observed["statistics"]["gates"]["deployment"]["point"] = False
    with pytest.raises(IndependentJoinError):
        verify(predictions, truths, observed, join_protocol, readout)


@pytest.mark.parametrize("target", ["join", "readout"])
def test_whitespace_only_protocol_drift_is_hash_rejected(target):
    predictions, truths = inputs(); join_protocol, readout = protocols()
    if target == "join":
        join_protocol += b"\n"
    else:
        readout += b"\n"
    with pytest.raises(AnonymousJoinError, match=target + "_protocol_sha"):
        compose(predictions, truths, join_protocol, readout)
    observed_join, observed_readout = protocols()
    observed = compose(predictions, truths, observed_join, observed_readout)
    with pytest.raises(IndependentJoinError, match=target + "_protocol_sha"):
        verify(predictions, truths, observed, join_protocol, readout)


def test_blocked_hierarchy_is_also_independently_recomputed():
    predictions, truths = inputs(full=1.0, baseline=1.0)
    join_protocol, readout = protocols()
    observed = compose(predictions, truths, join_protocol, readout)
    receipt = verify(predictions, truths, observed, join_protocol, readout)
    assert receipt["verification_pass"] is True
    assert observed["statistics"]["gates"]["core_positive"] is False
    assert observed["statistics"]["gates"]["quality_label_information"]["comparison"] is None
