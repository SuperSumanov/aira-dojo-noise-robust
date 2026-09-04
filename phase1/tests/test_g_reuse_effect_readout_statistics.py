import hashlib
from pathlib import Path

import pytest

from phase1.g_reuse_effect_readout_statistics import (
    ReadoutError, credit, evaluate, load_protocol, nested_cluster_bootstrap,
)


PROTOCOL = Path("phase1/g_reuse_effect_readout_protocol_v1.json")


def h(value):
    return hashlib.sha256(value.encode()).hexdigest()


def fixture(full=1.0, baseline=-1.0, l1=-1.0, hashed=-1.0):
    rows = []
    for task in range(4):
        for pair in range(3):
            sign = 1 if (task + pair) % 2 == 0 else -1
            margins = {"tfidf": baseline * sign}
            for seed in (6, 7, 8):
                margins.update({
                    f"L1|{seed}": l1 * sign,
                    f"Lbudget|{seed}": baseline * sign,
                    f"G-reuse-budget|{seed}": baseline * sign,
                    f"G-reuse-to-L-full|{seed}": full * sign,
                    f"Ghash-reuse-to-L-full|{seed}": hashed * sign,
                })
            rows.append({"pair_sha256": h(f"pair:{task}:{pair}"), "task_sha256": h(f"task:{task}"),
                         "parent_sha256": h(f"parent:{task}:{pair}"), "run_sha256": h(f"run:{task}:{pair}"),
                         "truth_sign": sign, "margins": margins})
    return rows


def test_tie_credit_is_half():
    assert credit(0.0, 1) == 0.5
    assert credit(0.0, -1) == 0.5


def test_clear_positive_passes_full_hierarchy():
    result = evaluate(fixture(), load_protocol(PROTOCOL))
    assert result["gates"]["deployment"]["all_pass"] is True
    assert result["gates"]["local_repeat_confound"] == {"triggered": False, "pass": True}
    assert result["gates"]["quality_label_information"]["pass"] is True
    assert result["gates"]["core_positive"] is True
    main = result["comparisons"]["full_minus_lbudget"]
    assert main["nested_parent_cluster_bootstrap_ci95"] == [1.0, 1.0]
    assert main["nested_physical_run_cluster_bootstrap_ci95"] == [1.0, 1.0]


def test_failed_deployment_omits_hash_comparison():
    result = evaluate(fixture(full=1.0, baseline=1.0), load_protocol(PROTOCOL))
    assert result["gates"]["deployment"]["all_pass"] is False
    assert result["gates"]["quality_label_information"] == {
        "eligible": False, "pass": None, "comparison": None
    }


def test_local_repeat_trigger_requires_full_to_beat_l1():
    rows = fixture(full=1.0, baseline=-1.0, l1=1.0)
    result = evaluate(rows, load_protocol(PROTOCOL))
    assert result["gates"]["local_repeat_confound"]["triggered"] is True
    assert result["gates"]["local_repeat_confound"]["pass"] is False
    assert result["gates"]["quality_label_information"]["eligible"] is False


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "nonfinite", "raw_id"])
def test_malformed_rows_fail_closed(mutation):
    rows = fixture()
    if mutation == "duplicate":
        rows[1]["pair_sha256"] = rows[0]["pair_sha256"]
    elif mutation == "missing":
        rows[0]["margins"].pop("L1|6")
    elif mutation == "nonfinite":
        rows[0]["margins"]["L1|6"] = float("nan")
    else:
        rows[0]["task_sha256"] = "task-name"
    with pytest.raises(ReadoutError):
        evaluate(rows, load_protocol(PROTOCOL))


def test_protocol_threshold_drift_is_rejected():
    import json
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    protocol["hierarchy"]["deployment"]["full_minus_lbudget_point_minimum"] = 0.0
    with pytest.raises(ReadoutError):
        evaluate(fixture(), protocol)


def test_nested_cluster_bootstrap_is_deterministic_and_field_checked():
    rows = fixture()
    args = dict(left="G-reuse-to-L-full", right="Lbudget", cluster_field="parent_sha256",
                comparison="test", seed=19, replicates=100)
    assert nested_cluster_bootstrap(rows, **args) == nested_cluster_bootstrap(rows, **args)
    args["cluster_field"] = "task_sha256"
    with pytest.raises(ReadoutError):
        nested_cluster_bootstrap(rows, **args)
