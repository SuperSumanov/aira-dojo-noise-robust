#!/usr/bin/env bash
#SBATCH --job-name=probe_ab_v2_gen
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --cpus-per-task=6
#SBATCH --gpus-per-node=4
#SBATCH --time=01:40:00
#SBATCH --constraint=rtx3090
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --output=/research/d7/spc/yzyang4/logs/probe_contract_ab_v2_generate_%j.out

set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
set +u
source "$HOME/env_setup.sh"
set -a
source /research/d7/spc/yzyang4/aira-dojo-reproduce/.env
set +a
set -u

repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
ops=/research/d7/spc/yzyang4/probe_contract_ab_ops/probe_contract_ab_safety_v2
export LOGGING_DIR="$ops/runs"
run_root="$LOGGING_DIR/aira-dojo"
status_dir="$ops/status"
aira_py=/research/d7/spc/yzyang4/venvs/aira/bin/python
audit_py=/research/d7/spc/yzyang4/venvs/exp/bin/python
commit=$(cat "$ops/prereg/expected_commit.txt")
seed=887

cd "$repo"
test "$(git rev-parse HEAD)" = "$commit"
test -z "$(git status --short)"
test -d "$ops/prereg/resolved_configs"
test -f "$ops/prereg/hydra_audit.json"
test ! -e "$run_root/user_yzyang4_issue_probe_contract_ab_safety_v2_original"
test ! -e "$run_root/user_yzyang4_issue_probe_contract_ab_safety_v2_contract"
test ! -e "$status_dir"
mkdir -p "$status_dir"
test -n "${PRIMARY_KEY_DEEPSEEK_V4_FLASH:-}"
export PYTHONPATH="$repo/src:$repo"
export PROBE_AB_AIRA_PYTHON="$aira_py"
export OMP_NUM_THREADS=6

printf 'PROBE_CONTRACT_AB_GENERATION_START %s job=%s node=%s commit=%s\n' \
  "$(date --iso-8601=seconds)" "$SLURM_JOB_ID" "$(hostname)" "$commit"
printf 'MATRIX blocks=8 entries=16 seed=%s waves=4 pair_concurrent=true gpu=4 candidate_cap_s=600\n' "$seed"
scontrol show job "$SLURM_JOB_ID" -o | sed -E 's/(Command|WorkDir)=[^ ]+//g'

declare -a wave_pids=()
declare -a wave_indices=()
declare -a all_rcs=()

launch_entry() {
  local index=$1
  local task=$2
  local arm=$3
  local issue=$4
  srun --exclusive --nodes=1 --ntasks=1 --cpus-per-task=6 --gres=gpu:1 \
    --job-name="probe-ab-${index}-${arm}" --chdir="$repo" \
    --output="$ops/index_${index}.stdout" --error="$ops/index_${index}.stderr" \
    "$audit_py" -m phase1.probe_contract_ab_generation_entry \
    --version v2 \
    --index "$index" --task "$task" --arm "$arm" --seed "$seed" --issue "$issue" \
    --status-dir "$status_dir" &
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
    printf 'PROBE_AB_ENTRY_WAIT index=%s rc=%s time=%s\n' \
      "${wave_indices[$position]}" "$rc" "$(date --iso-8601=seconds)"
  done
  set -e
  wave_pids=()
  wave_indices=()
}

# Wave 1: two task blocks, both arms simultaneous.
launch_entry 0 aerial-cactus-identification original probe_contract_ab_safety_v2_original
launch_entry 1 aerial-cactus-identification contract probe_contract_ab_safety_v2_contract
launch_entry 2 AI4Code contract probe_contract_ab_safety_v2_contract
launch_entry 3 AI4Code original probe_contract_ab_safety_v2_original
wait_wave

# Wave 2.
launch_entry 4 denoising-dirty-documents original probe_contract_ab_safety_v2_original
launch_entry 5 denoising-dirty-documents contract probe_contract_ab_safety_v2_contract
launch_entry 6 kuzushiji-recognition contract probe_contract_ab_safety_v2_contract
launch_entry 7 kuzushiji-recognition original probe_contract_ab_safety_v2_original
wait_wave

# Wave 3.
launch_entry 8 learning-agency-lab-automated-essay-scoring-2 original probe_contract_ab_safety_v2_original
launch_entry 9 learning-agency-lab-automated-essay-scoring-2 contract probe_contract_ab_safety_v2_contract
launch_entry 10 text-normalization-challenge-english-language contract probe_contract_ab_safety_v2_contract
launch_entry 11 text-normalization-challenge-english-language original probe_contract_ab_safety_v2_original
wait_wave

# Wave 4.
launch_entry 12 mlsp-2013-birds original probe_contract_ab_safety_v2_original
launch_entry 13 mlsp-2013-birds contract probe_contract_ab_safety_v2_contract
launch_entry 14 whale-categorization-playground contract probe_contract_ab_safety_v2_contract
launch_entry 15 whale-categorization-playground original probe_contract_ab_safety_v2_original
wait_wave

printf 'PROBE_AB_ALL_ENTRY_RCS %s\n' "${all_rcs[*]}"
for item in "${all_rcs[@]}"; do
  if [[ "${item##*:}" -ne 0 ]]; then
    echo 'PROBE_AB_GENERATION_INVALID_NONZERO_ENTRY' >&2
    exit 1
  fi
done

"$audit_py" -m phase1.build_probe_contract_ab_manifest \
  --version v2 \
  --run-root "$run_root" \
  --status-dir "$status_dir" \
  --out "$ops/generation_manifest.json"
printf 'PROBE_CONTRACT_AB_GENERATION_DONE %s\n' "$(date --iso-8601=seconds)"
