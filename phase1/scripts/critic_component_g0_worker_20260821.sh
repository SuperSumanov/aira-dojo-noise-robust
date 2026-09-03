#!/usr/bin/env bash
# Dev-only, fixed-ten-step Qwen3-1.7B engineering calibration. Never accepts test pairs.
set -euo pipefail
umask 077

: "${G0_CONTROL_ROOT:?set a clean checkout containing phase1 verification code}"
: "${G0_SOURCE_ROOT:?set the clean senior source checkout with both audited patches}"
: "${G0_EXPECTED_SOURCE_COMMIT:?pin the patched source commit}"
: "${G0_VENV:?set the critic virtual environment}"
: "${G0_TRAIN_PAIRS:?set the immutable component-split train JSONL}"
: "${G0_DEV_PAIRS:?set the immutable component-split dev JSONL}"
: "${G0_CARDS:?set the immutable Cards JSON}"
: "${G0_MODEL_SNAPSHOT:?set the offline pinned Qwen snapshot}"
: "${G0_RUN_ROOT:?set a new output root}"
: "${SLURM_JOB_ID:?G0 must run in a Slurm allocation}"
: "${CUDA_VISIBLE_DEVICES:?Slurm must expose exactly two GPUs}"

readonly verifier="$G0_CONTROL_ROOT/phase1/verify_critic_component_g0.py"
readonly model_manifest="$G0_CONTROL_ROOT/phase1/manifests/qwen3-1.7b-base-ea980cb0a6c2ae4b936e82123acc929f1cec04c1.sha256"
readonly launcher="$G0_SOURCE_ROOT/src/mle_critic/scripts/train/pro6000/train_rm_confirmatory_one.sh"
readonly python_bin="$G0_VENV/bin/python"
readonly accelerate_bin="$G0_VENV/bin/accelerate"

test -x "$python_bin"
test -x "$accelerate_bin"
test -f "$verifier"
test -f "$model_manifest"
test -f "$launcher"
test ! -e "$G0_RUN_ROOT"
mkdir -m 0700 -p "$G0_RUN_ROOT"

readonly worker_log="$G0_RUN_ROOT/worker.log"
exec > "$worker_log" 2>&1

readonly output_dir="$G0_RUN_ROOT/output"
readonly launcher_log="$G0_RUN_ROOT/accelerate.log"
readonly resource_usage="$G0_RUN_ROOT/resource_usage.txt"
readonly telemetry="$G0_RUN_ROOT/gpu_telemetry.csv"
readonly preflight="$G0_RUN_ROOT/preflight.json"
readonly verification="$G0_RUN_ROOT/verification.json"

export PATH="$G0_VENV/bin:$PATH"
export VIRTUAL_ENV="$G0_VENV"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export NCCL_DEBUG=WARN
export PYTHONHASHSEED=6

scratch_base=${SLURM_TMPDIR:-/tmp}
readonly scratch_root="$scratch_base/critic-g0-$SLURM_JOB_ID"
mkdir -m 0700 -p "$scratch_root/triton" "$scratch_root/torch-extensions"
export TRITON_CACHE_DIR="$scratch_root/triton"
export TORCH_EXTENSIONS_DIR="$scratch_root/torch-extensions"

"$python_bin" "$verifier" preflight \
  --run-root "$G0_RUN_ROOT" \
  --output-dir "$output_dir" \
  --source-root "$G0_SOURCE_ROOT" \
  --expected-source-commit "$G0_EXPECTED_SOURCE_COMMIT" \
  --control-root "$G0_CONTROL_ROOT" \
  --train-pairs "$G0_TRAIN_PAIRS" \
  --dev-pairs "$G0_DEV_PAIRS" \
  --cards "$G0_CARDS" \
  --model-snapshot "$G0_MODEL_SNAPSHOT" \
  --model-manifest "$model_manifest" \
  --receipt "$preflight"

printf '%s\n' \
  'timestamp_utc,visible_id,name,uuid,memory_total_mib,memory_used_mib,utilization_gpu_pct,power_draw_w' \
  > "$telemetry"

telemetry_pid=
collect_telemetry() {
  local timestamp device row
  local -a visible_devices
  IFS=',' read -r -a visible_devices <<< "$CUDA_VISIBLE_DEVICES"
  while true; do
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    for device in "${visible_devices[@]}"; do
      row=$(nvidia-smi -i "$device" \
        --query-gpu=name,uuid,memory.total,memory.used,utilization.gpu,power.draw \
        --format=csv,noheader,nounits)
      printf '%s,%s,%s\n' "$timestamp" "$device" "$row" >> "$telemetry"
    done
    sleep 5
  done
}
stop_telemetry() {
  if [[ -n ${telemetry_pid:-} ]]; then
    kill "$telemetry_pid" 2>/dev/null || true
    wait "$telemetry_pid" 2>/dev/null || true
    telemetry_pid=
  fi
}
trap stop_telemetry EXIT INT TERM
collect_telemetry &
telemetry_pid=$!

export CONFIRM_TRAIN_PAIRS="$G0_TRAIN_PAIRS"
export CONFIRM_DEV_PAIRS="$G0_DEV_PAIRS"
export CONFIRM_CARDS="$G0_CARDS"
export CONFIRM_MODEL="$G0_MODEL_SNAPSHOT"
export CONFIRM_OUTPUT_DIR="$output_dir"
export CONFIRM_LOG_PATH="$launcher_log"
export CONFIRM_SEED=6
export CONFIRM_PER_DEVICE_TRAIN_BATCH=8
export CONFIRM_PER_DEVICE_EVAL_BATCH=8
export CONFIRM_GRAD_ACCUM=8
export CONFIRM_NUM_PROCESSES=2
export CONFIRM_MAX_LEN=16384
export CONFIRM_EVAL_STEPS=10
export CONFIRM_EPOCHS=1
export CONFIRM_MAX_STEPS=10
export CONFIRM_LEARNING_RATE=1e-5
export CONFIRM_EFFECTIVE_PAIR_BATCH=128
export CONFIRM_LR_SCHEDULER_TYPE=cosine
export CONFIRM_WARMUP_RATIO=0.03
if [[ ${G0_RECOVERY_FINAL_ONLY:-0} == 1 ]]; then
  export CONFIRM_G0_FINAL_ONLY=1
  printf '[g0-recovery] final_only=1 load_best_model_at_end=false max_steps=10 eval_steps=10\n'
fi
export CONFIRM_EXPECTED_TRAIN_SHA256=0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e
export CONFIRM_EXPECTED_DEV_SHA256=3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4
export CONFIRM_EXPECTED_CARDS_SHA256=5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb

"$python_bin" -c \
  'import datetime as d,json,time; print("[g0-worker-timing] "+json.dumps({"event":"launcher_start","monotonic_ns":time.monotonic_ns(),"utc":d.datetime.now(d.timezone.utc).isoformat()},sort_keys=True),flush=True)'
set +e
/usr/bin/time -v -o "$resource_usage" bash "$launcher"
training_rc=$?
set -e
stop_telemetry
printf 'training_exit_status=%s\n' "$training_rc" > "$G0_RUN_ROOT/training_exit_status.txt"
if (( training_rc != 0 )); then
  printf 'status=G0_TRAINING_FAILED\n' > "$G0_RUN_ROOT/FAILED"
  exit "$training_rc"
fi

"$python_bin" "$verifier" verify \
  --preflight "$preflight" \
  --output-dir "$output_dir" \
  --launcher-log "$worker_log" \
  --resource-usage "$resource_usage" \
  --telemetry "$telemetry" \
  --receipt "$verification"

exec 1>&- 2>&-
sha256sum \
  "$preflight" \
  "$verification" \
  "$worker_log" \
  "$launcher_log" \
  "$resource_usage" \
  "$telemetry" \
  "$G0_RUN_ROOT/training_exit_status.txt" \
  > "$G0_RUN_ROOT/SHA256SUMS.tmp"
mv "$G0_RUN_ROOT/SHA256SUMS.tmp" "$G0_RUN_ROOT/SHA256SUMS"
printf 'status=G0_ENGINEERING_CALIBRATION_VALID\n' > "$G0_RUN_ROOT/COMPLETE"
