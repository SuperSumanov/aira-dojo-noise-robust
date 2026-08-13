#!/bin/bash
#SBATCH --job-name=traj_smoke
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=00:20:00
#SBATCH --constraint=rtx3090
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --output=/research/d7/spc/yzyang4/logs/trajectory_smoke_%j.out

set -euo pipefail
set +u
source "$HOME/env_setup.sh"
set -u

repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
root=/research/d7/spc/yzyang4/aira-dojo/phase1
py=/research/d7/spc/yzyang4/venvs/exp/bin/python
commit=4630a36a7e5cb989cf8872f03912b21b686d51c6
manifest="$repo/phase1/trajectory_smoke_manifest.jsonl"
out="$repo/phase1/trajectory_smoke_v1"
image_sha=801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda

cd "$repo"
test "$(git rev-parse HEAD)" = "$commit"
test "$(sha256sum "$manifest" | awk '{print $1}')" = e03af45e351ab552fbea311e6af2b30a84cb9e24d2f0e3d875a833c6958cb725
test ! -e "$out"
export FIDELITY_WORK="/tmp/trajectory_${SLURM_JOB_ID}"

echo "TRAJECTORY_JOB_START $(date --iso-8601=seconds) host=$(hostname) commit=$commit"
echo "MATRIX cards=2 checkpoints=30,60,120 max_gpu_seconds=240 gpu=1"
"$py" -m py_compile phase1/trajectory_fidelity_worker.py phase1/validate_trajectory_smoke.py
"$py" phase1/trajectory_fidelity_worker.py --self-test
"$py" phase1/validate_trajectory_smoke.py --self-test

set +e
"$py" phase1/trajectory_fidelity_worker.py \
  --manifest "$manifest" \
  --out "$out" \
  --checkpoints 30,60,120 \
  --online \
  --workbase "$FIDELITY_WORK" \
  --container-sha256 "$image_sha"
worker_rc=$?
set -e
echo "TRAJECTORY_WORKER_RC=$worker_rc $(date --iso-8601=seconds)"
if [[ "$worker_rc" -ne 0 ]]; then exit "$worker_rc"; fi

set +e
"$py" phase1/validate_trajectory_smoke.py --manifest "$manifest" --out-dir "$out"
validator_rc=$?
set -e
echo "TRAJECTORY_VALIDATOR_RC=$validator_rc $(date --iso-8601=seconds)"
if [[ "$validator_rc" -ne 0 ]]; then exit "$validator_rc"; fi

cat "$out/smoke_validation.json"
echo "TRAJECTORY_SMOKE_DONE $(date --iso-8601=seconds)"
