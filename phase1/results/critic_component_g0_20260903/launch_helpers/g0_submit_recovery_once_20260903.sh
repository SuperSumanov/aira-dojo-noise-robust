#!/usr/bin/env bash
# Explicitly approved single successor; never automatically retry an uncertain submission.
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
readonly submission=/research/d7/spc/yzyang4/critic-component-g0/submissions/20260903-g0-r2
readonly template="$control/phase1/scripts/critic_component_g0_shared_pro6000_20260821.sbatch"
test "$(cat "$preflight/exit_status.txt")" = preflight_exit=0
test -f "$preflight/COMPLETE"
test "$(git -C "$control" rev-parse HEAD)" = 94ad7dafff1866c6d50eb54927a4bf56547facc2
test "$(git -C "$source_root" rev-parse HEAD)" = 5f3bc362db922c8edee2ef134656dfdb9a2b74fb
test -z "$(git -C "$control" status --porcelain --untracked-files=all)"
test -z "$(git -C "$source_root" status --porcelain --untracked-files=all)"
( cd "$control" && sha256sum -c "$preflight/control.sha256" )
test -z "$(squeue -u "$(id -un)" -h -o '%i')"
test ! -e /research/d7/spc/yzyang4/balanced-e2a-hf-cache-e2d587d-a1
test -x "$runtime/bin/accelerate"
# Accounting includes the original failed allocation, never just the successful retry.
elapsed=$(sacct -X -n -P -j 12181 --format=ElapsedRaw | sed '/^[[:space:]]*$/d')
test "$elapsed" = 156
mkdir -m 0700 "$submission"
install -m 0400 "$0" "$submission/submit.sh"
printf 'state=SUBMISSION_INTENT_RECORDED\nmax_new_jobs=1\nprior_gpu_seconds=312\nmax_walltime_seconds=7020\nrequested_gpus=2\ncombined_gpu_second_cap=14400\nrequeue=0\n' >"$submission/intent.txt"
date -u +%Y-%m-%dT%H:%M:%SZ >"$submission/submitted_at_utc.txt"
"$runtime/bin/python" /tmp/check_official_storage_20260903.py >"$submission/storage_test.json"
"$runtime/bin/python" - "$submission/storage_test.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
assert r['checkpoint_reservation'] == 'PASS'
assert r['resulting_file_bytes'] == r['resulting_allocated_bytes'] == 4294967296
assert r['own_diagnostic_file_removed']
PY
sha256sum "$template" "$preflight/static_assets_receipt.json" "$preflight/recovery_binding.json" \
 "$submission/storage_test.json" "$submission/submit.sh" >"$submission/inputs.sha256"
set +e
sbatch --parsable --no-requeue --time=01:57:00 --job-name=critic_g0_retry_20260903 \
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
printf 'G0_RETRY_SUBMITTED job_id=%s requested_gpus=2 walltime_seconds=7020 combined_gpu_seconds_upper_bound=14352\n' "$job_id"
squeue -j "$job_id" -h -o '%i|%j|%T|%S|%R'
