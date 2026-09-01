#!/usr/bin/env bash
set -eo pipefail
umask 077
source "$HOME/env_setup.sh"
set -u

readonly public_commit="${RELEASE_TIER_PUBLIC_COMMIT:?set RELEASE_TIER_PUBLIC_COMMIT}"
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly cards="${repo}/phase1/cards_current_v11.jsonl"
readonly cards_sha=6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75
readonly upstream=/research/d7/spc/yzyang4/release-content-scan-v11/formal-fc41932-r1
readonly scan_summary="${upstream}/public/summary_a.json"
readonly scan_summary_sha=9ba53816984850397eeaf0dd80cd685cae2df6d602a7ab17aa0893852e703927
readonly scan_private="${upstream}/private/private_manifest_a.json"
readonly scan_private_sha=616e95f7cd85965d98975b6643b7bfe1cfe634a080ed3e8ca29776fda81388f7
readonly scan_verification="${upstream}/public/verification_a.json"
readonly scan_verification_sha=047a70b2ea189193d684aab41c04362035f4edd5119ddf90ace5b39342f1cf77
readonly scan_formal_summary="${upstream}/public/formal_summary.json"
readonly scan_formal_summary_sha=16a8b7045a5cddf3941f49f6637ef4c3a78149a762407b68587ae300c0dfe235
readonly scan_complete="${upstream}/COMPLETE"
readonly scan_complete_sha=3bc901e971ad845cda587a2ff71002d98bd03ffae1df39f39d898755dd49da5a
readonly short="${public_commit:0:7}"
readonly base=/research/d7/spc/yzyang4/release-content-tier-v1
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
  printf 'RELEASE_CONTENT_TIER_FORMAL=FAIL rc=%s root=%s\n' "${rc}" "${root}" >&2
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

printf 'PREFLIGHT_01_OBJECTIVE=conservative_v11_release_content_tiers\n'
git -C "${repo}" cat-file -e "${public_commit}^{commit}"
printf 'PREFLIGHT_02_EXACT_COMMIT=%s\n' "${public_commit}"
[[ ! -e "${upstream}/FAILED_RC" && -f "${scan_complete}" ]]
[[ "$(sha256sum "${scan_complete}" | awk '{print $1}')" == "${scan_complete_sha}" ]]
[[ "$(sha256sum "${scan_summary}" | awk '{print $1}')" == "${scan_summary_sha}" ]]
[[ "$(sha256sum "${scan_private}" | awk '{print $1}')" == "${scan_private_sha}" ]]
[[ "$(sha256sum "${scan_verification}" | awk '{print $1}')" == "${scan_verification_sha}" ]]
[[ "$(sha256sum "${scan_formal_summary}" | awk '{print $1}')" == "${scan_formal_summary_sha}" ]]
printf 'PREFLIGHT_03_UPSTREAM_SCAN=complete/hash_locked/postflight_passed\n'
[[ "$(sha256sum "${cards}" | awk '{print $1}')" == "${cards_sha}" ]]
[[ "$(wc -l <"${cards}")" == 16012 ]]
printf 'PREFLIGHT_04_CARDS=16012/%s\n' "${cards_sha}"
[[ -x "${python_bin}" ]]
"${python_bin}" -c 'import pytest'
command -v strace >/dev/null
command -v timeout >/dev/null
printf 'PREFLIGHT_05_RUNTIME=exp-python-with-pytest/strace/timeout\n'
printf 'PREFLIGHT_06_RULE=frozen_before_task_or_card_disposition\n'
printf 'PREFLIGHT_07_WHOLE_CARD_CONSERVATISM=true\n'
printf 'PREFLIGHT_08_PUBLIC_CARD_HASHES_ALLOWED=false\n'
printf 'PREFLIGHT_09_PRIVATE_RAW_IDS_OR_VALUES_ALLOWED=false\n'
printf 'PREFLIGHT_10_PROSPECTIVE_PATHS_ALLOWED=false\n'
printf 'PREFLIGHT_11_GPU_PAID_API_MODEL_FIT_BASE_UPDATE=0/0/0/0\n'

GIT_LFS_SKIP_SMUDGE=1 git -c core.hooksPath=/dev/null -C "${repo}" worktree add --detach "${worktree}" "${public_commit}"
[[ "$(git -C "${worktree}" rev-parse HEAD)" == "${public_commit}" ]]
[[ -z "$(git -C "${worktree}" status --porcelain --untracked-files=no)" ]]

cd "${worktree}"
readonly protocol=phase1/release_content_tier_protocol_v1.json
readonly protocol_sha=88cd6f1063f89e14a470c04a6af45c5f8ba2359fe5ba7ecf4e48bd783ed55d6c
readonly producer=phase1/build_release_content_tiers.py
readonly producer_sha=350db21a04ea0837b09be6b1ba8ae069018bb6fd4243a77b475b7608f384936b
readonly verifier=phase1/verify_release_content_tiers.py
readonly verifier_sha=dd685278e86381cf44f6657dbdd531dbbc92cf3e06713bd50ff83226a42ecf46
readonly focused_test=phase1/tests/test_release_content_tiers.py
readonly focused_test_sha=ef4b8c9bce692cb37c541e70ab631a6c00b848d1aaef7081c4848874913af85b
[[ "$(sha256sum "${protocol}" | awk '{print $1}')" == "${protocol_sha}" ]]
[[ "$(sha256sum "${producer}" | awk '{print $1}')" == "${producer_sha}" ]]
[[ "$(sha256sum "${verifier}" | awk '{print $1}')" == "${verifier_sha}" ]]
[[ "$(sha256sum "${focused_test}" | awk '{print $1}')" == "${focused_test_sha}" ]]
"${python_bin}" -m pytest "${focused_test}" -q | tee "${public}/focused_tests.txt"
"${python_bin}" -m pytest phase1/tests -q | tee "${public}/full_tests.txt"

readonly public_a="${public}/tier_summary_a.json"
readonly public_b="${public}/tier_summary_b.json"
readonly private_a="${private}/tier_manifest_a.json"
readonly private_b="${private}/tier_manifest_b.json"
readonly verify_a="${public}/verification_a.json"
readonly verify_b="${public}/verification_b.json"

timeout 3600s nice -n 10 ionice -c2 -n7 \
  strace -ff -qq -e trace=file,network -o "${private}/producer_a.strace" \
  "${python_bin}" -m phase1.build_release_content_tiers \
    --protocol "${protocol}" --protocol-sha256 "${protocol_sha}" \
    --scan-summary "${scan_summary}" --scan-summary-sha256 "${scan_summary_sha}" \
    --scan-private-manifest "${scan_private}" --scan-private-manifest-sha256 "${scan_private_sha}" \
    --cards "${cards}" --cards-sha256 "${cards_sha}" \
    --public-output "${public_a}" --private-output "${private_a}"

timeout 3600s nice -n 10 ionice -c2 -n7 \
  strace -ff -qq -e trace=file,network -o "${private}/producer_b.strace" \
  "${python_bin}" -m phase1.build_release_content_tiers \
    --protocol "${protocol}" --protocol-sha256 "${protocol_sha}" \
    --scan-summary "${scan_summary}" --scan-summary-sha256 "${scan_summary_sha}" \
    --scan-private-manifest "${scan_private}" --scan-private-manifest-sha256 "${scan_private_sha}" \
    --cards "${cards}" --cards-sha256 "${cards_sha}" \
    --public-output "${public_b}" --private-output "${private_b}"
cmp "${public_a}" "${public_b}"
cmp "${private_a}" "${private_b}"

readonly public_a_sha="$(sha256sum "${public_a}" | awk '{print $1}')"
readonly private_a_sha="$(sha256sum "${private_a}" | awk '{print $1}')"
timeout 3600s nice -n 10 ionice -c2 -n7 \
  strace -ff -qq -e trace=file,network -o "${private}/verifier_a.strace" \
  "${python_bin}" -m phase1.verify_release_content_tiers \
    --protocol "${protocol}" --protocol-sha256 "${protocol_sha}" \
    --scan-summary "${scan_summary}" --scan-summary-sha256 "${scan_summary_sha}" \
    --scan-private-manifest "${scan_private}" --scan-private-manifest-sha256 "${scan_private_sha}" \
    --cards "${cards}" --cards-sha256 "${cards_sha}" \
    --claimed-public "${public_a}" --claimed-public-sha256 "${public_a_sha}" \
    --claimed-private "${private_a}" --claimed-private-sha256 "${private_a_sha}" \
    --output "${verify_a}"

"${python_bin}" -m phase1.verify_release_content_tiers \
  --protocol "${protocol}" --protocol-sha256 "${protocol_sha}" \
  --scan-summary "${scan_summary}" --scan-summary-sha256 "${scan_summary_sha}" \
  --scan-private-manifest "${scan_private}" --scan-private-manifest-sha256 "${scan_private_sha}" \
  --cards "${cards}" --cards-sha256 "${cards_sha}" \
  --claimed-public "${public_a}" --claimed-public-sha256 "${public_a_sha}" \
  --claimed-private "${private_a}" --claimed-private-sha256 "${private_a_sha}" \
  --output "${verify_b}"
cmp "${verify_a}" "${verify_b}"

prospective_hits=$(grep -hE '/prospective_decision_v1|label_vault|outcome_vault|prediction_escrow' "${private}"/*.strace* 2>/dev/null | wc -l || true)
network_hits=$(grep -hE 'socket\(|connect\(|sendto\(|recvfrom\(' "${private}"/*.strace* 2>/dev/null | wc -l || true)
credential_hits=$(grep -hEi '(^|[^A-Za-z0-9])sk-[A-Za-z0-9._-]{12,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[A-Za-z0-9._-]{12,}|authorization:[[:space:]]*bearer' "${public_a}" "${verify_a}" | wc -l || true)
absolute_path_hits=$(grep -hE '/research/|/home/|C:\\' "${public_a}" "${verify_a}" | wc -l || true)
[[ "${prospective_hits}" == 0 ]]
[[ "${network_hits}" == 0 ]]
[[ "${credential_hits}" == 0 ]]
[[ "${absolute_path_hits}" == 0 ]]

"${python_bin}" - "${public_a}" "${verify_a}" "${public_commit}" "${public}/formal_summary.json" <<'PY'
import hashlib, json, pathlib, sys
result_path, verify_path, commit, output_path = map(pathlib.Path, sys.argv[1:])
result = json.loads(result_path.read_text())
verification = json.loads(verify_path.read_text())
assert result["status"] == "COMPLETE_PENDING_EXTERNAL_RELEASE_GATES"
assert verification["status"] == "INDEPENDENT_RECONSTRUCTION_EXACT"
totals = result["totals"]
assert totals["cards"] == 16012
assert totals["content_review_eligible_cards"] + totals["structure_only_cards"] == totals["cards"]
assert verification["cards_reconstructed"] == totals["cards"]
assert verification["structure_only_rows_reconstructed"] == totals["structure_only_cards"]
payload = {
    "protocol": "decision-corpus-release-content-tier-formal-summary-v1",
    "status": "PASS_PENDING_EXTERNAL_RELEASE_GATES",
    "source_commit": str(commit),
    "tier_summary_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
    "verification_sha256": hashlib.sha256(verify_path.read_bytes()).hexdigest(),
    "cards": totals["cards"],
    "content_review_eligible_cards": totals["content_review_eligible_cards"],
    "structure_only_cards": totals["structure_only_cards"],
    "structure_only_due_matched_pattern": totals["structure_only_due_matched_pattern"],
    "structure_only_due_unscanned_task": totals["structure_only_due_unscanned_task"],
    "content_review_eligible_fraction": totals["content_review_eligible_fraction"],
    "release_clearance": False,
    "prospective_paths_opened": False,
    "network_calls": 0,
    "credential_hits_public": 0,
    "gpu_paid_api_model_fit_base_update": "0/0/0/0",
}
output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
PY

find "${public}" -type f -exec chmod 0400 {} +
find "${private}" -type f -exec chmod 0400 {} +
find "${private}" -type d -exec chmod 0500 {} +
chmod 0500 "${public}"
printf '%s\n' 'RELEASE_CONTENT_TIER_FORMAL_PASS' >"${root}/COMPLETE"
chmod 0400 "${root}/COMPLETE" "${log}"
chmod 0500 "${root}"
printf 'RELEASE_CONTENT_TIER_FORMAL=PASS root=%s\n' "${root}"
