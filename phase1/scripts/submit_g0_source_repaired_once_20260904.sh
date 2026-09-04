#!/usr/bin/env bash
# User explicitly approved ONE new two-GPU allocation, 117 minutes, on 2026-09-04.
# An uncertain submission MUST NOT be retried. Never run an older submit helper.
set -Eeo pipefail
set +u
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf PYTHONDONTWRITEBYTECODE=1
readonly control=/research/d7/spc/yzyang4/worktrees/g0_recovery_94ad7da_sparse
readonly source_root=/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b
readonly runtime=/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-selective
readonly preflight=/research/d7/spc/yzyang4/critic-component-g0/recovery-preflight-20260903-r3
readonly repair=/research/d7/spc/yzyang4/critic-component-g0/source-repair-12288-20260904
readonly submission=/research/d7/spc/yzyang4/critic-component-g0/submissions/20260904-g0-r3
readonly template="$control/phase1/scripts/critic_component_g0_shared_pro6000_20260821.sbatch"
readonly exp_python=/research/d7/spc/yzyang4/venvs/exp/bin/python

test "$(cat "$preflight/exit_status.txt")" = preflight_exit=0
test "$(cat "$repair/recheck_exit.txt")" = recheck_exit=0
test -f "$repair/COMPLETE"
test "$(git -C "$control" rev-parse HEAD)" = 94ad7dafff1866c6d50eb54927a4bf56547facc2
test "$(git -C "$source_root" rev-parse HEAD)" = 5f3bc362db922c8edee2ef134656dfdb9a2b74fb
source_status=$(git -C "$source_root" status --porcelain --untracked-files=all)
control_status=$(git -C "$control" status --porcelain --untracked-files=all)
test -z "$source_status" && test -z "$control_status"
test ! -w "$source_root"
( cd "$control" && sha256sum -c "$preflight/control.sha256" )
test "$(sha256sum /tmp/verify_g0_source_repair_20260904.py | cut -d' ' -f1)" = df348985a6836ca8a3eb6e7d2d9e8999b9510571165feeb39f0a8214db0982cd
test "$(sha256sum /tmp/g0_recovery_bound_recheck_20260903.py | cut -d' ' -f1)" = bbe028018590d92251021f201658493157767466175b9ebd31458ac447a76d94
test "$(sha256sum /tmp/check_official_storage_20260903.py | cut -d' ' -f1)" = 3e45c41f8a37ddd410e874bc60a484092f3a507a6f74717e48bbb369a576ca1c
test -x "$runtime/bin/accelerate"
queue=$(squeue -u yzyang4 -h -o '%i')
test -z "$queue"
# mkdir is the exclusive, non-reusable admission latch, before any submit attempt.
mkdir -m 0700 "$submission"
install -m 0400 "$0" "$submission/submit.sh"
printf 'state=AUTHORIZED_SUBMISSION_INTENT\nmax_new_jobs=1\nprior_gpu_seconds=320\nmax_walltime_seconds=7020\nrequested_gpus=2\ncombined_gpu_second_cap=14400\nrequeue=0\n' >"$submission/intent.txt"
date -u +%Y-%m-%dT%H:%M:%SZ >"$submission/preflight_started_at_utc.txt"
trap 'rc=$?; printf "orchestrator_exit=%s\n" "$rc" >"$submission/orchestrator_exit.txt"' EXIT
cd "$submission"
"$exp_python" -B /tmp/verify_g0_source_repair_20260904.py >"$submission/source_and_budget_preflight.json"
# Exact established storage helper: creates/removes only its own 4-GiB diagnostic.
"$runtime/bin/python" -B /tmp/check_official_storage_20260903.py >"$submission/storage_test.json"
"$runtime/bin/python" - "$submission" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
r = json.loads((p/'storage_test.json').read_text())
assert r['checkpoint_reservation'] == 'PASS'
assert r['resulting_file_bytes'] == r['resulting_allocated_bytes'] == 4294967296
assert r['own_diagnostic_file_removed']
v = json.loads((p/'source_and_budget_preflight.json').read_text())
assert v['allocated_gpu_seconds_used'] == 320
assert v['proposed_cumulative_gpu_seconds'] == 14360 <= 14400
assert v['source_clean'] and v['queue_empty'] and v['source_root_nonwritable']
PY
# Rebind runtime without GPU context or model fit. No uv/default environment.
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
 "$runtime/bin/python" -B /tmp/g0_recovery_bound_recheck_20260903.py >"$submission/recovery_binding.json" 2>"$submission/runtime_recheck.stderr"
cmp "$repair/recovery_binding.json" "$submission/recovery_binding.json"
source_status=$(git -C "$source_root" status --porcelain --untracked-files=all)
control_status=$(git -C "$control" status --porcelain --untracked-files=all)
queue=$(squeue -u yzyang4 -h -o '%i')
test -z "$source_status" && test -z "$control_status" && test -z "$queue"
sha256sum "$template" "$repair/static_assets_receipt.json" "$submission/recovery_binding.json" \
 "$submission/source_and_budget_preflight.json" "$submission/storage_test.json" "$submission/submit.sh" \
 /tmp/check_official_storage_20260903.py >"$submission/inputs.sha256"
date -u +%Y-%m-%dT%H:%M:%SZ >"$submission/submission_attempted_at_utc.txt"
set +e
sbatch --parsable --no-requeue --time=01:57:00 --job-name=critic_g0_r3_20260904 \
 --output="$submission/slurm-%j.out" --error="$submission/slurm-%j.out" \
 --export=PATH=/usr/local/bin:/usr/bin:/bin,G0_CONTROL_ROOT="$control",G0_SOURCE_ROOT="$source_root",G0_EXPECTED_SOURCE_COMMIT=5f3bc362db922c8edee2ef134656dfdb9a2b74fb,G0_VENV="$runtime",G0_RECOVERY_FINAL_ONLY=1,PYTHONDONTWRITEBYTECODE=1,MAX_JOBS=2 \
 "$template" >"$submission/sbatch.stdout" 2>"$submission/sbatch.stderr"
rc=$?
set -e
printf 'sbatch_exit=%s\n' "$rc" >"$submission/sbatch_exit.txt"
if (( rc != 0 )); then
 printf 'state=SUBMISSION_FAILED_DO_NOT_RETRY\n' >"$submission/FAILED"
 exit "$rc"
fi
job_id=$(cut -d';' -f1 "$submission/sbatch.stdout")
[[ "$job_id" =~ ^[0-9]+$ ]]
printf '%s\n' "$job_id" >"$submission/job_id.txt"
scontrol show job -o "$job_id" >"$submission/scheduler_receipt.txt"
printf 'state=SUBMITTED\njob_id=%s\n' "$job_id" >"$submission/SUBMITTED"
printf 'G0_R3_SUBMITTED job_id=%s requested_gpus=2 walltime_seconds=7020 cumulative_gpu_seconds_upper_bound=14360\n' "$job_id"
squeue -j "$job_id" -h -o '%i|%T|%S|%e|%R'
