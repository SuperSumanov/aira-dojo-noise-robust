#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 OUTPUT_ROOT EXPECTED_GIT_COMMIT" >&2
  exit 2
fi

output_root=$1
expected_commit=$2
actual_commit=$(git rev-parse HEAD)
if [[ "$actual_commit" != "$expected_commit" ]]; then
  echo "git commit mismatch" >&2
  exit 2
fi
if [[ -e "$output_root" ]]; then
  echo "output root already exists" >&2
  exit 2
fi

baseline_snapshot=7cdaefcf2be7786442e1af1f4d0b4012edee708932f1fad31e174c0dcaf803a1
current_snapshot=8579d7cd32091a11089b935217f7189e321b1d623dbaa69233182ba2fedd9248
state_root=/research/d7/spc/yzyang4/prospective_decision_v1/snapshots
baseline_root=$state_root/$baseline_snapshot/accumulator
current_root=$state_root/$current_snapshot/accumulator
gate=phase1/results/prospective_0823_batch_postflight_20260825_6299865/structural_gate.json
common=phase1/results/prediction_receipt_common_support_8579_20260826_9f2cbe9/independent_verification.json

gate_sha=ca44845bc0f5feaf5de0e77ec658e4b0cca3f5a451b75b33bb4c63acfc1eccca
baseline_summary_sha=ad3e8fe4180fd6c6f7fcea121ef0c51c0f292445d77368e2b3ab4dc9a56d4585
baseline_ledger_sha=43b1f16d5326fad5de490a5b63bd8a6f3c454ad303c031cd1fb54e607919cf83
current_summary_sha=bc03570594dca4acf36f7068fd7f185e7e3121f8d759d8d9c5bf81e91151aa15
current_ledger_sha=09e3f63b2ae274e6a769ff26fdbcd400a55cacbf6719c3b71063c0c84664bcd1
common_sha=24a7ff758d391f4fd506236df97f1a9d6692ddb965cab490e6e92475e2cb012e

mkdir -p "$output_root"
printf '%s\n' \
  "PREFLIGHT_01_QUESTION=Can structural-only sources reproduce guard v2 and forward debt accounting?" \
  "PREFLIGHT_02_ESTIMAND=25-percent dominant-task pair-share integer envelope and later structural debt" \
  "PREFLIGHT_03_PRIMARY=exact independent reconstruction; no statistical effect" \
  "PREFLIGHT_04_COHORT=baseline $baseline_snapshot to current $current_snapshot" \
  "PREFLIGHT_05_SPLIT=chronological provisional first-960; membership unchanged" \
  "PREFLIGHT_06_INPUTS=gate $gate_sha; baseline summary/ledger $baseline_summary_sha/$baseline_ledger_sha; current summary/ledger $current_summary_sha/$current_ledger_sha; receipt $common_sha" \
  "PREFLIGHT_07_FORBIDDEN=prediction pair/value/matrix; label/outcome/raw archive/effect" \
  "PREFLIGHT_08_CONTROLS=producer A/B; non-importing verifier A/B; tamper tests" \
  "PREFLIGHT_09_RANDOMNESS=none" \
  "PREFLIGHT_10_RESOURCES=CPU only; GPU/API/model-fit/base-update 0/0/0/0" \
  "PREFLIGHT_11_FAILURE=any binding, count, chronology, A/B, trace, credential, or test failure" \
  "PREFLIGHT_12_OUTPUT=immutable JSON receipts plus traces and SHA256SUMS" \
  "PREFLIGHT_13_CLAIM=provenance repair only; no causal, accuracy, or utility claim" \
  > "$output_root/preflight_13.txt"

export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
export PYTHONHASHSEED=0

python -m pytest -q phase1/tests/test_task_balance_structural_only_v2.py \
  > "$output_root/focused_tests.txt"
python -m pytest -q phase1/tests \
  > "$output_root/full_tests.txt"

guard_command=(
  python -m phase1.build_task_balance_accrual_guard_v2
  --structural-gate "$gate"
  --expect-structural-gate-sha256 "$gate_sha"
  --accumulator-summary "$baseline_root/summary.json"
  --expect-accumulator-summary-sha256 "$baseline_summary_sha"
  --first960-ledger "$baseline_root/provisional_first960_runs.jsonl"
  --expect-first960-ledger-sha256 "$baseline_ledger_sha"
  --snapshot-sha256 "$baseline_snapshot"
)
strace -f -qq -e trace=file -o "$output_root/guard_a.strace" \
  "${guard_command[@]}" --output "$output_root/guard_a.json" \
  > "$output_root/guard_a.stdout"
strace -f -qq -e trace=file -o "$output_root/guard_b.strace" \
  "${guard_command[@]}" --output "$output_root/guard_b.json" \
  > "$output_root/guard_b.stdout"
cmp "$output_root/guard_a.json" "$output_root/guard_b.json"
guard_sha=$(sha256sum "$output_root/guard_a.json" | awk '{print $1}')

guard_verify_command=(
  python -m phase1.verify_task_balance_accrual_guard_v2
  --structural-gate "$gate"
  --expect-structural-gate-sha256 "$gate_sha"
  --accumulator-summary "$baseline_root/summary.json"
  --expect-accumulator-summary-sha256 "$baseline_summary_sha"
  --first960-ledger "$baseline_root/provisional_first960_runs.jsonl"
  --expect-first960-ledger-sha256 "$baseline_ledger_sha"
  --snapshot-sha256 "$baseline_snapshot"
  --guard "$output_root/guard_a.json"
  --expect-guard-sha256 "$guard_sha"
)
strace -f -qq -e trace=file -o "$output_root/guard_verify_a.strace" \
  "${guard_verify_command[@]}" --output "$output_root/guard_verify_a.json" \
  > "$output_root/guard_verify_a.stdout"
strace -f -qq -e trace=file -o "$output_root/guard_verify_b.strace" \
  "${guard_verify_command[@]}" --output "$output_root/guard_verify_b.json" \
  > "$output_root/guard_verify_b.stdout"
cmp "$output_root/guard_verify_a.json" "$output_root/guard_verify_b.json"
guard_verification_sha=$(sha256sum "$output_root/guard_verify_a.json" | awk '{print $1}')

forward_command=(
  python -m phase1.task_balance_guard_forward_validation_v2
  --guard "$output_root/guard_a.json"
  --expect-guard-sha256 "$guard_sha"
  --guard-verification "$output_root/guard_verify_a.json"
  --expect-guard-verification-sha256 "$guard_verification_sha"
  --baseline-summary "$baseline_root/summary.json"
  --expect-baseline-summary-sha256 "$baseline_summary_sha"
  --baseline-ledger "$baseline_root/provisional_first960_runs.jsonl"
  --expect-baseline-ledger-sha256 "$baseline_ledger_sha"
  --baseline-snapshot-sha256 "$baseline_snapshot"
  --current-summary "$current_root/summary.json"
  --expect-current-summary-sha256 "$current_summary_sha"
  --current-ledger "$current_root/provisional_first960_runs.jsonl"
  --expect-current-ledger-sha256 "$current_ledger_sha"
  --current-snapshot-sha256 "$current_snapshot"
  --current-common-support-verification "$common"
  --expect-current-common-support-verification-sha256 "$common_sha"
)
strace -f -qq -e trace=file -o "$output_root/forward_a.strace" \
  "${forward_command[@]}" --output "$output_root/forward_a.json" \
  > "$output_root/forward_a.stdout"
strace -f -qq -e trace=file -o "$output_root/forward_b.strace" \
  "${forward_command[@]}" --output "$output_root/forward_b.json" \
  > "$output_root/forward_b.stdout"
cmp "$output_root/forward_a.json" "$output_root/forward_b.json"
forward_sha=$(sha256sum "$output_root/forward_a.json" | awk '{print $1}')

forward_verify_command=(
  python -m phase1.verify_task_balance_guard_forward_validation_v2
  --guard "$output_root/guard_a.json"
  --expect-guard-sha256 "$guard_sha"
  --guard-verification "$output_root/guard_verify_a.json"
  --expect-guard-verification-sha256 "$guard_verification_sha"
  --baseline-summary "$baseline_root/summary.json"
  --expect-baseline-summary-sha256 "$baseline_summary_sha"
  --baseline-ledger "$baseline_root/provisional_first960_runs.jsonl"
  --expect-baseline-ledger-sha256 "$baseline_ledger_sha"
  --baseline-snapshot-sha256 "$baseline_snapshot"
  --current-summary "$current_root/summary.json"
  --expect-current-summary-sha256 "$current_summary_sha"
  --current-ledger "$current_root/provisional_first960_runs.jsonl"
  --expect-current-ledger-sha256 "$current_ledger_sha"
  --current-snapshot-sha256 "$current_snapshot"
  --current-common-support-verification "$common"
  --expect-current-common-support-verification-sha256 "$common_sha"
  --result "$output_root/forward_a.json"
  --expect-result-sha256 "$forward_sha"
)
strace -f -qq -e trace=file -o "$output_root/forward_verify_a.strace" \
  "${forward_verify_command[@]}" --output "$output_root/forward_verify_a.json" \
  > "$output_root/forward_verify_a.stdout"
strace -f -qq -e trace=file -o "$output_root/forward_verify_b.strace" \
  "${forward_verify_command[@]}" --output "$output_root/forward_verify_b.json" \
  > "$output_root/forward_verify_b.stdout"
cmp "$output_root/forward_verify_a.json" "$output_root/forward_verify_b.json"

if grep -E -i '/(pair_predictions|pairs|labels|grades|outcomes|regrade_results)\.jsonl([" ]|$)' \
  "$output_root"/*.strace > "$output_root/forbidden_trace_hits.txt"; then
  echo "forbidden file open detected" >&2
  exit 2
fi
: > "$output_root/forbidden_trace_hits.txt"

if find "$output_root" -type f -printf '%f\n' | grep -E -i '(\.env|api[_-]?key|token|secret)' \
  > "$output_root/name_scan_hits.txt"; then
  echo "credential-like output filename detected" >&2
  exit 2
fi
: > "$output_root/name_scan_hits.txt"
credential_pattern='(^|[^[:alnum:]_])(sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,})'
if printf '%s\n' '/research/example/task-balance-structural-only-v2' | \
  grep -E -i "$credential_pattern" > /dev/null; then
  echo "credential scanner boundary self-test failed" >&2
  exit 2
fi
positive_probe='s''k-abcdefghijklmnop'
if ! printf '%s\n' "$positive_probe" | grep -E -i "$credential_pattern" > /dev/null; then
  echo "credential scanner positive self-test failed" >&2
  exit 2
fi
unset positive_probe
if grep -R -E -i "$credential_pattern" \
  --exclude=content_scan_hits.txt "$output_root" > "$output_root/content_scan_hits.txt"; then
  echo "credential-like output content detected" >&2
  exit 2
fi
: > "$output_root/content_scan_hits.txt"

printf '%s\n' \
  "git_commit=$actual_commit" \
  "guard_sha256=$guard_sha" \
  "guard_independent_sha256=$guard_verification_sha" \
  "forward_sha256=$forward_sha" \
  "forward_independent_sha256=$(sha256sum "$output_root/forward_verify_a.json" | awk '{print $1}')" \
  "producer_ab_byte_identical=true" \
  "verifier_ab_byte_identical=true" \
  "prediction_matrix_input_used=false" \
  "forbidden_trace_hits=0" \
  "credential_filename_hits=0" \
  "credential_content_hits=0" \
  "gpu_api_model_fit_base_update=0/0/0/0" \
  > "$output_root/formal_summary.txt"

(
  cd "$output_root"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  touch COMPLETE
)
echo "TASK_BALANCE_STRUCTURAL_ONLY_V2_COMPLETE"
