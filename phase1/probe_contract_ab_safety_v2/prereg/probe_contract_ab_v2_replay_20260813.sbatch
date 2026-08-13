#!/usr/bin/env bash
#SBATCH --job-name=probe_ab_v2_replay
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:1
#SBATCH --time=00:20:00
#SBATCH --constraint=rtx3090
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --array=0-15%4
#SBATCH --output=/research/d7/spc/yzyang4/logs/probe_contract_ab_v2_replay_%A_%a.out

set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
set +u
source "$HOME/env_setup.sh"
set -u

repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
ops=/research/d7/spc/yzyang4/probe_contract_ab_ops/probe_contract_ab_safety_v2
manifest="$ops/replay_manifest.jsonl"
out="$ops/replay"
workbase="$ops/workdirs"
py=/research/d7/spc/yzyang4/venvs/exp/bin/python
commit=$(cat "$ops/prereg/expected_commit.txt")
image_sha=$(cat "$ops/prereg/container_sha256.txt")

cd "$repo"
test "$(git rev-parse HEAD)" = "$commit"
test -z "$(git status --short)"
test "${EXPECTED_MANIFEST_SHA:-}" != ""
test "$(printf '%s' "$EXPECTED_MANIFEST_SHA" | wc -c)" = 64
test "$(sha256sum "$manifest" | awk '{print $1}')" = "$EXPECTED_MANIFEST_SHA"
test -f "$ops/replay_manifest.audit.json"
test ! -e "$out/index_${SLURM_ARRAY_TASK_ID}"
export PYTHONPATH="$repo/src:$repo/phase1:$repo"

printf 'PROBE_CONTRACT_AB_REPLAY_START %s array=%s index=%s node=%s commit=%s manifest_sha=%s\n' \
  "$(date --iso-8601=seconds)" "$SLURM_ARRAY_JOB_ID" "$SLURM_ARRAY_TASK_ID" \
  "$(hostname)" "$commit" "$EXPECTED_MANIFEST_SHA"
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
printf 'PROBE_CONTRACT_AB_WORKER_RC=%s time=%s\n' "$worker_rc" "$(date --iso-8601=seconds)"
exit "$worker_rc"
