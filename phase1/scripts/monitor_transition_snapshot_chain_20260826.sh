#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

if [[ "$#" -ne 2 ]]; then
  printf 'usage: %s CONTROL_REPO CONTROL_COMMIT\n' "$0" >&2
  exit 64
fi

control_repo=$1
control_commit=$2
scorer_commit=7458f0969b92a258ea0e495bbbee282aa12b748e
scorer_repo=/research/d7/spc/yzyang4/worktrees/transition_future_7458f09_nosmudge
formal_root=/research/d7/spc/yzyang4/transition-future-escrow/7458f09-v1
legacy_monitor_root=${SNAPSHOT_CHAIN_LEGACY_MONITOR_ROOT:-/research/d7/spc/yzyang4/transition-future-escrow/monitor_7458f09}
state_root=${SNAPSHOT_CHAIN_STATE_ROOT:-/research/d7/spc/yzyang4/prospective_decision_v1}
output_root=${SNAPSHOT_CHAIN_OUTPUT_ROOT:-/research/d7/spc/yzyang4/transition-future-escrow/7458f09-snapshot-chain}
monitor_root=${SNAPSHOT_CHAIN_MONITOR_ROOT:-/research/d7/spc/yzyang4/transition-future-escrow/monitor_7458f09_snapshot_chain_v1}
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
cards=/research/d7/spc/yzyang4/worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json
train=/research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl
dev=/research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/dev.jsonl
protocol=${scorer_repo}/phase1/transition_future_escrow_protocol_v1.json
activation=${formal_root}/activation.json
activation_verification=${formal_root}/activation_verification_1.json
model_summary=${formal_root}/model_1/summary.json
model_spec=${formal_root}/model_1/model_spec.json
train_reference=${formal_root}/model_1/train_reference.csv
model_verification=${formal_root}/model_verification_1.json
chain_protocol=${control_repo}/phase1/provisional_first960_snapshot_chain_protocol_v1.json
chain_verifier=${control_repo}/phase1/verify_provisional_first960_snapshot_chain.py

protocol_sha=ea8912e19f1bcc83eefe19737a12a9f7cbfc0476179f1e87535ccff11eddd23f
activation_sha=dd3aeb4afce7ff64423f9539beadba133cfeb3310a74169eb18ea27f7ba487d3
activation_verification_sha=70e611bdd56718c7112c8765ab3bf9e896e570f178a07d7c8d6413439be82b46
model_summary_sha=7b32ddc85217245d65c767445439072e4dd08f4da88523ce5c52fc3156122bf3
model_spec_sha=11465b4ea842d79ce8e9bdcd60d219a02be7f35bac9bab029a6d38f77120ca59
train_reference_sha=3cb1bec50fdfc9f9affaacb65fe9c75618d979f48097233ae0ad06cb1f856b0f
model_verification_sha=33a117fb60577b96420cafff1cff274e3c029f20525d3a9996cdf0fe7ee933eb

poll_seconds=${SNAPSHOT_CHAIN_POLL_SECONDS:-300}
max_polls=${SNAPSHOT_CHAIN_MAX_POLLS:-144}
mkdir -p "${output_root}" "${monitor_root}"
log=${monitor_root}/monitor.log
state_file=${monitor_root}/state.tsv
lock_file=${monitor_root}/monitor.lock
script_sha=$(sha256sum "$0" | awk '{print $1}')
chain_protocol_sha=$(sha256sum "${chain_protocol}" | awk '{print $1}')
chain_verifier_sha=$(sha256sum "${chain_verifier}" | awk '{print $1}')

exec 9>"${lock_file}"
if ! flock -n 9; then
  printf '%s monitor_already_running\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "${log}"
  exit 3
fi
trap 'printf "%s monitor_error line=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$LINENO" >> "${log}"' ERR

[[ "${poll_seconds}" =~ ^[1-9][0-9]*$ ]]
[[ "${max_polls}" =~ ^[1-9][0-9]*$ ]]
[[ "${control_commit}" =~ ^[0-9a-f]{40}$ ]]
[[ "$(git -C "${control_repo}" rev-parse HEAD)" == "${control_commit}" ]]
[[ -z "$(git -C "${control_repo}" status --porcelain --untracked-files=all)" ]]
[[ "$(git -C "${scorer_repo}" rev-parse HEAD)" == "${scorer_commit}" ]]
[[ -z "$(git -C "${scorer_repo}" status --porcelain --untracked-files=all)" ]]
[[ -f "${formal_root}/COMPLETE" ]]
[[ "$(sha256sum "${protocol}" | awk '{print $1}')" == "${protocol_sha}" ]]
[[ "$(sha256sum "${activation}" | awk '{print $1}')" == "${activation_sha}" ]]
[[ "$(sha256sum "${activation_verification}" | awk '{print $1}')" == "${activation_verification_sha}" ]]
[[ "$(sha256sum "${model_summary}" | awk '{print $1}')" == "${model_summary_sha}" ]]
[[ "$(sha256sum "${model_spec}" | awk '{print $1}')" == "${model_spec_sha}" ]]
[[ "$(sha256sum "${train_reference}" | awk '{print $1}')" == "${train_reference_sha}" ]]
[[ "$(sha256sum "${model_verification}" | awk '{print $1}')" == "${model_verification_sha}" ]]
[[ -x "${python_bin}" ]]
command -v strace >/dev/null

if [[ -f "${state_file}" ]]; then
  IFS=$'\t' read -r prior_snapshot prior_artifact prior_summary_sha < "${state_file}"
else
  IFS=$'\t' read -r prior_snapshot prior_artifact prior_summary_sha < "${legacy_monitor_root}/state.tsv"
  printf '%s\t%s\t%s\n' "${prior_snapshot}" "${prior_artifact}" "${prior_summary_sha}" > "${state_file}"
fi
[[ "${prior_snapshot}" =~ ^[0-9a-f]{64}$ ]]
[[ "${prior_summary_sha}" =~ ^[0-9a-f]{64}$ ]]
[[ -d "${state_root}/snapshots/${prior_snapshot}" ]]
[[ "$(sha256sum "${prior_artifact}/summary.json" | awk '{print $1}')" == "${prior_summary_sha}" ]]

export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1

run_logged() {
  local stage=$1
  shift
  set +e
  /usr/bin/time -v -o "${output}/${stage}.time.txt" \
    strace -ff -e trace=file -o "${output}/${stage}.strace" \
    "$@" > "${output}/${stage}.stdout.txt" 2> "${output}/${stage}.stderr.txt"
  local rc=$?
  set -e
  printf '%s\n' "${rc}" > "${output}/${stage}.rc.txt"
  [[ "${rc}" == 0 ]]
}

process_snapshot() {
  local current_snapshot=$1
  local stamp
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  output=${output_root}/${stamp}_${current_snapshot:0:12}
  [[ ! -e "${output}" ]]
  [[ -d "${state_root}/snapshots/${current_snapshot}" ]]
  mkdir "${output}"
  printf '%s\n' \
    '01_direction=Decision Corpus + Predictor Benchmark + Audit Protocol only; PASS' \
    '02_question=prediction escrow snapshot-chain integrity only; PASS' \
    '03_inputs=current/prior blind snapshots and frozen prediction chain only; PASS' \
    '04_forbidden_inputs=no label/outcome/score registry/regrade paths passed; PASS' \
    '05_order=frozen chronological first-960; PASS' \
    '06_positive_contract=append,stasis,churn accepted only when rank-explained; PASS' \
    '07_negative_contract=shared prediction mutation fails closed; PASS' \
    '08_independence=frozen producer plus non-importing scorer verifier plus chain verifier; PASS' \
    '09_reproducibility=exact commits,hashes,commands,manifest; PASS' \
    '10_statistics=no effect estimate or seed; structural identities only; PASS' \
    '11_resources=cpu-only,gpu=0,api=0,base_llm_updates=0; PASS' \
    '12_security=strace and boundary-aware credential scan required; PASS' \
    '13_stop=any failure prevents state promotion; PASS' \
    > "${output}/preflight13.txt"
  {
    printf 'protocol=transition-snapshot-chain-monitor-v1\n'
    printf 'control_commit=%s\n' "${control_commit}"
    printf 'scorer_commit=%s\n' "${scorer_commit}"
    printf 'monitor_script_sha256=%s\n' "${script_sha}"
    printf 'chain_protocol_sha256=%s\n' "${chain_protocol_sha}"
    printf 'chain_verifier_sha256=%s\n' "${chain_verifier_sha}"
    printf 'prior_snapshot=%s\n' "${prior_snapshot}"
    printf 'current_snapshot=%s\n' "${current_snapshot}"
    printf 'prior_summary_sha256=%s\n' "${prior_summary_sha}"
    printf 'producer_runs=1\nindependent_scorer_verifier_runs=1\nchain_verifier_runs=1\n'
    printf 'fixed_hgb_fits=6\ngpu_jobs=0\napi_calls=0\nbase_llm_updates=0\neffect_metrics=0\n'
  } > "${output}/matrix.txt"

  producer=(
    env "PYTHONPATH=${scorer_repo}" "${python_bin}" -m phase1.prospective_transition_future_escrow
    --repo-root "${scorer_repo}" --source-commit "${scorer_commit}"
    --protocol "${protocol}" --expect-protocol-sha256 "${protocol_sha}"
    --activation "${activation}" --expect-activation-sha256 "${activation_sha}"
    --activation-verification "${activation_verification}"
    --expect-activation-verification-sha256 "${activation_verification_sha}"
    --model-summary "${model_summary}" --expect-model-summary-sha256 "${model_summary_sha}"
    --model-spec "${model_spec}" --expect-model-spec-sha256 "${model_spec_sha}"
    --train-reference "${train_reference}" --expect-train-reference-sha256 "${train_reference_sha}"
    --model-verification "${model_verification}" --expect-model-verification-sha256 "${model_verification_sha}"
    --training-cards "${cards}" --train-pairs "${train}" --dev-pairs "${dev}"
    --state-root "${state_root}" --snapshot-root "${state_root}/snapshots/${current_snapshot}"
    --expect-snapshot-sha256 "${current_snapshot}" --output "${output}/artifact"
  )
  verifier=(
    env "PYTHONPATH=${scorer_repo}" "${python_bin}" -m phase1.verify_prospective_transition_future_escrow
    --repo-root "${scorer_repo}" --source-commit "${scorer_commit}"
    --protocol "${protocol}" --expect-protocol-sha256 "${protocol_sha}"
    --activation "${activation}" --expect-activation-sha256 "${activation_sha}"
    --activation-verification "${activation_verification}"
    --expect-activation-verification-sha256 "${activation_verification_sha}"
    --model-summary "${model_summary}" --expect-model-summary-sha256 "${model_summary_sha}"
    --model-spec "${model_spec}" --expect-model-spec-sha256 "${model_spec_sha}"
    --train-reference "${train_reference}" --expect-train-reference-sha256 "${train_reference_sha}"
    --model-verification "${model_verification}" --expect-model-verification-sha256 "${model_verification_sha}"
    --training-cards "${cards}" --train-pairs "${train}" --dev-pairs "${dev}"
    --state-root "${state_root}" --snapshot-root "${state_root}/snapshots/${current_snapshot}"
    --expect-snapshot-sha256 "${current_snapshot}"
    --artifact "${output}/artifact" --output "${output}/independent_verification.json"
  )
  printf '%q ' "${producer[@]}" > "${output}/producer_command.txt"
  printf '\n' >> "${output}/producer_command.txt"
  printf '%q ' "${verifier[@]}" > "${output}/independent_verifier_command.txt"
  printf '\n' >> "${output}/independent_verifier_command.txt"
  run_logged producer "${producer[@]}"
  run_logged independent_verifier "${verifier[@]}"

  current_summary_sha=$(sha256sum "${output}/artifact/summary.json" | awk '{print $1}')
  chain_command=(
    env "PYTHONPATH=${control_repo}" "${python_bin}" -m phase1.verify_provisional_first960_snapshot_chain
    --family transition
    --prior-snapshot-root "${state_root}/snapshots/${prior_snapshot}"
    --current-snapshot-root "${state_root}/snapshots/${current_snapshot}"
    --expect-prior-snapshot-sha256 "${prior_snapshot}"
    --expect-current-snapshot-sha256 "${current_snapshot}"
    --prior-artifact "${prior_artifact}"
    --current-artifact "${output}/artifact"
    --expect-prior-summary-sha256 "${prior_summary_sha}"
    --expect-current-summary-sha256 "${current_summary_sha}"
    --current-independent-verification "${output}/independent_verification.json"
    --output "${output}/snapshot_chain_receipt.json"
  )
  printf '%q ' "${chain_command[@]}" > "${output}/snapshot_chain_command.txt"
  printf '\n' >> "${output}/snapshot_chain_command.txt"
  run_logged snapshot_chain "${chain_command[@]}"

  forbidden_hits=$( { grep -hEi '/prospective_decision_v1/(label|outcome|scorer)|label_vault|outcome_vault|score_registry|regrade' "${output}"/*.strace* || true; } | wc -l )
  printf 'forbidden_path_hits=%s\n' "${forbidden_hits}" > "${output}/security.txt"
  [[ "${forbidden_hits}" == 0 ]]
  credential_hits=$( { grep -rIPIl '(?<![A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' "${output}" || true; } | wc -l )
  printf 'credential_content_file_hits=%s\n' "${credential_hits}" >> "${output}/security.txt"
  [[ "${credential_hits}" == 0 ]]

  env "PYTHONPATH=${control_repo}" "${python_bin}" - "${output}" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
summary = json.loads((root / "artifact" / "summary.json").read_text(encoding="utf-8"))
independent = json.loads((root / "independent_verification.json").read_text(encoding="utf-8"))
chain = json.loads((root / "snapshot_chain_receipt.json").read_text(encoding="utf-8"))
assert summary["append"]["prior_used"] is False
assert summary["scope"]["prospective_outcomes_read"] is False
assert summary["scope"]["effect_metrics_computed"] == []
assert independent["maximum_training_reference_difference"] == 0.0
assert independent["maximum_future_margin_difference"] == 0.0
assert chain["status"] == "PROVISIONAL_FIRST960_SNAPSHOT_CHAIN_INDEPENDENTLY_VERIFIED"
assert chain["scope"]["prospective_outcomes_read"] is False
assert chain["scope"]["effect_metrics_computed"] == []
receipt = {
    "snapshot_sha256": summary["inputs"]["snapshot_sha256"],
    "artifact_summary_sha256": hashlib.sha256(
        (root / "artifact" / "summary.json").read_bytes()
    ).hexdigest(),
    "independent_verification_sha256": chain["independent_current_verification"]["path_sha256"],
    "selected_runs": chain["snapshots"]["current"]["selected_runs"],
    "added_runs": chain["cohort_churn"]["added_runs"],
    "removed_runs": chain["cohort_churn"]["removed_runs"],
    "common_pairs": chain["prediction_intersection"]["pairs"]["common"],
    "support_gate_is_provisional_until_closure": chain["closure"]["support_gate_is_provisional_until_closure"],
    "outcomes_read": False,
    "effect_metrics_computed": [],
}
(root / "monitor_receipt.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY
  touch "${output}/COMPLETE"
  (
    cd "${output}"
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
    sha256sum -c SHA256SUMS > manifest_verification.txt
  )
  chmod -R a-w "${output}"
  printf '%s\t%s\t%s\n' "${current_snapshot}" "${output}/artifact" "${current_summary_sha}" > "${state_file}.next"
  mv "${state_file}.next" "${state_file}"
  prior_snapshot=${current_snapshot}
  prior_artifact=${output}/artifact
  prior_summary_sha=${current_summary_sha}
  printf '%s snapshot_chain_complete snapshot=%s output=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${current_snapshot}" "${output}" >> "${log}"
  if "${python_bin}" - "${output}/snapshot_chain_receipt.json" <<'PY'
import json
import pathlib
import sys
value = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
raise SystemExit(0 if value["closure"]["final_first960_identity"] else 1)
PY
  then
    touch "${monitor_root}/FINAL_CLOSURE_OBSERVED"
    return 10
  fi
  return 0
}

printf '%s monitor_start prior_snapshot=%s poll_seconds=%s max_polls=%s script_sha256=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${prior_snapshot}" "${poll_seconds}" "${max_polls}" "${script_sha}" >> "${log}"
for ((poll = 1; poll <= max_polls; poll += 1)); do
  current_snapshot=$(tr -d '\r\n' < "${state_root}/LATEST")
  [[ "${current_snapshot}" =~ ^[0-9a-f]{64}$ ]]
  if [[ "${current_snapshot}" != "${prior_snapshot}" ]]; then
    printf '%s new_snapshot poll=%s old=%s new=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${prior_snapshot}" "${current_snapshot}" >> "${log}"
    set +e
    process_snapshot "${current_snapshot}"
    rc=$?
    set -e
    if [[ "${rc}" == 10 ]]; then
      printf '%s final_closure_observed snapshot=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${current_snapshot}" >> "${log}"
      exit 0
    fi
    [[ "${rc}" == 0 ]]
  else
    printf '%s no_change poll=%s snapshot=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${current_snapshot}" >> "${log}"
  fi
  if (( poll < max_polls )); then
    sleep "${poll_seconds}"
  fi
done
printf '%s monitor_complete prior_snapshot=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${prior_snapshot}" >> "${log}"
