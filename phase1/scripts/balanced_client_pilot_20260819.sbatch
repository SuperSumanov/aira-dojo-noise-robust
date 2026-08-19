#!/usr/bin/env bash
#SBATCH --job-name=client_pilot
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gpus-per-node=1
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --time=02:15:00
#SBATCH --signal=TERM@120
#SBATCH --output=/research/d7/spc/yzyang4/logs/balanced_client_pilot_%j.out

set -eo pipefail
source "$HOME/env_setup.sh"
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

: "${BALANCED_SOURCE_ROOT:?}"
: "${BALANCED_RUN_ROOT:?}"
: "${BALANCED_SOURCE_COMMIT:?}"
: "${BALANCED_PILOT_SHARD:?}"
ENV_FILE=/research/d7/spc/yzyang4/aira-dojo-reproduce/.env
PYTHON=/research/d7/spc/yzyang4/venvs/aira/bin/python
MANIFEST="$BALANCED_RUN_ROOT/manifest.json"

test "$(git -C "$BALANCED_SOURCE_ROOT" rev-parse HEAD)" = "$BALANCED_SOURCE_COMMIT"
test -z "$(git -C "$BALANCED_SOURCE_ROOT" status --porcelain --untracked-files=all)"
test -f "$ENV_FILE"
test -f "$MANIFEST"
set -a
source "$ENV_FILE"
set +a
export PYTHONPATH="$BALANCED_SOURCE_ROOT/src"
export LOGGING_DIR="$BALANCED_RUN_ROOT/outputs"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

case "$BALANCED_PILOT_SHARD" in
  0) pilot_indices="0 4 8" ;;
  1) pilot_indices="5 9 1" ;;
  2) pilot_indices="10 2 6" ;;
  3) pilot_indices="3 7 11" ;;
  *) echo "INVALID_PILOT_SHARD=$BALANCED_PILOT_SHARD" >&2; exit 64 ;;
esac

run_one() {
  local pilot_index="$1"
  local row client model base_url task seed issue resolved resolved_err rc_file run_rc
  mapfile -t row < <("$PYTHON" - "$MANIFEST" "$pilot_index" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
index = int(sys.argv[2])
entry = manifest["rows"][index]
if entry["index"] != index:
    raise SystemExit("manifest index mismatch")
for key in ("client_config", "model_id", "base_url", "task", "seed"):
    print(entry[key])
PY
  )
  test "${#row[@]}" -eq 5 || return $?
  client="${row[0]}"
  model="${row[1]}"
  base_url="${row[2]}"
  task="${row[3]}"
  seed="${row[4]}"
  issue="balanced_client_pilot_20260819_${model}_${task}_${seed}"
  resolved="$BALANCED_RUN_ROOT/resolved_${pilot_index}.yaml"
  resolved_err="$BALANCED_RUN_ROOT/resolved_${pilot_index}.stderr"
  rc_file="$BALANCED_RUN_ROOT/rc_${pilot_index}.json"

  local common=(
    "task=mlebench/$task"
    solver=mlebench/mcts
    interpreter=jupyter
    "solver/client@solver.operators.analyze.llm.client=$client"
    "solver/client@solver.operators.debug.llm.client=$client"
    "solver/client@solver.operators.draft.llm.client=$client"
    "solver/client@solver.operators.improve.llm.client=$client"
    solver.step_limit=4
    solver.execution_timeout=300
    solver.time_limit_secs=1800
    "metadata.seed=$seed"
    "metadata.git_issue_id=$issue"
    logger.use_wandb=false
    logger.write_env_vars=false
    logger.print_config=false
  )

  cd "$BALANCED_SOURCE_ROOT"
  "$PYTHON" -m dojo.main_run "${common[@]}" --cfg job >"$resolved" 2>"$resolved_err" || return $?
  "$PYTHON" - "$resolved" "$model" "$base_url" "$task" "$seed" <<'PY' || return $?
import sys
from pathlib import Path
import yaml

payload = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
solver = payload["solver"]
if solver["step_limit"] != 4 or solver["execution_timeout"] != 300 or solver["time_limit_secs"] != 1800:
    raise SystemExit("resolved budget mismatch")
if payload["task"]["name"] != sys.argv[4] or payload["metadata"]["seed"] != int(sys.argv[5]):
    raise SystemExit("resolved task/seed mismatch")
for name in ("analyze", "debug", "draft", "improve"):
    client = solver["operators"][name]["llm"]["client"]
    if client["model_id"] != sys.argv[2] or client["base_url"] != sys.argv[3]:
        raise SystemExit(f"resolved client mismatch: {name}")
print(f"RESOLVED_PILOT_PASS model={sys.argv[2]} task={sys.argv[4]} seed={sys.argv[5]} operators=4")
PY

  if "$PYTHON" -m dojo.main_run "${common[@]}"; then
    run_rc=0
  else
    run_rc=$?
  fi
  "$PYTHON" - "$rc_file.tmp" "$pilot_index" "$model" "$task" "$seed" "$run_rc" "$BALANCED_SOURCE_COMMIT" <<'PY'
import json
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(json.dumps({
    "index": int(sys.argv[2]), "model": sys.argv[3], "task": sys.argv[4],
    "seed": int(sys.argv[5]), "rc": int(sys.argv[6]), "source_commit": sys.argv[7]
}, sort_keys=True) + "\n", encoding="utf-8")
PY
  mv "$rc_file.tmp" "$rc_file"
  echo "BALANCED_CLIENT_PILOT_WORKER_DONE index=$pilot_index model=$model task=$task seed=$seed rc=$run_rc"
  return "$run_rc"
}

overall_rc=0
for pilot_index in $pilot_indices; do
  if run_one "$pilot_index"; then
    row_rc=0
  else
    row_rc=$?
  fi
  if [[ "$row_rc" -ne 0 ]]; then
    overall_rc=1
    echo "BALANCED_CLIENT_PILOT_ROW_FAILED index=$pilot_index rc=$row_rc" >&2
  fi
done
echo "BALANCED_CLIENT_PILOT_SHARD_DONE shard=$BALANCED_PILOT_SHARD rc=$overall_rc"
exit "$overall_rc"
