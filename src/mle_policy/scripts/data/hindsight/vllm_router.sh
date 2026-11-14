#!/usr/bin/env bash
# Input: instance count, TP size, build/vllm/vllm.sif and local model caches.
# Output: tmp/hindsight_instance_<index>.log and tmp/hindsight_router.log.
set -eo pipefail

instances=2
tp=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --instances) instances=$2; shift 2 ;;
    --tp) tp=$2; shift 2 ;;
    -h|--help)
      echo "Usage: bash $0 [--instances 2] [--tp 1]"
      echo "Uses instances * tp GPUs, starting at GPU 0; instance ports start at 8000."
      exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../../../.." && pwd)
cd "$REPO_ROOT"
mkdir -p tmp
pids=()
backends=()
trap 'trap - EXIT INT TERM; kill "${pids[@]}" 2>/dev/null || true; wait || true' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for ((instance=0; instance<instances; instance++)); do
  gpus=()
  for ((offset=0; offset<tp; offset++)); do
    gpus+=("$((instance * tp + offset))")
  done
  devices=$(IFS=,; echo "${gpus[*]}")
  port=$((8000 + instance))
  backends+=("http://127.0.0.1:$port")
  singularity exec --nv --cleanenv \
    --env CUDA_VISIBLE_DEVICES="$devices" \
    --env LD_LIBRARY_PATH=/usr/local/cuda/compat:$LD_LIBRARY_PATH \
    --env VLLM_WORKER_MULTIPROC_METHOD=spawn \
    --env VLLM_CACHE_ROOT=/research/d2/gds/zzchen2/vllm_cache \
    --env TRITON_HOME=/research/d2/gds/zzchen2/triton_home \
    --env TORCH_HOME=/research/d2/gds/zzchen2/torchhome \
    --env HF_HOME=/research/d2/gds/zzchen2/transformerscache \
    --env HF_HUB_OFFLINE=1 \
    -B /research/d2/gds/zzchen2:/research/d2/gds/zzchen2 \
    build/vllm/vllm.sif \
    vllm serve Qwen/Qwen3.8-27B \
      --served-model-name qwen3.8-27b \
      --host 0.0.0.0 \
      --port "$port" \
      --api-key sk-local-vllm \
      --tensor-parallel-size "$tp" \
      --max-model-len 131072 \
      --gpu-memory-utilization 0.95 \
      --limit-mm-per-prompt '{"image":0,"video":0}' \
      --max-num-seqs 8 > "tmp/hindsight_instance_${instance}.log" 2>&1 &
  pids+=("$!")
  echo "Starting instance $instance: GPUs $devices, port $port"
done

while true; do
  ready=true
  for ((instance=0; instance<instances; instance++)); do
    if ! kill -0 "${pids[instance]}" 2>/dev/null; then
      echo "Instance $instance exited; see tmp/hindsight_instance_${instance}.log" >&2
      exit 1
    fi
    if ! curl --fail --silent --output /dev/null --noproxy '*' \
      --connect-timeout 2 --max-time 5 "${backends[instance]}/health"; then
      ready=false
    fi
  done
  if "$ready"; then break; fi
  sleep 5
done
echo "All instances ready; starting router on port 7999"

source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
export PYTHONPATH="$PWD/src:$PWD${PYTHONPATH:+:$PYTHONPATH}"

python -m mle_policy.src.data.hindsight.router \
  --backends "${backends[@]}" \
  --host 127.0.0.1 --port 7999 > tmp/hindsight_router.log 2>&1 &
pids+=("$!")

wait "${pids[instances]}"
