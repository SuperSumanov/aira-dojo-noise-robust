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
scorer_repo=/research/d7/spc/yzyang4/worktrees/codex_wl_escrow_031edb3
scorer_commit=031edb34400781ca026bc9833ac7f850312ffb1c
python=/research/d7/spc/yzyang4/venvs/exp/bin/python
state_root=${WL_CHAIN_STATE_ROOT:-/research/d7/spc/yzyang4/prospective_decision_v1}
output_root=${WL_CHAIN_OUTPUT_ROOT:-/research/d7/spc/yzyang4/wl-graph-escrow-snapshot-chain}
monitor_root=${WL_CHAIN_MONITOR_ROOT:-/research/d7/spc/yzyang4/wl-graph-escrow-snapshot-chain-monitor}
seed_state=${WL_CHAIN_SEED_STATE:-${monitor_root}/SEED_STATE.tsv}
protocol=${scorer_repo}/phase1/wl_graph_prediction_protocol_v1.json
activation=/research/d7/spc/yzyang4/wl-graph-activation-031edb3-v1/activation_receipt.json
bundle_root=/research/d7/spc/yzyang4/wl-graph-multiview-f67157a-v1
bundle=${bundle_root}/result/wl_graph_multiview_scorer.npz
bundle_summary=${bundle_root}/result/summary.json
bundle_verification=${bundle_root}/independent_verification.json
chain_protocol=${control_repo}/phase1/provisional_first960_snapshot_chain_protocol_v1.json
chain_verifier=${control_repo}/phase1/verify_provisional_first960_snapshot_chain.py

protocol_sha=e3d299863eacf3655d17de378e7838bbebecfc347d751f33d19249b6b9f0bda3
activation_sha=0139670acc49c961e38e6851d0416d1e5bfa1c318024b50330c15d51823112fb
bundle_sha=df02cd1f5ba74be6b171ee9c377eeb58cf209a310a470b2ade671f2db03ee19e
bundle_summary_sha=d8d1b57172e4b63f391a0ca93b1213c0f040adf9592637c38d057ad6576622f5
bundle_verification_sha=9918e6797b8f48fa9bb72e8cb740d1d5fab0ef81c0a961809fef40250b3e6b6e
poll_seconds=${WL_CHAIN_POLL_SECONDS:-300}
max_polls=${WL_CHAIN_MAX_POLLS:-72}
minimum_new_runs=${WL_CHAIN_MINIMUM_NEW_RUNS:-12}

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
[[ "${minimum_new_runs}" =~ ^[1-9][0-9]*$ ]]
[[ "${control_commit}" =~ ^[0-9a-f]{40}$ ]]
test "$(git -C "${control_repo}" rev-parse HEAD)" = "${control_commit}"
test -z "$(git -C "${control_repo}" status --porcelain --untracked-files=all)"
test "$(git -C "${scorer_repo}" rev-parse HEAD)" = "${scorer_commit}"
test -z "$(git -C "${scorer_repo}" status --porcelain --untracked-files=all)"
test "$(sha256sum "${protocol}" | awk '{print $1}')" = "${protocol_sha}"
test "$(sha256sum "${activation}" | awk '{print $1}')" = "${activation_sha}"
test "$(sha256sum "${bundle}" | awk '{print $1}')" = "${bundle_sha}"
test "$(sha256sum "${bundle_summary}" | awk '{print $1}')" = "${bundle_summary_sha}"
test "$(sha256sum "${bundle_verification}" | awk '{print $1}')" = "${bundle_verification_sha}"
command -v strace >/dev/null

if [[ -f "${state_file}" ]]; then
  IFS=$'\t' read -r prior_snapshot prior_artifact prior_summary prior_all_runs < "${state_file}"
else
  test -f "${seed_state}"
  IFS=$'\t' read -r prior_snapshot prior_artifact prior_summary prior_all_runs < "${seed_state}"
  printf '%s\t%s\t%s\t%s\n' \
    "${prior_snapshot}" "${prior_artifact}" "${prior_summary}" "${prior_all_runs}" > "${state_file}"
fi
[[ "${prior_snapshot}" =~ ^[0-9a-f]{64}$ ]]
[[ "${prior_summary}" =~ ^[0-9a-f]{64}$ ]]
[[ "${prior_all_runs}" =~ ^[1-9][0-9]*$ ]]
test -d "${state_root}/snapshots/${prior_snapshot}"
test "$(sha256sum "${prior_artifact}/summary.json" | awk '{print $1}')" = "${prior_summary}"

export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 BLIS_NUM_THREADS=1

snapshot_metadata() {
  "${python}" - "$1" <<'PY'
import json
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
value = json.loads((root / "accumulator" / "summary.json").read_text(encoding="utf-8"))
inventory = value["inventory"]
closure = value["closure"]
print(
    inventory["eligible_runs"],
    inventory["provisional_first960_runs"],
    value["outputs"]["provisional_first960_runs_sha256"],
    int(
    closure["provided"] is True
    and closure["all_scheduled_runs_uploaded"] is True
    and closure["outcomes_read"] is False
    ),
)
PY
}

read -r prior_metadata_runs prior_selected_runs prior_selected_sha prior_closure_ready \
  < <(snapshot_metadata "${state_root}/snapshots/${prior_snapshot}")
test "${prior_metadata_runs}" = "${prior_all_runs}"
[[ "${prior_selected_runs}" =~ ^[1-9][0-9]*$ ]]
[[ "${prior_selected_sha}" =~ ^[0-9a-f]{64}$ ]]

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
  local current_all_runs=$2
  local stamp
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  output=${output_root}/${stamp}_${current_snapshot:0:12}
  test ! -e "${output}"
  mkdir "${output}"
  printf '%s\n' \
    '01_direction=Decision Corpus + Predictor Benchmark + Audit Protocol only; PASS' \
    '02_question=WL prediction escrow snapshot-chain update only; PASS' \
    '03_inputs=prior/current blind snapshots and frozen WL chain; PASS' \
    '04_forbidden_inputs=no label/outcome/score registry/regrade paths; PASS' \
    '05_order=ordering rule frozen,membership provisional until closure; PASS' \
    '06_batch_rule=batched before 960,immediate full-prefix churn or closure; PASS' \
    '07_negative_contract=shared prediction mutation/rank-unexplained rows fail; PASS' \
    '08_independence=original WL numerical verifier plus chain verifier; PASS' \
    '09_reproducibility=exact commits,hashes,commands,manifest; PASS' \
    '10_statistics=structural counts only,no effect metric; PASS' \
    '11_resources=single CPU,gpu=0,api=0,base update=0; PASS' \
    '12_security=strace and boundary-aware credential scan required; PASS' \
    '13_stop=any failure prevents state promotion; PASS' \
    > "${output}/preflight13.txt"
  {
    printf 'protocol=wl-snapshot-chain-monitor-v1\n'
    printf 'control_commit=%s\nscorer_commit=%s\n' "${control_commit}" "${scorer_commit}"
    printf 'script_sha256=%s\nprior_snapshot=%s\ncurrent_snapshot=%s\n' \
      "${script_sha}" "${prior_snapshot}" "${current_snapshot}"
    printf 'chain_protocol_sha256=%s\nchain_verifier_sha256=%s\n' \
      "${chain_protocol_sha}" "${chain_verifier_sha}"
    printf 'prior_all_runs=%s\ncurrent_all_runs=%s\nminimum_new_runs=%s\n' \
      "${prior_all_runs}" "${current_all_runs}" "${minimum_new_runs}"
    printf 'producer_runs=1\nindependent_verifier_runs=1\nchain_verifier_runs=1\n'
    printf 'gpu_jobs=0\napi_calls=0\nbase_llm_updates=0\neffect_metrics=0\n'
  } > "${output}/matrix.txt"

  producer=(
    env "PYTHONPATH=${scorer_repo}" "${python}" -m phase1.prospective_wl_graph_escrow
    --repo-root "${scorer_repo}" --source-commit "${scorer_commit}"
    --protocol "${protocol}" --expect-protocol-sha256 "${protocol_sha}"
    --activation-receipt "${activation}" --expect-activation-receipt-sha256 "${activation_sha}"
    --bundle "${bundle}" --expect-bundle-sha256 "${bundle_sha}"
    --bundle-summary "${bundle_summary}" --expect-bundle-summary-sha256 "${bundle_summary_sha}"
    --bundle-verification "${bundle_verification}" --expect-bundle-verification-sha256 "${bundle_verification_sha}"
    --state-root "${state_root}" --snapshot-root "${state_root}/snapshots/${current_snapshot}"
    --expect-snapshot-sha256 "${current_snapshot}" --output "${output}/artifact"
  )
  verifier=(
    env "PYTHONPATH=${scorer_repo}" "${python}" -m phase1.verify_prospective_wl_graph_escrow
    --state-root "${state_root}" --snapshot-root "${state_root}/snapshots/${current_snapshot}"
    --expect-snapshot-sha256 "${current_snapshot}"
    --bundle "${bundle}" --expect-bundle-sha256 "${bundle_sha}"
    --activation-receipt "${activation}" --expect-activation-receipt-sha256 "${activation_sha}"
    --artifact "${output}/artifact" --output "${output}/independent_verification.json"
  )
  printf '%q ' "${producer[@]}" > "${output}/producer_command.txt"
  printf '\n' >> "${output}/producer_command.txt"
  printf '%q ' "${verifier[@]}" > "${output}/independent_verifier_command.txt"
  printf '\n' >> "${output}/independent_verifier_command.txt"
  run_logged producer "${producer[@]}"
  run_logged independent_verifier "${verifier[@]}"
  current_summary=$(sha256sum "${output}/artifact/summary.json" | awk '{print $1}')
  chain=(
    env "PYTHONPATH=${control_repo}" "${python}" -m phase1.verify_provisional_first960_snapshot_chain
    --family wl_graph
    --prior-snapshot-root "${state_root}/snapshots/${prior_snapshot}"
    --current-snapshot-root "${state_root}/snapshots/${current_snapshot}"
    --expect-prior-snapshot-sha256 "${prior_snapshot}"
    --expect-current-snapshot-sha256 "${current_snapshot}"
    --prior-artifact "${prior_artifact}" --current-artifact "${output}/artifact"
    --expect-prior-summary-sha256 "${prior_summary}"
    --expect-current-summary-sha256 "${current_summary}"
    --current-independent-verification "${output}/independent_verification.json"
    --output "${output}/snapshot_chain_receipt.json"
  )
  printf '%q ' "${chain[@]}" > "${output}/snapshot_chain_command.txt"
  printf '\n' >> "${output}/snapshot_chain_command.txt"
  run_logged snapshot_chain "${chain[@]}"

  forbidden_hits=$( { grep -hEi '/prospective_decision_v1/(label|outcome|scorer)|label_vault|outcome_vault|score_registry|regrade' "${output}"/*.strace* || true; } | wc -l )
  credential_hits=$( { grep -rIPIl '(?<![A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' "${output}" || true; } | wc -l )
  printf 'forbidden_path_hits=%s\ncredential_content_file_hits=%s\n' "${forbidden_hits}" "${credential_hits}" > "${output}/security.txt"
  test "${forbidden_hits}" = 0
  test "${credential_hits}" = 0

  "${python}" - "${output}" <<'PY'
import hashlib
import json
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
summary = json.loads((root / "artifact" / "summary.json").read_text())
independent = json.loads((root / "independent_verification.json").read_text())
chain = json.loads((root / "snapshot_chain_receipt.json").read_text())
assert summary["scope"]["prospective_outcomes_read"] is False
assert summary["scope"]["effect_metrics_computed"] == []
assert independent["status"] == "INDEPENDENT_PROSPECTIVE_WL_GRAPH_ESCROW_VERIFIED"
assert independent["prospective_outcomes_read"] is False
assert independent["effect_metrics_computed"] == []
assert all(value == 0.0 for value in independent["maximum_absolute_score_difference"].values())
assert chain["status"] == "PROVISIONAL_FIRST960_SNAPSHOT_CHAIN_INDEPENDENTLY_VERIFIED"
assert chain["scope"]["prospective_outcomes_read"] is False
assert chain["scope"]["effect_metrics_computed"] == []
artifact_summary_sha = hashlib.sha256(
    (root / "artifact" / "summary.json").read_bytes()
).hexdigest()
assert independent["artifact_summary_sha256"] == artifact_summary_sha
receipt = {
    "snapshot_sha256": summary["inputs"]["snapshot_sha256"],
    "artifact_summary_sha256": artifact_summary_sha,
    "independent_verification_sha256": chain["independent_current_verification"]["path_sha256"],
    "selected_runs": chain["snapshots"]["current"]["selected_runs"],
    "added_runs": chain["cohort_churn"]["added_runs"],
    "removed_runs": chain["cohort_churn"]["removed_runs"],
    "common_pairs": chain["prediction_intersection"]["pairs"]["common"],
    "support_gate_is_provisional_until_closure": chain["closure"]["support_gate_is_provisional_until_closure"],
    "outcomes_read": False,
    "effect_metrics_computed": [],
}
(root / "monitor_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
PY
  touch "${output}/COMPLETE"
  (
    cd "${output}"
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
    sha256sum -c SHA256SUMS > manifest_verification.txt
  )
  chmod -R a-w "${output}"
  printf '%s\t%s\t%s\t%s\n' \
    "${current_snapshot}" "${output}/artifact" "${current_summary}" "${current_all_runs}" > "${state_file}.next"
  mv "${state_file}.next" "${state_file}"
  prior_snapshot=${current_snapshot}
  prior_artifact=${output}/artifact
  prior_summary=${current_summary}
  prior_all_runs=${current_all_runs}
  prior_selected_runs=${current_selected_runs}
  prior_selected_sha=${current_selected_sha}
  printf '%s update_complete snapshot=%s all_runs=%s output=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${current_snapshot}" "${current_all_runs}" "${output}" >> "${log}"
}

printf '%s monitor_start prior_snapshot=%s prior_all_runs=%s min_new_runs=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${prior_snapshot}" "${prior_all_runs}" "${minimum_new_runs}" >> "${log}"
for ((poll = 1; poll <= max_polls; poll += 1)); do
  current_snapshot=$(tr -d '\r\n' < "${state_root}/LATEST")
  [[ "${current_snapshot}" =~ ^[0-9a-f]{64}$ ]]
  if [[ "${current_snapshot}" != "${prior_snapshot}" ]]; then
    read -r current_all_runs current_selected_runs current_selected_sha closure_ready \
      < <(snapshot_metadata "${state_root}/snapshots/${current_snapshot}")
    delta=$((current_all_runs - prior_all_runs))
    test "${delta}" -ge 0
    membership_changed=0
    if [[ "${current_selected_sha}" != "${prior_selected_sha}" ]]; then
      membership_changed=1
    fi
    if (( closure_ready == 1 \
          || (membership_changed == 1 \
              && (delta >= minimum_new_runs || current_selected_runs == 960)) )); then
      process_snapshot "${current_snapshot}" "${current_all_runs}"
      if [[ -f "${output}/snapshot_chain_receipt.json" ]] \
        && "${python}" - "${output}/snapshot_chain_receipt.json" <<'PY'
import json
import pathlib
import sys
value = json.loads(pathlib.Path(sys.argv[1]).read_text())
raise SystemExit(0 if value["closure"]["final_first960_identity"] else 1)
PY
      then
        touch "${monitor_root}/FINAL_CLOSURE_OBSERVED"
        exit 0
      fi
    else
      printf '%s deferred poll=%s snapshot=%s delta_runs=%s selected_runs=%s membership_changed=%s threshold=%s closure=%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${current_snapshot}" "${delta}" \
        "${current_selected_runs}" "${membership_changed}" "${minimum_new_runs}" "${closure_ready}" >> "${log}"
    fi
  else
    printf '%s no_change poll=%s snapshot=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${current_snapshot}" >> "${log}"
  fi
  if (( poll < max_polls )); then
    sleep "${poll_seconds}"
  fi
done
printf '%s monitor_complete prior_snapshot=%s prior_all_runs=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${prior_snapshot}" "${prior_all_runs}" >> "${log}"
