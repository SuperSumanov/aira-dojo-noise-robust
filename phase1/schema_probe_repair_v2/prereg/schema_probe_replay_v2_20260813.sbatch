#!/usr/bin/env bash
#SBATCH --job-name=schema_replay_v2
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:1
#SBATCH --time=00:40:00
#SBATCH --constraint=rtx3090
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --array=0-1%2
#SBATCH --output=/research/d7/spc/yzyang4/logs/schema_probe_replay_v2_%A_%a.out

set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
ops=/research/d7/spc/yzyang4/schema_probe_ops/schema_probe_repair_v2
manifest="$ops/replay_manifest.jsonl"
out="$ops/replay"
workbase="$ops/workdirs"
py=/research/d7/spc/yzyang4/venvs/exp/bin/python
commit=c1dc17420e95b9e2994a474c25afdcb85063ab36
image_sha=801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda

cd "$repo"
test "$(git rev-parse HEAD)" = "$commit"
test -z "$(git status --short)"
test "${EXPECTED_MANIFEST_SHA:-}" != ""
test "$(printf '%s' "$EXPECTED_MANIFEST_SHA" | wc -c)" = 64
test "$(sha256sum "$manifest" | awk '{print $1}')" = "$EXPECTED_MANIFEST_SHA"
test -f "$ops/replay_manifest.audit.json"
test ! -e "$out/index_${SLURM_ARRAY_TASK_ID}"
export PYTHONPATH="$repo/src:$repo"

printf 'SCHEMA_PROBE_V2_REPLAY_START %s array=%s index=%s node=%s commit=%s manifest_sha=%s\n' \
  "$(date --iso-8601=seconds)" "$SLURM_ARRAY_JOB_ID" "$SLURM_ARRAY_TASK_ID" "$(hostname)" "$commit" "$EXPECTED_MANIFEST_SHA"
printf 'MATRIX index=%s checkpoints=30,60,120,240,360,600 max_candidate_gpu_seconds=600\n' "$SLURM_ARRAY_TASK_ID"
set +e
"$py" phase1/schema_probe_contract_worker.py \
  --manifest "$manifest" \
  --index "$SLURM_ARRAY_TASK_ID" \
  --out "$out" \
  --checkpoints 30,60,120,240,360,600 \
  --poll-s 0.10 \
  --workbase "$workbase" \
  --container-sha256 "$image_sha" \
  --online
worker_rc=$?
set -e
printf 'SCHEMA_PROBE_V2_WORKER_RC=%s time=%s\n' "$worker_rc" "$(date --iso-8601=seconds)"
exit "$worker_rc"

