#!/usr/bin/env bash
#SBATCH --job-name=schema_gen_v2
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=2
#SBATCH --cpus-per-task=6
#SBATCH --gpus-per-node=2
#SBATCH --time=00:45:00
#SBATCH --constraint=rtx3090
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --output=/research/d7/spc/yzyang4/logs/schema_probe_generate_v2_%j.out

set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
set +u
source "$HOME/env_setup.sh"
set -a
source /research/d7/spc/yzyang4/aira-dojo-reproduce/.env
set +a
set -u

repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
ops=/research/d7/spc/yzyang4/schema_probe_ops/schema_probe_repair_v2
export LOGGING_DIR="$ops/runs"
run_root="$LOGGING_DIR/aira-dojo"
status_dir="$ops/status"
aira_py=/research/d7/spc/yzyang4/venvs/aira/bin/python
audit_py=/research/d7/spc/yzyang4/venvs/exp/bin/python
commit=c1dc17420e95b9e2994a474c25afdcb85063ab36
issue=schema_probe_repair_v2
seed=862

cd "$repo"
test "$(git rev-parse HEAD)" = "$commit"
test -z "$(git status --short)"
test -d "$ops/prereg"
test ! -e "$run_root/user_yzyang4_issue_$issue"
test ! -e "$status_dir"
mkdir -p "$status_dir"
test -n "${PRIMARY_KEY_DEEPSEEK_V4_FLASH:-}"
export PYTHONPATH="$repo/src:$repo"
export SCHEMA_PROBE_AIRA_PYTHON="$aira_py"
export OMP_NUM_THREADS=6

printf 'SCHEMA_PROBE_V2_GENERATION_START %s job=%s node=%s commit=%s\n' \
  "$(date --iso-8601=seconds)" "$SLURM_JOB_ID" "$(hostname)" "$commit"
printf 'MATRIX tasks=2 seed=%s root_plus_draft_plus_optional_debug=3 num_children=1 max_debug_depth=1 stop_after_first_valid=true execution_timeout=600 gpu=2\n' "$seed"
scontrol show job "$SLURM_JOB_ID" -o | sed -E 's/(Command|WorkDir)=[^ ]+//g'

srun --exclusive --nodes=1 --ntasks=1 --cpus-per-task=6 --gres=gpu:1 \
  --job-name=schema-spaceship-v2 --chdir="$repo" \
  --output="$ops/index_0.stdout" --error="$ops/index_0.stderr" \
  "$audit_py" phase1/schema_probe_repair_generation_entry.py \
  --task spaceship-titanic --index 0 --seed "$seed" --issue "$issue" \
  --status-dir "$status_dir" &
pid0=$!

srun --exclusive --nodes=1 --ntasks=1 --cpus-per-task=6 --gres=gpu:1 \
  --job-name=schema-tweet-v2 --chdir="$repo" \
  --output="$ops/index_1.stdout" --error="$ops/index_1.stderr" \
  "$audit_py" phase1/schema_probe_repair_generation_entry.py \
  --task tweet-sentiment-extraction --index 1 --seed "$seed" --issue "$issue" \
  --status-dir "$status_dir" &
pid1=$!

set +e
wait "$pid0"
wait0=$?
wait "$pid1"
wait1=$?
set -e
printf 'SCHEMA_PROBE_V2_ENTRY_WAIT_RCS index0=%s index1=%s time=%s\n' \
  "$wait0" "$wait1" "$(date --iso-8601=seconds)"
if [[ "$wait0" -ne 0 || "$wait1" -ne 0 ]]; then
  exit 1
fi

"$audit_py" phase1/build_schema_probe_repair_manifest.py \
  --run-root "$run_root" \
  --status-dir "$status_dir" \
  --issue "$issue" \
  --seed "$seed" \
  --tasks spaceship-titanic tweet-sentiment-extraction \
  --out "$ops/generation_manifest.json" \
  --audit "$ops/generation_manifest.audit.json"

printf 'SCHEMA_PROBE_V2_GENERATION_DONE %s\n' "$(date --iso-8601=seconds)"

