#!/usr/bin/env bash
# Drop the vision-tower LoRA tensors a merged SFT adapter carries, so vLLM can load it.
# Usage: bash prune_lora_adapter_for_vllm.sh ADAPTER_DIR [OUTPUT_DIR]
set -euo pipefail

ADAPTER_DIR=${1:?expected the lora_adapter directory written by verl.model_merger}
OUTPUT_DIR=${2:-}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../../.." && pwd)
export PYTHONPATH="$REPO_ROOT/src/mle_policy${PYTHONPATH:+:$PYTHONPATH}"
cd "$REPO_ROOT"

if [[ -n $OUTPUT_DIR ]]; then
    python -m src.export.lora_adapter --adapter-dir "$ADAPTER_DIR" --output-dir "$OUTPUT_DIR"
else
    python -m src.export.lora_adapter --adapter-dir "$ADAPTER_DIR"
fi
