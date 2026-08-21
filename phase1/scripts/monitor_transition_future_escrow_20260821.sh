#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

commit=7458f0969b92a258ea0e495bbbee282aa12b748e
repo=/research/d7/spc/yzyang4/worktrees/transition_future_7458f09_nosmudge
formal_root=/research/d7/spc/yzyang4/transition-future-escrow/7458f09-v1
append_root=/research/d7/spc/yzyang4/transition-future-escrow/7458f09-append
monitor_root=/research/d7/spc/yzyang4/transition-future-escrow/monitor_7458f09
state_root=/research/d7/spc/yzyang4/prospective_decision_v1
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
cards=/research/d7/spc/yzyang4/worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json
train=/research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl
dev=/research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/dev.jsonl
protocol=${repo}/phase1/transition_future_escrow_protocol_v1.json
activation=${formal_root}/activation.json
activation_verification=${formal_root}/activation_verification_1.json
model_summary=${formal_root}/model_1/summary.json
model_spec=${formal_root}/model_1/model_spec.json
train_reference=${formal_root}/model_1/train_reference.csv
model_verification=${formal_root}/model_verification_1.json

protocol_sha=ea8912e19f1bcc83eefe19737a12a9f7cbfc0476179f1e87535ccff11eddd23f
activation_sha=dd3aeb4afce7ff64423f9539beadba133cfeb3310a74169eb18ea27f7ba487d3
activation_verification_sha=70e611bdd56718c7112c8765ab3bf9e896e570f178a07d7c8d6413439be82b46
model_summary_sha=7b32ddc85217245d65c767445439072e4dd08f4da88523ce5c52fc3156122bf3
model_spec_sha=11465b4ea842d79ce8e9bdcd60d219a02be7f35bac9bab029a6d38f77120ca59
train_reference_sha=3cb1bec50fdfc9f9affaacb65fe9c75618d979f48097233ae0ad06cb1f856b0f
model_verification_sha=33a117fb60577b96420cafff1cff274e3c029f20525d3a9996cdf0fe7ee933eb
initial_snapshot=83ab1d681ed863d2374a6648df4801e6dbd6fb80d89f4f20cec8d46de1d5c047
initial_prior=${formal_root}/escrow_1
initial_prior_sha=a3a2977ea2efb7c439e9669ffa24ffe7d6e9e2a5ce7f16a7e40ab8bca5649b50

poll_seconds=${TRANSITION_MONITOR_POLL_SECONDS:-300}
max_polls=${TRANSITION_MONITOR_MAX_POLLS:-144}
script_sha=$(sha256sum "$0" | awk '{print $1}')
mkdir -p "${append_root}" "${monitor_root}"
log=${monitor_root}/monitor.log
state_file=${monitor_root}/state.tsv
lock_file=${monitor_root}/monitor.lock
exec 9>"${lock_file}"
if ! flock -n 9; then
  printf '%s monitor_already_running\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "${log}"
  exit 3
fi
trap 'printf "%s monitor_error line=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$LINENO" >> "${log}"' ERR

[[ "${poll_seconds}" =~ ^[1-9][0-9]*$ ]]
[[ "${max_polls}" =~ ^[1-9][0-9]*$ ]]
[[ "$(git -C "${repo}" rev-parse HEAD)" == "${commit}" ]]
[[ -f "${formal_root}/COMPLETE" ]]
[[ "$(cat "${formal_root}/trace_audit.txt")" == "prospective_forbidden_path_hits=0" ]]
[[ "$(sha256sum "${protocol}" | awk '{print $1}')" == "${protocol_sha}" ]]
[[ "$(sha256sum "${activation}" | awk '{print $1}')" == "${activation_sha}" ]]
[[ "$(sha256sum "${activation_verification}" | awk '{print $1}')" == "${activation_verification_sha}" ]]
[[ "$(sha256sum "${model_summary}" | awk '{print $1}')" == "${model_summary_sha}" ]]
[[ "$(sha256sum "${model_spec}" | awk '{print $1}')" == "${model_spec_sha}" ]]
[[ "$(sha256sum "${train_reference}" | awk '{print $1}')" == "${train_reference_sha}" ]]
[[ "$(sha256sum "${model_verification}" | awk '{print $1}')" == "${model_verification_sha}" ]]

if [[ -f "${state_file}" ]]; then
  IFS=$'\t' read -r last_snapshot prior_artifact prior_summary_sha < "${state_file}"
else
  last_snapshot=${initial_snapshot}
  prior_artifact=${initial_prior}
  prior_summary_sha=${initial_prior_sha}
  printf '%s\t%s\t%s\n' "${last_snapshot}" "${prior_artifact}" "${prior_summary_sha}" > "${state_file}"
fi
[[ "${last_snapshot}" =~ ^[0-9a-f]{64}$ ]]
[[ "${prior_summary_sha}" =~ ^[0-9a-f]{64}$ ]]
[[ "${prior_artifact}" == "${formal_root}"/* || "${prior_artifact}" == "${append_root}"/* ]]
[[ "$(sha256sum "${prior_artifact}/summary.json" | awk '{print $1}')" == "${prior_summary_sha}" ]]

export PYTHONPATH=${repo}
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
    "$@" > "${output}/${stage}.stdout.txt" 2> "${output}/${stage}.stderr.txt"
  local rc=$?
  set -e
  printf '%s\n' "${rc}" > "${output}/${stage}.rc.txt"
  [[ "${rc}" == 0 ]]
}

append_snapshot() {
  local snapshot=$1
  local stamp
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  output=${append_root}/${stamp}_${snapshot:0:12}
  [[ ! -e "${output}" ]]
  [[ -d "${state_root}/snapshots/${snapshot}" ]]
  mkdir "${output}"
  {
    echo "protocol=transition-future-escrow-monitor-append-v1"
    echo "source_commit=${commit}"
    echo "monitor_script_sha256=${script_sha}"
    echo "snapshot=${snapshot}"
    echo "prior_artifact=${prior_artifact}"
    echo "prior_summary_sha256=${prior_summary_sha}"
    echo "producer_runs=1"
    echo "independent_verifier_runs=1"
    echo "fixed_hgb_fits=6"
    echo "gpu_jobs=0"
    echo "api_calls=0"
    echo "prospective_outcome_paths_passed=0"
    echo "effect_metrics=0"
  } > "${output}/preflight_matrix.txt"

  local producer=(
    "${python_bin}" -m phase1.prospective_transition_future_escrow
    --repo-root "${repo}" --source-commit "${commit}"
    --protocol "${protocol}" --expect-protocol-sha256 "${protocol_sha}"
    --activation "${activation}" --expect-activation-sha256 "${activation_sha}"
    --activation-verification "${activation_verification}"
    --expect-activation-verification-sha256 "${activation_verification_sha}"
    --model-summary "${model_summary}" --expect-model-summary-sha256 "${model_summary_sha}"
    --model-spec "${model_spec}" --expect-model-spec-sha256 "${model_spec_sha}"
    --train-reference "${train_reference}" --expect-train-reference-sha256 "${train_reference_sha}"
    --model-verification "${model_verification}" --expect-model-verification-sha256 "${model_verification_sha}"
    --training-cards "${cards}" --train-pairs "${train}" --dev-pairs "${dev}"
    --state-root "${state_root}" --snapshot-root "${state_root}/snapshots/${snapshot}"
    --expect-snapshot-sha256 "${snapshot}"
    --prior-artifact "${prior_artifact}" --expect-prior-summary-sha256 "${prior_summary_sha}"
    --output "${output}/artifact"
  )
  local verifier=(
    "${python_bin}" -m phase1.verify_prospective_transition_future_escrow
    --repo-root "${repo}" --source-commit "${commit}"
    --protocol "${protocol}" --expect-protocol-sha256 "${protocol_sha}"
    --activation "${activation}" --expect-activation-sha256 "${activation_sha}"
    --activation-verification "${activation_verification}"
    --expect-activation-verification-sha256 "${activation_verification_sha}"
    --model-summary "${model_summary}" --expect-model-summary-sha256 "${model_summary_sha}"
    --model-spec "${model_spec}" --expect-model-spec-sha256 "${model_spec_sha}"
    --train-reference "${train_reference}" --expect-train-reference-sha256 "${train_reference_sha}"
    --model-verification "${model_verification}" --expect-model-verification-sha256 "${model_verification_sha}"
    --training-cards "${cards}" --train-pairs "${train}" --dev-pairs "${dev}"
    --state-root "${state_root}" --snapshot-root "${state_root}/snapshots/${snapshot}"
    --expect-snapshot-sha256 "${snapshot}"
    --prior-artifact "${prior_artifact}" --expect-prior-summary-sha256 "${prior_summary_sha}"
    --artifact "${output}/artifact" --output "${output}/verification.json"
  )
  printf '%q ' "${producer[@]}" > "${output}/producer_command.txt"
  printf '\n' >> "${output}/producer_command.txt"
  printf '%q ' "${verifier[@]}" > "${output}/verifier_command.txt"
  printf '\n' >> "${output}/verifier_command.txt"
  run_logged producer strace -ff -e trace=file -o "${output}/producer.strace" "${producer[@]}"
  run_logged verifier strace -ff -e trace=file -o "${output}/verifier.strace" "${verifier[@]}"

  local forbidden_hits
  forbidden_hits=$( { grep -hEi '/(scores?|vault|grades?)/|outcome_registry|score_registry|regrade|raw_archive|\.env' \
    "${output}"/*.strace* || true; } | wc -l )
  printf 'prospective_forbidden_path_hits=%s\n' "${forbidden_hits}" > "${output}/trace_audit.txt"
  [[ "${forbidden_hits}" == 0 ]]
  local credential_hits
  credential_hits=$( { grep -rIEl '(sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' \
    "${output}" || true; } | wc -l )
  printf 'artifact_files_with_credential_shape_hits=%s\n' "${credential_hits}" > "${output}/integrity_postcheck.txt"
  [[ "${credential_hits}" == 0 ]]

  "${python_bin}" - "${output}" "${snapshot}" "${prior_summary_sha}" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
snapshot = sys.argv[2]
prior_sha = sys.argv[3]
summary = json.loads((root / "artifact/summary.json").read_text())
verification = json.loads((root / "verification.json").read_text())
assert summary["inputs"]["snapshot_sha256"] == snapshot
assert summary["append"]["prior_summary_sha256"] == prior_sha
assert summary["append"]["prior_used"] is True
assert summary["append"]["survival_exact"] is True
assert summary["scope"]["prospective_outcomes_read"] is False
assert summary["scope"]["effect_metrics_computed"] == []
assert verification["maximum_training_reference_difference"] == 0.0
assert verification["maximum_future_margin_difference"] == 0.0
receipt = {
    "eligible_pairs": summary["support"]["inventory"]["eligible_pairs"],
    "eligible_runs": summary["support"]["inventory"]["eligible_runs"],
    "eligible_tasks": summary["support"]["inventory"]["eligible_tasks"],
    "effect_metrics_computed": [],
    "prior_pairs": summary["append"]["prior_pairs"],
    "prior_survival_exact": summary["append"]["survival_exact"],
    "snapshot_sha256": snapshot,
    "status": summary["status"],
    "strict_pairs": summary["support"]["inventory"]["strict_pairs"],
    "summary_sha256": hashlib.sha256((root / "artifact/summary.json").read_bytes()).hexdigest(),
}
(root / "monitor_receipt.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
    encoding="utf-8",
)
PY
  (
    cd "${output}"
    find . -type f ! -name output_manifest.sha256 ! -name manifest_verification.txt -printf '%P\0' \
      | sort -z | xargs -0 sha256sum > output_manifest.sha256
    sha256sum -c output_manifest.sha256 > manifest_verification.txt
  )
  local next_sha
  next_sha=$(sha256sum "${output}/artifact/summary.json" | awk '{print $1}')
  chmod -R a-w "${output}"
  printf '%s\t%s\t%s\n' "${snapshot}" "${output}/artifact" "${next_sha}" > "${state_file}.next"
  mv "${state_file}.next" "${state_file}"
  last_snapshot=${snapshot}
  prior_artifact=${output}/artifact
  prior_summary_sha=${next_sha}
  printf '%s append_complete snapshot=%s output=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${snapshot}" "${output}" >> "${log}"
}

printf '%s monitor_start last_snapshot=%s poll_seconds=%s max_polls=%s script_sha256=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${last_snapshot}" "${poll_seconds}" "${max_polls}" "${script_sha}" >> "${log}"
for ((poll = 1; poll <= max_polls; poll += 1)); do
  snapshot=$(cat "${state_root}/LATEST")
  [[ "${snapshot}" =~ ^[0-9a-f]{64}$ ]]
  if [[ "${snapshot}" != "${last_snapshot}" ]]; then
    printf '%s new_snapshot poll=%s old=%s new=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${last_snapshot}" "${snapshot}" >> "${log}"
    append_snapshot "${snapshot}"
  else
    printf '%s no_change poll=%s snapshot=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${snapshot}" >> "${log}"
  fi
  if (( poll < max_polls )); then
    sleep "${poll_seconds}"
  fi
done
printf '%s monitor_complete last_snapshot=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${last_snapshot}" >> "${log}"
