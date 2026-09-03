#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
readonly setup=/research/d7/spc/yzyang4/critic-component-g0/runtime-setup-20260903-r3
readonly target=/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-selective
test -f "$setup/dependency_closure.json"
test ! -e "$setup/validation.log"
exec >"$setup/validation.log" 2>&1
trap 'rc=$?; printf "validation_exit=%s\n" "$rc" >"$setup/exit_status.txt"' EXIT
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
mkdir -m 0700 "$setup/triton"
export TRITON_CACHE_DIR="$setup/triton"
"$target/bin/python" -m pip check >"$setup/pip_check.txt"
"$target/bin/python" /tmp/g0_validate_selective_runtime_20260903.py
printf 'BLACKWELL_RUNTIME_CPU_COMPATIBILITY_COMPLETE gpu_jobs=0 model_fits=0\n' >"$setup/COMPLETE"
