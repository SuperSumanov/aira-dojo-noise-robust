#!/usr/bin/env bash
#SBATCH --job-name=spt_pilot_v1
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=3
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:3
#SBATCH --time=01:30:00
#SBATCH --constraint=rtx3090
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --output=/research/d7/spc/yzyang4/logs/spt_pilot_v1_%j.out

set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
ops=/research/d7/spc/yzyang4/spt_ops/spt_label_blind_pilot_v1
prereg="$ops/prereg"
manifest="$prereg/pilot_manifest.jsonl"
runtime="$repo/phase1/scoreable_prediction_tap_runtime.py"
results="$ops/results"
workbase="$ops/workdirs"
status_dir="$ops/status"
analysis="$ops/analysis"
py=/research/d7/spc/yzyang4/venvs/exp/bin/python
container_sha=801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda
expected_commit=$(tr -d '[:space:]' < "$prereg/git_commit.txt")
manifest_sha=$(tr -d '[:space:]' < "$prereg/manifest_sha256.txt")

cd "$repo"
test "$(git rev-parse HEAD)" = "$expected_commit"
test -z "$(git status --short)"
test "$(sha256sum "$manifest" | awk '{print $1}')" = "$manifest_sha"
test "$(sha256sum /research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif | awk '{print $1}')" = "$container_sha"
test ! -e "$results"
test ! -e "$workbase"
test ! -e "$status_dir"
test ! -e "$analysis"
mkdir -p "$results" "$workbase" "$status_dir"
export PYTHONPATH="$repo/src:$repo:$repo/phase1"
export OMP_NUM_THREADS=6

printf 'SPT_PILOT_START %s job=%s node=%s commit=%s manifest_sha=%s\n' \
  "$(date --iso-8601=seconds)" "$SLURM_JOB_ID" "$(hostname)" "$expected_commit" "$manifest_sha"
printf 'MATRIX groups=3 cards=6 arms=3 executions=18 waves=6 concurrent_gpu=3 candidate_cap_s=600\n'
scontrol show job "$SLURM_JOB_ID" -o | sed -E 's/(Command|WorkDir)=[^ ]+//g'

declare -a wave_pids=()
declare -a wave_indices=()
declare -a all_rcs=()

launch_entry() {
  local index=$1
  srun --exclusive --nodes=1 --ntasks=1 --cpus-per-task=6 --gres=gpu:1 \
    --job-name="spt-${index}" --chdir="$repo" \
    --output="$ops/index_${index}.stdout" --error="$ops/index_${index}.stderr" \
    "$py" -m phase1.spt_replay_entry \
    --index "$index" --repo "$repo" --manifest "$manifest" \
    --runtime-source "$runtime" --out "$results" --workbase "$workbase" \
    --status-dir "$status_dir" --container-sha256 "$container_sha" &
  wave_pids+=("$!")
  wave_indices+=("$index")
}

wait_wave() {
  local position rc
  set +e
  for position in "${!wave_pids[@]}"; do
    wait "${wave_pids[$position]}"
    rc=$?
    all_rcs+=("${wave_indices[$position]}:$rc")
    printf 'SPT_ENTRY_WAIT index=%s rc=%s time=%s\n' \
      "${wave_indices[$position]}" "$rc" "$(date --iso-8601=seconds)"
  done
  set -e
  wave_pids=()
  wave_indices=()
}

for card in 0 1 2 3 4 5; do
  base=$((card * 3))
  launch_entry "$base"
  launch_entry "$((base + 1))"
  launch_entry "$((base + 2))"
  wait_wave
done

printf 'SPT_ALL_ENTRY_RCS %s\n' "${all_rcs[*]}"
for item in "${all_rcs[@]}"; do
  if [[ "${item##*:}" -ne 0 ]]; then
    echo 'SPT_PILOT_INVALID_NONZERO_ENTRY' >&2
    exit 1
  fi
done

"$py" -m phase1.verify_spt_pilot \
  --manifest "$manifest" --manifest-sha256 "$manifest_sha" \
  --results "$results" --status-dir "$status_dir" --out "$analysis"
printf 'SPT_PILOT_DONE %s verdict=%s\n' \
  "$(date --iso-8601=seconds)" "$(tr -d '[:space:]' < "$analysis/verdict.txt")"
