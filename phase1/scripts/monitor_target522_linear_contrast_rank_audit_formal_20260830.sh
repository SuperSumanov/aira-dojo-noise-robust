#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -Eeo pipefail
set -u
umask 077

if [[ $# -ne 10 ]]; then
  echo 'usage: monitor_target522_linear_contrast_rank_audit_formal_20260830.sh {start|resume} MONITOR_ROOT SOURCE_COMMIT EXECUTION_SHA PROTOCOL_SHA ANALYZER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA MONITOR_SHA' >&2
  exit 64
fi
readonly mode=$1
readonly root=$2
readonly source_commit=$3
readonly execution_sha=$4
readonly protocol_sha=$5
readonly analyzer_sha=$6
readonly verifier_sha=$7
readonly test_sha=$8
readonly runner_sha=$9
readonly monitor_sha=${10}
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly stage_a=/research/d7/spc/yzyang4/vertex-cost-contrast-target522/formal-4fc9c3e-selection-v1
readonly stage_a_monitor=/research/d7/spc/yzyang4/vertex-cost-contrast-target522/formal-monitor-4fc9c3e-selection-v1
readonly formal_output=/research/d7/spc/yzyang4/target522-linear-contrast-rank/formal-${source_commit:0:7}-v1
readonly execution_rel=phase1/target522_linear_contrast_rank_execution_v1.json
readonly protocol_rel=phase1/target522_linear_contrast_rank_audit_v1.json
readonly analyzer_rel=phase1/audit_target522_linear_contrast_rank.py
readonly verifier_rel=phase1/verify_target522_linear_contrast_rank.py
readonly test_rel=phase1/tests/test_target522_linear_contrast_rank.py
readonly runner_rel=phase1/scripts/run_target522_linear_contrast_rank_audit_formal_20260830.sh
readonly monitor_rel=phase1/scripts/monitor_target522_linear_contrast_rank_audit_formal_20260830.sh
readonly credential_pattern='(^|[^A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'

[[ $mode == start || $mode == resume ]]
[[ $root =~ ^/research/d7/spc/yzyang4/target522-linear-contrast-rank/formal-monitor-[A-Za-z0-9._-]+$ ]]
[[ $source_commit =~ ^[0-9a-f]{40}$ ]]
for value in "$execution_sha" "$protocol_sha" "$analyzer_sha" "$verifier_sha" \
  "$test_sha" "$runner_sha" "$monitor_sha"; do
  [[ $value =~ ^[0-9a-f]{64}$ ]]
done
git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${source_commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$source_commit" fork/phase1-value-critic
test "$(git -C "$repo" show "${source_commit}:${execution_rel}" | sha256sum | awk '{print $1}')" = "$execution_sha"
test "$(git -C "$repo" show "${source_commit}:${protocol_rel}" | sha256sum | awk '{print $1}')" = "$protocol_sha"
test "$(git -C "$repo" show "${source_commit}:${analyzer_rel}" | sha256sum | awk '{print $1}')" = "$analyzer_sha"
test "$(git -C "$repo" show "${source_commit}:${verifier_rel}" | sha256sum | awk '{print $1}')" = "$verifier_sha"
test "$(git -C "$repo" show "${source_commit}:${test_rel}" | sha256sum | awk '{print $1}')" = "$test_sha"
test "$(git -C "$repo" show "${source_commit}:${runner_rel}" | sha256sum | awk '{print $1}')" = "$runner_sha"
test "$(sha256sum "$0" | awk '{print $1}')" = "$monitor_sha"

if [[ $mode == start ]]; then
  test ! -e "$root"
  test ! -e "$formal_output"
  mkdir -p "$root"
else
  test -d "$root" && test ! -L "$root"
  test ! -e "$root/COMPLETE"
  test ! -e "$root/FAILED_RC"
fi

exec 9>"$root/monitor.lock"
flock -n 9
printf '%s\n' "$$" >"$root/monitor.pid"
interrupted=0
failure_receipt() {
  rc=$?
  if (( rc != 0 )); then
    if (( interrupted == 1 )); then
      printf '%s\n' "$rc" >"$root/INTERRUPTED_RC" 2>/dev/null || true
    else
      printf '%s\n' "$rc" >"$root/FAILED_RC" 2>/dev/null || true
    fi
  fi
  exit "$rc"
}
trap failure_receipt EXIT
trap 'interrupted=1; exit 143' TERM
trap 'interrupted=1; exit 130' INT
trap 'interrupted=1; exit 129' HUP

if [[ $mode == start ]]; then
  git -C "$repo" show "${source_commit}:${monitor_rel}" >"$root/source_script.sh"
  git -C "$repo" show "${source_commit}:${runner_rel}" >"$root/formal_runner.sh"
  git -C "$repo" show "${source_commit}:${execution_rel}" >"$root/execution_protocol.json"
  cmp "$0" "$root/source_script.sh"
  test "$(sha256sum "$root/formal_runner.sh" | awk '{print $1}')" = "$runner_sha"
  test "$(sha256sum "$root/execution_protocol.json" | awk '{print $1}')" = "$execution_sha"
  cat >"$root/preflight_13.txt" <<EOF
01_direction=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; PASS
02_role=wait for exact immutable Stage-A COMPLETE then invoke one hash-bound structural rank audit; PASS
03_pre_result=scientific protocol froze before Target-522 candidate and monitor opens no Stage-A profile before COMPLETE; PASS
04_source=exact public commit execution protocol scientific protocol analyzer verifier test runner monitor; PASS
05_wait_inputs=marker existence only before Stage-A COMPLETE,no public profile private selection identity or value read; PASS
06_activation=Stage-A manifest and public producer A/B hashes checked only after immutable COMPLETE; PASS
07_formal_output=${formal_output},single immutable target,no alternate input or threshold arguments; PASS
08_reproducibility=fresh worktree full tests analyzer A/B and independent verifier A/B; PASS
09_checkpoint=start or resume with exclusive lock and bounded six-hour wait; PASS
10_quantity=endpoint-edge incidence rank over exact disjoint sibling cliques only; PASS
11_security=no credential private selection label outcome prediction accuracy gap runtime or utility access; PASS
12_failure=Stage-A failure hash drift duplicate output trace or formal failure stops closed; PASS
13_resources=CPU watcher and audit only,GPU paid-API model-fit base-update 0/0/0/0; PASS
EOF
  test "$(wc -l <"$root/preflight_13.txt")" = 13
else
  test -f "$root/source_script.sh" && test -f "$root/formal_runner.sh"
  test -f "$root/execution_protocol.json" && test -f "$root/preflight_13.txt"
  cmp "$0" "$root/source_script.sh"
  test "$(sha256sum "$root/formal_runner.sh" | awk '{print $1}')" = "$runner_sha"
  test "$(sha256sum "$root/execution_protocol.json" | awk '{print $1}')" = "$execution_sha"
  test "$(wc -l <"$root/preflight_13.txt")" = 13
  rm -f "$root/INTERRUPTED_RC" "$root/TIMEOUT_RC"
  if test -e "$formal_output"; then test -f "$formal_output/COMPLETE"; fi
fi

for poll in $(seq 0 720); do
  test ! -e "$stage_a/FAILED_RC"
  test ! -e "$stage_a_monitor/FAILED_RC"
  if test -f "$stage_a/COMPLETE"; then
    stage_a_manifest_sha=$(sha256sum "$stage_a/SHA256SUMS" | awk '{print $1}')
    for public_name in producer_a.json producer_b.json; do
      test "$(awk -v name="./$public_name" '$2 == name {count += 1} END {print count + 0}' "$stage_a/SHA256SUMS")" = 1
      expected_public_sha=$(awk -v name="./$public_name" '$2 == name {print $1}' "$stage_a/SHA256SUMS")
      test "$(sha256sum "$stage_a/$public_name" | awk '{print $1}')" = "$expected_public_sha"
    done
    if test ! -e "$formal_output"; then
      printf '%s activation stage_a_manifest_sha256=%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage_a_manifest_sha" >>"$root/monitor.log"
      bash "$root/formal_runner.sh" \
        "$formal_output" "$source_commit" "$execution_sha" "$protocol_sha" "$analyzer_sha" \
        "$verifier_sha" "$test_sha" "$runner_sha" "$monitor_sha" "$stage_a_manifest_sha" \
        >"$root/formal.stdout" 2>"$root/formal.stderr"
    fi
    test -f "$formal_output/COMPLETE"
    test ! -e "$formal_output/FAILED_RC"
    formal_manifest_sha=$(sha256sum "$formal_output/SHA256SUMS" | awk '{print $1}')
    (
      cd "$formal_output"
      sha256sum -c SHA256SUMS >/dev/null
    )
    cat >"$root/READY" <<EOF
status=TARGET522_LINEAR_CONTRAST_RANK_AUDIT_COMPLETE
completed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
source_commit=${source_commit}
execution_protocol_sha256=${execution_sha}
scientific_protocol_sha256=${protocol_sha}
stage_a_sha256sums_sha256=${stage_a_manifest_sha}
formal_output=${formal_output}
formal_sha256sums_sha256=${formal_manifest_sha}
classification=$(jq -r .classification "$formal_output/result_a.json")
prospective_values_read=false
first960_closure_opened=false
private_selection_opened=false
gpu_paid_api_model_fit_base_update=0/0/0/0
EOF
    filename_hits=$(find "$root" -type f -printf '%f\n' \
      | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
    credential_files=$(grep -R -E -i -l "$credential_pattern" "$root" \
      --exclude=security.txt --exclude=SHA256SUMS || true)
    test "$filename_hits" = 0
    test -z "$credential_files"
    printf 'credential_filename_hits=0\nboundary_aware_credential_content_file_hits=0\n' \
      >"$root/security.txt"
    (
      cd "$root"
      find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
        | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
      touch COMPLETE
    )
    chmod -R a-w "$root"
    trap - EXIT
    exit 0
  fi
  if (( poll % 60 == 0 )); then
    printf '%s waiting poll=%s stage_a_complete=false prospective_values_read=false\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$poll" >>"$root/monitor.log"
  fi
  sleep 30
done

printf '%s\n' 124 >"$root/TIMEOUT_RC"
trap - EXIT
exit 0
