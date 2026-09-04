import hashlib
import random
from pathlib import Path

import pytest

from phase1.g_reuse_effect_readout_statistics import (
    ReadoutError, credit, evaluate, load_protocol, nested_cluster_bootstrap,
)
from phase1.verify_g_reuse_effect_readout_statistics import IndependentReadoutError, verify


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


@pytest.mark.parametrize("full,baseline,l1", [(1.0, -1.0, -1.0), (1.0, 1.0, -1.0), (1.0, -1.0, 1.0)])
def test_independent_recomputation_matches_hierarchy(full, baseline, l1):
    rows = fixture(full=full, baseline=baseline, l1=l1)
    protocol = load_protocol(PROTOCOL)
    observed = evaluate(rows, protocol)
    receipt = verify(rows, observed, protocol)
    assert receipt["verification_pass"] is True
    assert receipt["maximum_numeric_absolute_difference"] <= 1e-12


def test_independent_recomputation_rejects_tampered_gate():
    rows = fixture()
    protocol = load_protocol(PROTOCOL)
    observed = evaluate(rows, protocol)
    observed["gates"]["deployment"]["point"] = False
    with pytest.raises(IndependentReadoutError):
        verify(rows, observed, protocol)


def test_independent_recomputation_matches_irregular_ties_and_clusters():
    rng = random.Random(20260905)
    rows = []
    for task, pair_count in enumerate((2, 3, 5, 7, 4, 6)):
        for pair in range(pair_count):
            margins = {"tfidf": rng.choice((-2.0, 0.0, 2.0))}
            for arm in ("L1", "Lbudget", "G-reuse-budget", "G-reuse-to-L-full",
                        "Ghash-reuse-to-L-full"):
                for seed in (6, 7, 8):
                    margins[f"{arm}|{seed}"] = rng.choice((-3.0, -1.0, 0.0, 1.0, 3.0))
            rows.append({
                "pair_sha256": h(f"irregular-pair:{task}:{pair}"),
                "task_sha256": h(f"irregular-task:{task}"),
                "parent_sha256": h(f"irregular-parent:{task}:{pair // 2}"),
                "run_sha256": h(f"irregular-run:{task}:{pair // 3}"),
                "truth_sign": rng.choice((-1, 1)), "margins": margins,
            })
    protocol = load_protocol(PROTOCOL)
    receipt = verify(rows, evaluate(rows, protocol), protocol)
    assert receipt["maximum_numeric_absolute_difference"] <= 1e-12
