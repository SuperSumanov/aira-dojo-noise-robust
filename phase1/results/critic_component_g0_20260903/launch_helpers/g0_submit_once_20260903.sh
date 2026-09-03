#!/usr/bin/env bash
# User-authorized, single-submission G0. No automatic retry or scientific configuration change.
set -Eeuo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHONDONTWRITEBYTECODE=1
readonly control=/research/d7/spc/yzyang4/worktrees/g0_shared_a99bf8a_nosmudge
readonly source_root=/research/d7/spc/yzyang4/aira-dojo-audit-9f25145
readonly runtime=/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-selective
readonly setup=/research/d7/spc/yzyang4/critic-component-g0/runtime-setup-20260903-r3
readonly preflight=/research/d7/spc/yzyang4/critic-component-g0/preflight-20260903-r1
readonly submission=/research/d7/spc/yzyang4/critic-component-g0/submissions/20260903-g0-r1
readonly template="$control/phase1/scripts/critic_component_g0_shared_pro6000_20260821.sbatch"
test "$(cat "$setup/exit_status.txt")" = validation_exit=0
test -f "$setup/COMPLETE"
test "$(cat "$setup/pip_check.txt")" = 'No broken requirements found.'
test "$(cat "$preflight/exit_status.txt")" = preflight_exit=0
test "$(git -C "$control" rev-parse HEAD)" = a99bf8a78ee25fc0257dce5aabdc947ef0725839
test -z "$(git -C "$control" status --porcelain --untracked-files=all)"
test "$(git -C "$source_root" rev-parse HEAD)" = 51c7f480a844364a91cf1ee4ebd9dac18f6bb832
test -z "$(git -C "$source_root" status --porcelain --untracked-files=all)"
( cd "$control" && sha256sum -c "$preflight/control.sha256" )
test -x "$runtime/bin/accelerate"
# No existing current-user job is silently combined with the first G0 authorization.
queue=$(squeue -u "$(id -un)" -h -o '%i|%j|%T')
test -z "$queue"
mkdir -p "$(dirname "$submission")"
# Atomic, once-only latch. An uncertain sbatch response must be reconciled, never retried.
mkdir -m 0700 "$submission"
install -m 0400 "$0" "$submission/submit.sh"
printf 'state=SUBMISSION_INTENT_RECORDED\nmax_new_jobs=1\nmax_walltime_seconds=7200\nrequested_gpus=2\nmax_gpu_hours=4\n' >"$submission/intent.txt"
date -u +%Y-%m-%dT%H:%M:%SZ >"$submission/submitted_at_utc.txt"
sha256sum "$template" "$setup/compatibility.json" "$setup/dependency_closure.json" \
  "$preflight/static_assets_receipt.json" "$submission/submit.sh" >"$submission/inputs.sha256"
set +e
sbatch --parsable --job-name=critic_g0_20260903 \
  --output="$submission/slurm-%j.out" --error="$submission/slurm-%j.out" \
  --export=PATH=/usr/local/bin:/usr/bin:/bin,G0_CONTROL_ROOT="$control",G0_VENV="$runtime",PYTHONDONTWRITEBYTECODE=1,MAX_JOBS=2 \
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
printf 'G0_SUBMITTED job_id=%s requested_gpus=2 walltime_hours=2 gpu_hour_cap=4\n' "$job_id"
squeue -j "$job_id" -h -o '%i|%j|%T|%S|%R'
