#!/usr/bin/env bash
set -eo pipefail
source ~/env_setup.sh
set -u

export PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES=""
export WANDB_MODE=disabled
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

root=/research/d7/spc/yzyang4/config-v2-producer-hook/real_config_smoke_65896b6_v1
run_root=/research/d7/spc/yzyang4/aira-dojo-runs
candidate_root=/research/d7/spc/yzyang4/config-v2-producer-hook/verify_fa2151b_v4/worktree
reference_root=/research/d7/spc/yzyang4/config-v2-producer-hook/verify_fa2151b_v4/reference
runner="$root/real_config_v2_schema_smoke.py"
selection="$root/selection.tsv"
python_bin=/research/d7/spc/yzyang4/venvs/aira/bin/python

if [[ -e "$root/started" ]]; then
    echo "REFUSE_EXISTING_SCHEMA_SMOKE_ROOT"
    exit 2
fi
mkdir -p "$root"
date -u +%Y-%m-%dT%H:%M:%SZ > "$root/started"

if [[ "$(git -C "$candidate_root" rev-parse HEAD)" != \
      "57d5d7bc617c5f303662e8e0e9db19a1026aa04e" ]]; then
    echo "CANDIDATE_COMMIT_MISMATCH"
    exit 2
fi
if [[ "$(git -C "$reference_root" rev-parse HEAD)" != \
      "f5955b0b887e6c89244fd5ac5b8b17de7b1ae88b" ]]; then
    echo "REFERENCE_COMMIT_MISMATCH"
    exit 2
fi

find "$run_root" -type f -name dojo_config.json \
    -printf '%T@\t%s\t%p\n' 2>/dev/null \
    | sort -n \
    | tail -20 \
    > "$selection"
if [[ "$(wc -l < "$selection")" != 20 ]]; then
    echo "SELECTION_COUNT_MISMATCH"
    exit 2
fi
selection_sha=$(sha256sum "$selection" | awk '{print $1}')

strace -f -qq -e trace=open,openat -o "$root/open_trace.log" \
    "$python_bin" "$runner" \
    --selection "$selection" \
    --candidate "$candidate_root/src/dojo/utils/config_v2_sidecar.py" \
    --reference-root "$reference_root" \
    > "$root/summary.json"

forbidden_hits=$(grep -iE \
    '(env_variables|journal|submission|grade|cards|pairs|\.tar|outcome|prediction)' \
    "$root/open_trace.log" | wc -l || true)
if [[ "$forbidden_hits" != 0 ]]; then
    echo "FORBIDDEN_PATH_OPEN_HITS=$forbidden_hits"
    exit 2
fi
summary_status=$("$python_bin" -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["status"])' \
    "$root/summary.json")
if [[ "$summary_status" != "REAL_CONFIG_SCHEMA_COMPAT_PASS" ]]; then
    echo "SUMMARY_STATUS_FAIL"
    exit 2
fi

credential_hits=$( \
    { grep -iE '(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16})' \
        "$root/summary.json" "$selection" || true; } | wc -l \
)
{
    echo "status=REAL_CONFIG_SCHEMA_COMPAT_PASS"
    echo "selection_rule=latest_20_regular_dojo_configs_by_mtime"
    echo "selection_sha256=$selection_sha"
    echo "candidate_commit=57d5d7bc617c5f303662e8e0e9db19a1026aa04e"
    echo "reference_commit=f5955b0b887e6c89244fd5ac5b8b17de7b1ae88b"
    echo "forbidden_path_open_hits=$forbidden_hits"
    echo "credential_output_hits=$credential_hits"
    echo "gpu_jobs_submitted=0"
    echo "env_or_archive_or_outcome_read=false"
    echo "historical_only_not_provenance=true"
} > "$root/receipt.txt"

find "$root" -type f ! -name SHA256SUMS ! -name SHA256SUMS.sha256 -print0 \
    | sort -z | xargs -0 sha256sum > "$root/SHA256SUMS"
sha256sum "$root/SHA256SUMS" > "$root/SHA256SUMS.sha256"
cat "$root/summary.json"
cat "$root/receipt.txt"
cat "$root/SHA256SUMS.sha256"
chmod -R a-w "$root"
