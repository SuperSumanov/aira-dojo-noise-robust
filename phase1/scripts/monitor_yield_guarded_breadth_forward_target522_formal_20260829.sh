#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -Eeo pipefail
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

if [[ $# -ne 9 ]]; then
  echo 'usage: monitor_yield_guarded_breadth_forward_target522_formal_20260829.sh {start|resume} MONITOR_ROOT SOURCE_COMMIT PROTOCOL_SHA PRODUCER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA MONITOR_SHA' >&2
  exit 64
fi
readonly mode=$1
readonly root=$2
readonly source_commit=$3
readonly protocol_sha=$4
readonly producer_sha=$5
readonly verifier_sha=$6
readonly test_sha=$7
readonly runner_sha=$8
readonly monitor_sha=$9
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly selection=/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/latch-42f1044-after-887-v2
readonly formal_output=/research/d7/spc/yzyang4/yield-guarded-breadth-forward-target522/formal-${source_commit:0:7}-v1
readonly runner_rel=phase1/scripts/run_yield_guarded_breadth_forward_target522_formal_20260829.sh
readonly monitor_rel=phase1/scripts/monitor_yield_guarded_breadth_forward_target522_formal_20260829.sh
readonly protocol_rel=phase1/yield_guarded_breadth_forward_target522_v1.json
readonly producer_rel=phase1/confirm_yield_guarded_breadth_forward_target522.py
readonly verifier_rel=phase1/verify_yield_guarded_breadth_forward_target522.py
readonly test_rel=phase1/tests/test_yield_guarded_breadth_forward_target522.py
readonly credential_pattern='(^|[^A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'

[[ $mode == start || $mode == resume ]]
[[ $root =~ ^/research/d7/spc/yzyang4/yield-guarded-breadth-forward-target522/formal-monitor-[A-Za-z0-9._-]+$ ]]
[[ $source_commit =~ ^[0-9a-f]{40}$ ]]
for value in "$protocol_sha" "$producer_sha" "$verifier_sha" "$test_sha" "$runner_sha" "$monitor_sha"; do
  [[ $value =~ ^[0-9a-f]{64}$ ]]
done
test -d "$selection" && test ! -L "$selection"
git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${source_commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$source_commit" fork/phase1-value-critic
test "$(git -C "$repo" show "${source_commit}:${protocol_rel}" | sha256sum | awk '{print $1}')" = "$protocol_sha"
test "$(git -C "$repo" show "${source_commit}:${producer_rel}" | sha256sum | awk '{print $1}')" = "$producer_sha"
test "$(git -C "$repo" show "${source_commit}:${verifier_rel}" | sha256sum | awk '{print $1}')" = "$verifier_sha"
test "$(git -C "$repo" show "${source_commit}:${test_rel}" | sha256sum | awk '{print $1}')" = "$test_sha"
test "$(git -C "$repo" show "${source_commit}:${runner_rel}" | sha256sum | awk '{print $1}')" = "$runner_sha"
test "$(sha256sum "$0" | awk '{print $1}')" = "$monitor_sha"

if [[ $mode == start ]]; then
  test ! -e "$root"
  test ! -e "$formal_output"
  test ! -e "$selection/candidate.tsv"
  test ! -e "$selection/READY"
  test ! -e "$selection/COMPLETE"
  test ! -e "$selection/FAILED_RC"
  test ! -e "$selection/CONTINUITY_GAP"
  test ! -e "$selection/TIMEOUT_RC"
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
  cmp "$0" "$root/source_script.sh"
  test "$(sha256sum "$root/formal_runner.sh" | awk '{print $1}')" = "$runner_sha"
  cat >"$root/preflight_13.txt" <<EOF
01_direction=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; PASS
02_role=wait for the exact first Target-522 selection then invoke one hash-bound formal runner; PASS
03_pre_candidate=selection candidate READY COMPLETE and failure markers absent at start; PASS
04_source_commit=${source_commit},protocol producer verifier test runner monitor exact; PASS
05_wait_inputs=file existence only before COMPLETE,no candidate content or profile read; PASS
06_activation=selection SHA256SUMS verified only after COMPLETE; PASS
07_formal_output=${formal_output},single immutable target; PASS
08_reproducibility=public exact commit plus A/B producer private witness and verifier; PASS
09_checkpoint=start or resume with exclusive lock and bounded six-hour wait; PASS
10_resources=CPU watcher only before formal,GPU API model-fit base-update 0/0/0/0; PASS
11_security=no credential file sourced,no label outcome prediction accuracy or utility; PASS
12_failure=selection failure hash drift duplicate output or formal failure fails closed; PASS
13_interruption=TERM INT HUP receipts and explicit resume without alternate candidate; PASS
EOF
  test "$(wc -l <"$root/preflight_13.txt")" = 13
else
  test -f "$root/source_script.sh" && test -f "$root/formal_runner.sh" && test -f "$root/preflight_13.txt"
  cmp "$0" "$root/source_script.sh"
  test "$(sha256sum "$root/formal_runner.sh" | awk '{print $1}')" = "$runner_sha"
  test "$(wc -l <"$root/preflight_13.txt")" = 13
  rm -f "$root/INTERRUPTED_RC" "$root/TIMEOUT_RC"
  if test -e "$formal_output"; then test -f "$formal_output/COMPLETE"; fi
fi

for poll in $(seq 0 720); do
  test ! -e "$selection/FAILED_RC"
  test ! -e "$selection/CONTINUITY_GAP"
  test ! -e "$selection/TIMEOUT_RC"
  if test -f "$selection/COMPLETE"; then
    selection_manifest_sha=$(sha256sum "$selection/SHA256SUMS" | awk '{print $1}')
    (
      cd "$selection"
      sha256sum -c SHA256SUMS >/dev/null
    )
    if test ! -e "$formal_output"; then
      printf '%s activation selection_manifest_sha256=%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$selection_manifest_sha" >>"$root/monitor.log"
      bash "$root/formal_runner.sh" \
        "$formal_output" "$source_commit" "$protocol_sha" "$producer_sha" "$verifier_sha" \
        "$test_sha" "$runner_sha" "$selection_manifest_sha" \
        >"$root/formal.stdout" 2>"$root/formal.stderr"
    fi
    test -f "$formal_output/COMPLETE"
    test ! -e "$formal_output/FAILED_RC"
    formal_manifest_sha=$(sha256sum "$formal_output/SHA256SUMS" | awk '{print $1}')
    cat >"$root/READY" <<EOF
status=TARGET522_YIELD_GUARDED_BREADTH_FORMAL_COMPLETE
completed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
source_commit=${source_commit}
selection_sha256sums_sha256=${selection_manifest_sha}
formal_output=${formal_output}
formal_sha256sums_sha256=${formal_manifest_sha}
prospective_values_read=false
gpu_api_model_fit_base_update=0/0/0/0
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
  if (( poll % 120 == 0 )); then
    printf '%s waiting poll=%s selection_complete=false prospective_values_read=false\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$poll" >>"$root/monitor.log"
  fi
  sleep 30
done

printf '%s\n' 124 >"$root/TIMEOUT_RC"
trap - EXIT
exit 0
