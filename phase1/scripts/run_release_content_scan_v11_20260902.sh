#!/usr/bin/env bash
set -eo pipefail
source "$HOME/env_setup.sh"
set -u

readonly public_commit="${RELEASE_SCAN_PUBLIC_COMMIT:?set RELEASE_SCAN_PUBLIC_COMMIT}"
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly cards="${repo}/phase1/cards_current_v11.jsonl"
readonly cards_sha=6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75
readonly data_root=/research/d7/spc/yzyang4/mle-bench-data
readonly short="${public_commit:0:7}"
readonly base=/research/d7/spc/yzyang4/release-content-scan-v11
readonly worktree="${base}/worktree-${short}"
readonly root="${base}/formal-${short}-r1"
readonly private="${root}/private"
readonly public="${root}/public"
readonly log="${root}/runner.log"

fail() {
  local rc="$1"
  set +e
  printf '%s\n' "${rc}" >"${root}/FAILED_RC"
  chmod 0400 "${root}/FAILED_RC" 2>/dev/null || true
  printf 'RELEASE_CONTENT_SCAN_FORMAL=FAIL rc=%s root=%s\n' "${rc}" "${root}" >&2
  exit "${rc}"
}
trap 'fail $?' ERR

[[ "${public_commit}" =~ ^[0-9a-f]{40}$ ]]
[[ ! -e "${root}" ]]
mkdir -p "${base}" "${root}" "${private}" "${public}"
chmod 0700 "${root}" "${private}" "${public}"
: >"${log}"
chmod 0600 "${log}"
exec > >(tee -a "${log}") 2>&1

printf 'PREFLIGHT_01_OBJECTIVE=verbatim_historical_release_content_scan\n'
git -C "${repo}" cat-file -e "${public_commit}^{commit}"
printf 'PREFLIGHT_02_EXACT_COMMIT=%s\n' "${public_commit}"
[[ "$(sha256sum "${cards}" | awk '{print $1}')" == "${cards_sha}" ]]
[[ "$(stat -c '%s' "${cards}")" == 305750663 ]]
[[ "$(wc -l <"${cards}")" == 16012 ]]
printf 'PREFLIGHT_03_CARDS=16012/305750663/%s\n' "${cards_sha}"
[[ -d "${data_root}" ]]
printf 'PREFLIGHT_04_DATA_ROOT_PRESENT=true\n'
command -v grep >/dev/null
command -v strace >/dev/null
command -v timeout >/dev/null
printf 'PREFLIGHT_05_RUNTIME=grep/strace/timeout\n'
printf 'PREFLIGHT_06_FIELDS=stdout_tail/code_literal_or_comment\n'
printf 'PREFLIGHT_07_THRESHOLDS=40/12/24\n'
printf 'PREFLIGHT_08_PROSPECTIVE_PATHS_ALLOWED=false\n'
printf 'PREFLIGHT_09_PUBLIC_RAW_VALUES_ALLOWED=false\n'
printf 'PREFLIGHT_10_SCALE=16012_cards/25_tasks/23_prepared/1377069541_bytes\n'
printf 'PREFLIGHT_11_GPU_API_MODEL_FIT_BASE_UPDATE=0/0/0/0\n'
printf 'PREFLIGHT_12_TIMEOUT=14400s/task3600s\n'
printf 'PREFLIGHT_13_IMMUTABLE_V11=true\n'

GIT_LFS_SKIP_SMUDGE=1 git -c core.hooksPath=/dev/null -C "${repo}" worktree add --detach "${worktree}" "${public_commit}"
[[ "$(git -C "${worktree}" rev-parse HEAD)" == "${public_commit}" ]]
[[ -z "$(git -C "${worktree}" status --porcelain --untracked-files=no)" ]]

cd "${worktree}"
python -m pytest phase1/tests/test_release_content_scan.py -q | tee "${public}/focused_tests.txt"
python -m pytest phase1/tests -q | tee "${public}/full_tests.txt"

readonly summary_a="${public}/summary_a.json"
readonly summary_b="${public}/summary_b.json"
readonly private_a="${private}/private_manifest_a.json"
readonly private_b="${private}/private_manifest_b.json"
readonly verify_a="${public}/verification_a.json"
readonly verify_b="${public}/verification_b.json"

timeout 14400s nice -n 10 ionice -c2 -n7 \
  strace -ff -qq -e trace=file,network -o "${private}/producer_a.strace" \
  python -m phase1.release_content_scan \
    --cards "${cards}" \
    --expected-cards-sha256 "${cards_sha}" \
    --data-root "${data_root}" \
    --work-dir "${private}/scan_work" \
    --summary "${summary_a}" \
    --private-manifest "${private_a}" \
    --matcher grep \
    --task-timeout-s 3600

timeout 14400s nice -n 10 ionice -c2 -n7 \
  strace -ff -qq -e trace=file,network -o "${private}/producer_b.strace" \
  python -m phase1.release_content_scan \
    --cards "${cards}" \
    --expected-cards-sha256 "${cards_sha}" \
    --data-root "${data_root}" \
    --work-dir "${private}/scan_work" \
    --summary "${summary_b}" \
    --private-manifest "${private_b}" \
    --matcher grep \
    --task-timeout-s 3600 \
    --resume

cmp "${summary_a}" "${summary_b}"
cmp "${private_a}" "${private_b}"

timeout 14400s nice -n 10 ionice -c2 -n7 \
  strace -ff -qq -e trace=file,network -o "${private}/verifier_a.strace" \
  python -m phase1.verify_release_content_scan \
    --summary "${summary_a}" \
    --private-manifest "${private_a}" \
    --cards "${cards}" \
    --data-root "${data_root}" \
    --work-dir "${private}/scan_work" \
    --output "${verify_a}"

timeout 14400s nice -n 10 ionice -c2 -n7 \
  python -m phase1.verify_release_content_scan \
    --summary "${summary_a}" \
    --private-manifest "${private_a}" \
    --cards "${cards}" \
    --data-root "${data_root}" \
    --work-dir "${private}/scan_work" \
    --output "${verify_b}"
cmp "${verify_a}" "${verify_b}"

prospective_hits=$(grep -hE '/prospective_decision_v1|label_vault|outcome_vault|prediction_escrow' "${private}"/*.strace* 2>/dev/null | wc -l || true)
network_hits=$(grep -hE 'socket\(|connect\(|sendto\(|recvfrom\(' "${private}"/*.strace* 2>/dev/null | wc -l || true)
credential_hits=$(grep -hEi '(^|[^A-Za-z0-9])sk-[A-Za-z0-9._-]{12,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[A-Za-z0-9._-]{12,}|authorization:[[:space:]]*bearer' "${summary_a}" "${verify_a}" | wc -l || true)
[[ "${prospective_hits}" == 0 ]]
[[ "${network_hits}" == 0 ]]
[[ "${credential_hits}" == 0 ]]

python - "${summary_a}" "${verify_a}" "${public_commit}" "${public}/formal_summary.json" <<'PY'
import hashlib, json, pathlib, sys
summary_path, verify_path, commit, output_path = map(pathlib.Path, sys.argv[1:])
summary = json.loads(summary_path.read_text())
verification = json.loads(verify_path.read_text())
assert verification["status"] == "PASS"
assert summary["coverage"]["tasks_total"] == 25
assert summary["coverage"]["tasks_scanned"] == 23
assert summary["coverage"]["tasks_unscanned"] == 2
assert summary["coverage"]["unscanned_tasks"] == [
    "aptos2019-blindness-detection",
    "histopathologic-cancer-detection",
]
payload = {
    "protocol": "release-content-scan-formal-summary-v1",
    "status": "PASS_PARTIAL_COVERAGE",
    "source_commit": str(commit),
    "summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
    "verification_sha256": hashlib.sha256(verify_path.read_bytes()).hexdigest(),
    "cards_rows": summary["input"]["cards_rows"],
    "tasks_total": summary["coverage"]["tasks_total"],
    "tasks_scanned": summary["coverage"]["tasks_scanned"],
    "tasks_unscanned": summary["coverage"]["tasks_unscanned"],
    "candidate_patterns": summary["totals"]["candidate_patterns"],
    "matched_patterns": summary["totals"]["matched_patterns"],
    "affected_card_sum_across_tasks": summary["totals"]["affected_card_sum_across_tasks"],
    "prospective_paths_opened": False,
    "network_calls": 0,
    "credential_hits_public": 0,
    "gpu_api_model_fit_base_update": "0/0/0/0",
}
output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
PY

find "${public}" -type f -exec chmod 0400 {} +
find "${private}" -type f -exec chmod 0400 {} +
find "${private}" -type d -exec chmod 0500 {} +
chmod 0500 "${public}"
printf '%s\n' 'RELEASE_CONTENT_SCAN_FORMAL_PASS' >"${root}/COMPLETE"
chmod 0400 "${root}/COMPLETE" "${log}"
chmod 0500 "${root}"
printf 'RELEASE_CONTENT_SCAN_FORMAL=PASS root=%s\n' "${root}"
