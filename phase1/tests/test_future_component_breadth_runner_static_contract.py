from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PREDICTION_RUNNER = (
    ROOT / "phase1" / "scripts" / "run_critic_component_breadth_future_escrow_20260824.sh"
)
TRUTH_RUNNER = (
    ROOT / "phase1" / "scripts" / "run_score_channel_future_dual_truth_20260823.sh"
)
ZERO_COMMIT = "0" * 40


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal_assignment(text: str, name: str) -> str:
    matches = re.findall(rf"^{re.escape(name)}=([^\s#]+)$", text, flags=re.MULTILINE)
    assert len(matches) == 1, f"expected one literal assignment for {name}"
    return matches[0]


def heredoc_body(text: str, target_fragment: str) -> str:
    start = text.index(target_fragment)
    body_start = text.index("\n", start) + 1
    body_end = text.index("\nEOF", body_start)
    return text[body_start:body_end]


@pytest.mark.parametrize(
    ("path", "commit_name"),
    ((PREDICTION_RUNNER, "control_commit"), (TRUTH_RUNNER, "commit")),
)
def test_release_commit_is_source_bound_and_zero_value_fails_closed(
    path: Path, commit_name: str
) -> None:
    text = source(path)
    value = literal_assignment(text, commit_name)
    assert re.fullmatch(r"[0-9a-f]{40}", value)
    assert "if [[ $# -ne 0 ]]; then" in text
    assert "exit 64" in text[: text.index(f"{commit_name}=")]
    guard = f"if [[ ${{{commit_name}}} == {ZERO_COMMIT} ]]; then"
    guard_position = text.index(guard)
    exit_position = text.index("exit 69", guard_position)
    assert guard_position < exit_position < text.index("\nsource ") < text.index("base_repo=")
    # Ignore awk programs such as '{print $1}'; those dollars are single-quoted
    # literals, not caller-controlled shell positional parameters.
    shell_code = re.sub(r"'[^'\n]*'", "''", text)
    assert not re.search(r"\$(?:\{)?[1-9]", shell_code)
    assert "getopts" not in text
    assert not re.search(r"^\s*shift(?:\s|$)", text, flags=re.MULTILINE)


@pytest.mark.parametrize("path", (PREDICTION_RUNNER, TRUTH_RUNNER))
def test_cohort_identity_comes_only_from_fixed_first_closure_anchor(path: Path) -> None:
    text = source(path)
    anchor = "closure_anchor=${cohort_root}/FIRST_CLOSED_COHORT_ANCHOR.json"
    assert text.count(anchor) == 1
    assert 'test -f "${closure_anchor}"' in text
    assert 'test ! -L "${closure_anchor}"' in text
    assert 'value.get("protocol") != "score-channel-future-closure-anchor-v1"' in text
    assert (
        'value.get("status") '
        '!= "FUTURE_COHORT_FIRST_CLOSURE_ANCHORED_TRUTH_UNREAD"'
    ) in text
    assert 'value.get("identity_selected_before_truth") is not True' in text
    assert 'value.get("label_vault_opened") is not False' in text
    assert 'value.get("score_or_outcome_opened") is not False' in text
    assert "cohort.is_symlink()" in text
    assert 'hashlib.sha256((cohort / "summary.json").read_bytes()).hexdigest()' in text
    assert "cohort_dir=${anchor_values[0]}" in text
    assert "LATEST" not in text


def test_prediction_receipt_is_a_hard_predecessor_of_every_truth_module() -> None:
    prediction = source(PREDICTION_RUNNER)
    truth = source(TRUTH_RUNNER)
    assert (
        "critic-component-breadth-future/${short}-${cohort_summary_sha:0:12}-v1"
        in prediction
    )
    assert (
        "critic-component-breadth-future/${short}-${expected_cohort_sha:0:12}-v1"
        in truth
    )

    complete = truth.index('test -f "${prediction_root}/COMPLETE"')
    complete_value = truth.index(
        "FORMAL_FUTURE_COMPONENT_BREADTH_PREDICTION_ESCROW_COMPLETE_TRUTH_UNREAD"
    )
    manifest = truth.index('test -f "${prediction_root}/SHA256SUMS"')
    manifest_check = truth.index("sha256sum -c SHA256SUMS")
    predecessor = truth.index("PREDICTION_ESCROW_PREDECESSOR_PASS_TRUTH_STILL_UNREAD")
    closed_guard = truth.index("CLOSED_COHORT_GUARD_PASS_TRUTH_STILL_UNREAD")
    first_truth = min(
        truth.index('"${clean_python[@]}" -m phase1.score_channel_future_truth_support'),
        truth.index('"${clean_python[@]}" -m phase1.score_channel_future_raw_grade_support'),
    )
    assert complete < complete_value < manifest_check
    assert manifest < manifest_check < predecessor < closed_guard < first_truth
    assert 'test "$(cat "${prediction_root}/control_commit.txt")" = "${commit}"' in truth
    assert (
        'test "$(cat "${prediction_root}/cohort_summary_sha256.txt")" '
        '= "${expected_cohort_sha}"'
    ) in truth
    assert 'verification.get("status") != "INDEPENDENT_SOURCE_REFIT_PASS"' in truth
    assert "--label-vault" not in prediction
    assert "phase1.score_channel_future_truth_support" not in prediction
    assert "phase1.score_channel_future_raw_grade_support" not in prediction


def test_complete_receipts_and_sha_manifests_cover_both_stages() -> None:
    prediction = source(PREDICTION_RUNNER)
    truth = source(TRUTH_RUNNER)
    prediction_marker = (
        "FORMAL_FUTURE_COMPONENT_BREADTH_PREDICTION_ESCROW_COMPLETE_TRUTH_UNREAD"
    )
    truth_marker = "SCORE_CHANNEL_FUTURE_DUAL_TRUTH_FORMAL_COMPLETE_REPLAY_UNAUTHORIZED"

    for text, marker in ((prediction, prediction_marker), (truth, truth_marker)):
        marker_position = text.rindex(marker)
        manifest_position = text.rindex("find . -type f ! -name SHA256SUMS")
        assert marker_position < manifest_position
        assert "xargs -0 sha256sum" in text[manifest_position:]
        assert 'chmod -R a-w "${root}"' in text or 'chmod -R a-w "${final}"' in text
    assert "sha256sum -c SHA256SUMS" in prediction
    assert "sha256sum -c SHA256SUMS" in truth  # verifies the prediction predecessor
    assert 'sha256sum "${root}/SHA256SUMS"' in prediction
    assert 'sha256sum "${final}/SHA256SUMS"' in truth


def test_all_static_sha_bindings_are_full_and_source_bindings_match() -> None:
    prediction = source(PREDICTION_RUNNER)
    truth = source(TRUTH_RUNNER)
    prediction_shas = {
        name: literal_assignment(prediction, name)
        for name in ("contract_sha", "cards_sha", "train_sha")
    }
    assert all(re.fullmatch(r"[0-9a-f]{64}", value) for value in prediction_shas.values())
    assert prediction_shas["contract_sha"] == digest(
        ROOT / "phase1" / "critic_component_breadth_future_escrow_v1.json"
    )

    truth_sources = {
        "base_protocol_sha": ROOT
        / "phase1"
        / "score_channel_future_identifiability_protocol_v1.json",
        "base_producer_sha": ROOT / "phase1" / "score_channel_future_truth_support.py",
        "base_verifier_sha": ROOT / "phase1" / "verify_score_channel_future_truth_support.py",
        "raw_protocol_sha": ROOT
        / "phase1"
        / "score_channel_future_raw_grade_support_protocol_v1.json",
        "raw_producer_sha": ROOT / "phase1" / "score_channel_future_raw_grade_support.py",
        "raw_verifier_sha": ROOT / "phase1" / "verify_score_channel_future_raw_grade_support.py",
    }
    for name, path in truth_sources.items():
        value = literal_assignment(truth, name)
        assert re.fullmatch(r"[0-9a-f]{64}", value)
        assert value == digest(path)
    assert re.fullmatch(r"[0-9a-f]{64}", literal_assignment(truth, "grade_helpers_sha"))
    assert re.fullmatch(r"[0-9a-f]{40}", literal_assignment(truth, "mlebench_commit"))


def test_no_gpu_api_or_automatic_replay_path_exists() -> None:
    prediction = source(PREDICTION_RUNNER)
    truth = source(TRUTH_RUNNER)
    forbidden_command = re.compile(
        r"^\s*(?:sbatch|srun|qsub|bsub|curl|wget|nvidia-smi)(?:\s|$)",
        flags=re.MULTILINE | re.IGNORECASE,
    )
    for text in (prediction, truth):
        assert forbidden_command.search(text) is None
        assert "CUDA_VISIBLE_DEVICES" not in text
        assert "SLURM_" not in text
        assert "--provider" not in text
        assert "replay_submission_authorized\": true" not in text.lower()
        assert "clean_python=(" in text
        assert "  env -i" in text
        assert '"${clean_python[@]}" -m phase1.' in text
    assert "GPU=0 API=0 base-LLM updates=0" in prediction
    assert "GPU=0; API=0; model-fit=0; base-LLM-update=0" in truth
    assert '"gpu_jobs_authorized": 0' in truth
    assert '"effect_claim_authorized": False' in truth
    assert '"replay_submission_authorized": False' in truth


def test_prediction_and_both_truth_estimands_are_double_produced_and_verified() -> None:
    prediction = source(PREDICTION_RUNNER)
    truth = source(TRUTH_RUNNER)
    assert prediction.count("for replica in 1 2; do") == 2
    assert prediction.count("-m phase1.critic_component_breadth_future_escrow") == 1
    assert prediction.count("-m phase1.verify_critic_component_breadth_future_escrow") == 1
    assert 'diff -r "${root}/producer_1" "${root}/producer_2"' in prediction
    assert 'cmp "${root}/verification_1.json" "${root}/verification_2.json"' in prediction
    assert (
        "producer x2 plus non-truth-module independent source-refit verifier x2"
        in prediction
    )

    assert truth.count("for replica in a b; do") == 4
    for module in (
        "phase1.score_channel_future_truth_support",
        "phase1.verify_score_channel_future_truth_support",
        "phase1.score_channel_future_raw_grade_support",
        "phase1.verify_score_channel_future_raw_grade_support",
    ):
        assert truth.count(f"-m {module}") == 1
    for receipt in (
        "base_producer_reproducibility.diff",
        "base_verifier_reproducibility.diff",
        "raw_producer_reproducibility.diff",
        "raw_verifier_reproducibility.diff",
    ):
        assert truth.count(receipt) == 1


def test_both_runners_have_the_twelve_core_preflight_items() -> None:
    prediction = source(PREDICTION_RUNNER)
    truth = source(TRUTH_RUNNER)
    prediction_preflight = heredoc_body(prediction, 'cat > "${root}/preflight_12.txt" <<EOF')
    truth_preflight = heredoc_body(truth, 'cat > "${staging}/preflight_matrix.txt" <<EOF')

    prediction_items = re.findall(r"^(\d{2})_([a-z_]+)=", prediction_preflight, re.MULTILINE)
    assert [int(number) for number, _name in prediction_items] == list(range(1, 13))
    assert [name for _number, name in prediction_items] == [
        "direction",
        "question",
        "origin",
        "inputs",
        "unit",
        "matrix",
        "fairness",
        "model",
        "inference",
        "leakage",
        "reproducibility",
        "resources",
    ]

    truth_items = re.findall(r"^PREFLIGHT_(\d{2})_([A-Z_]+)=", truth_preflight, re.MULTILINE)
    assert [int(number) for number, _name in truth_items[:12]] == list(range(1, 13))
    assert len({number for number, _name in truth_items[:12]}) == 12
    assert truth_items[12] == ("13", "STOP")  # an allowed fail-closed extension


def test_three_hundred_run_cohort_is_supporting_evidence_not_the_sole_main_experiment() -> None:
    prediction = source(PREDICTION_RUNNER)
    truth = source(TRUTH_RUNNER)
    prediction_preflight = heredoc_body(prediction, 'cat > "${root}/preflight_12.txt" <<EOF')
    truth_preflight = heredoc_body(truth, 'cat > "${staging}/preflight_matrix.txt" <<EOF')
    assert "Decision Corpus plus Predictor Benchmark" in prediction_preflight
    assert "supporting hypothesis" in prediction_preflight
    assert "target 300 includes complete boundary-archive overshoot" in prediction_preflight
    assert "dual truth-support gate only" in truth_preflight
    assert "no effect, replay, winner, or method claim" in truth_preflight
    assert (
        "only an eligible estimand may receive a separately frozen replay matrix, "
        "power analysis, and user GPU-hour approval request"
    ) in truth

    cohort_first = re.compile(
        r"(?:300[- ]run|300[- ]physical[- ]run|300.{0,20}cohort).{0,80}"
        r"(?:sole|only|unique|main|primary|唯一主实验)",
        flags=re.IGNORECASE,
    )
    claim_first = re.compile(
        r"(?:sole|only|unique|main|primary|唯一主实验).{0,80}"
        r"(?:300[- ]run|300[- ]physical[- ]run|300.{0,20}cohort)",
        flags=re.IGNORECASE,
    )
    for text in (prediction, truth):
        assert cohort_first.search(text) is None
        assert claim_first.search(text) is None
        lowered = text.lower()
        assert "sole main experiment" not in lowered
        assert "only main experiment" not in lowered
        assert "唯一主实验" not in text
